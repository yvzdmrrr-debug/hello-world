"""Skill kataloğu ve otomatik Skill fabrikası (Bölüm 6, 19).

Bir Skill, `run(girdi: str) -> str` fonksiyonu içeren tek bir Python dosyasıdır.
Kurulum sırası: statik güvenlik taraması → izole alt süreçte testler → sürümlü kayıt.
Eski sürüm dosyaları silinmez (skills/<ad>/v<N>.py).
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .db import DB, now
from .security import Security

SAFE_IMPORTS = {"ast", "operator", "math", "re", "json", "statistics", "datetime", "collections", "itertools",
                "functools", "string", "textwrap", "decimal", "fractions", "unicodedata"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
                "globals", "locals", "vars", "getattr", "setattr", "delattr"}

_RUNNER = """
import json, runpy, sys
req = json.load(sys.stdin)
ns = runpy.run_path(req["path"])
print("\\x00" + json.dumps({"out": str(ns["run"](req["input"]))}))
"""


class SkillError(Exception):
    pass


def scan(code: str) -> list[str]:
    """Düşük riskli Skill için güvenlik bulgularını döndürür (boş liste = temiz)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"sözdizimi hatası: {e}"]
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            issues += [f"izin verilmeyen modül: {a.name}" for a in node.names
                       if a.name.split(".")[0] not in SAFE_IMPORTS]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in SAFE_IMPORTS:
                issues.append(f"izin verilmeyen modül: {node.module}")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            issues.append(f"izin verilmeyen işlev: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            issues.append(f"izin verilmeyen özel nitelik: {node.attr}")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "run" for n in tree.body):
        issues.append("run(girdi) fonksiyonu yok")
    return issues


def execute(path: str, text: str, timeout: float = 5.0) -> str:
    """Skill dosyasını ayrı, izole bir Python sürecinde çalıştırır."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            p = subprocess.run(
                [sys.executable, "-I", "-c", _RUNNER],
                input=json.dumps({"path": os.path.abspath(path), "input": text}),
                capture_output=True, text=True, timeout=timeout, cwd=tmp, env={})
        except subprocess.TimeoutExpired:
            raise SkillError(f"zaman aşımı ({timeout} sn)")
    if p.returncode != 0 or "\x00" not in p.stdout:
        raise SkillError((p.stderr.strip().splitlines() or ["bilinmeyen hata"])[-1])
    return json.loads(p.stdout.split("\x00", 1)[1])["out"]


class Skills:
    def __init__(self, db: DB, security: Security, root: str = "skills"):
        self.db, self.sec, self.root = db, security, Path(root)

    def get(self, name: str):
        return self.db.one("SELECT * FROM skills WHERE name=?", (name,))

    def catalog(self) -> list[dict]:
        return self.db.all("SELECT * FROM skills ORDER BY name")

    def install(self, name: str, description: str, code: str,
                tests: list[tuple[str, str]], *, projects: str = "") -> dict:
        """Skill'i dener; yalnızca bütün testler geçerse kataloğa ekler.

        Dönen rapor: {"ok", "version", "issues", "results"}. Başarısız Skill kurulmaz.
        """
        if not name.isidentifier():
            raise SkillError("Skill adı harf, rakam ve alt çizgiden oluşmalı")
        if not tests:
            raise SkillError("Test edilmemiş Skill kurulamaz: en az bir test gerekli")
        issues = scan(code)
        syntax_or_shape = [i for i in issues if "sözdizimi" in i or "run(" in i]
        if syntax_or_shape:
            return {"ok": False, "version": None, "issues": issues, "results": []}
        permission = "yuksek" if issues else "dusuk"
        # Güvenli listenin dışına çıkan Skill ancak kullanıcı onayıyla kurulur.
        self.sec.check("skill.install_high" if issues else "skill.install_low", name)

        old = self.get(name)
        version = (old["version"] + 1) if old else 1
        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"v{version}.py"
        path.write_text(code, encoding="utf-8")

        results = []
        for given, expected in tests:
            try:
                got = execute(str(path), given)
                results.append({"input": given, "expected": expected, "got": got,
                                "ok": got == expected})
            except SkillError as e:
                results.append({"input": given, "expected": expected, "got": f"HATA: {e}",
                                "ok": False})
        ok = all(r["ok"] for r in results)
        if not ok:
            path.unlink()  # başarısız aday kataloğa girmez; önceki sürüm aynen kalır
            return {"ok": False, "version": None, "issues": issues, "results": results}

        status = f"GEÇTİ ({len(results)}/{len(results)})"
        self.db.run(
            "INSERT INTO skills(name,description,version,tools,deps,permission,test_status,"
            "last_used,uses,successes,projects,path) VALUES(?,?,?,?,?,?,?,NULL,0,0,?,?) "
            "ON CONFLICT(name) DO UPDATE SET description=excluded.description,"
            "version=excluded.version,permission=excluded.permission,"
            "test_status=excluded.test_status,path=excluded.path",
            (name, description, version, "python", "stdlib", permission, status,
             projects, str(path)))
        return {"ok": True, "version": version, "issues": issues, "results": results}

    def run(self, name: str, text: str) -> str:
        skill = self.get(name)
        if not skill:
            raise SkillError(f"Skill bulunamadı: {name}")
        self.sec.check("skill.run", name)
        self.db.run("UPDATE skills SET uses=uses+1, last_used=? WHERE name=?", (now(), name))
        out = execute(skill["path"], text)
        self.db.run("UPDATE skills SET successes=successes+1 WHERE name=?", (name,))
        return out

    def rollback(self, name: str) -> int:
        """Skill'i bir önceki sürüm dosyasına döndürür (onay gerekir)."""
        skill = self.get(name)
        if not skill or skill["version"] < 2:
            raise SkillError("Geri alınacak önceki sürüm yok")
        prev = self.root / name / f"v{skill['version'] - 1}.py"
        if not prev.exists():
            raise SkillError("Önceki sürüm dosyası bulunamadı")
        self.sec.check("version.rollback", name)
        self.db.run("UPDATE skills SET version=?, path=? WHERE name=?",
                    (skill["version"] - 1, str(prev), name))
        return skill["version"] - 1

    def duplicates(self) -> list[tuple[str, str]]:
        """Açıklamaları büyük ölçüde örtüşen Skill çiftleri (silmez, yalnızca bildirir)."""
        cat, out = self.catalog(), []
        for i, a in enumerate(cat):
            wa = set(a["description"].lower().split())
            for b in cat[i + 1:]:
                wb = set(b["description"].lower().split())
                if wa and wb and len(wa & wb) / len(wa | wb) > 0.6:
                    out.append((a["name"], b["name"]))
        return out


# --- Hazır gelen Skill'ler: kurulumda aynı fabrikadan, testleriyle birlikte geçer ---
BUILTIN = {
    "hesapla": ("Dört işlem, üs ve parantez içeren aritmetik ifadeyi hesaplar", '''
import ast, operator
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
       ast.USub: operator.neg, ast.UAdd: operator.pos}

def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 1000:
            raise ValueError("üs çok büyük")
        return OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](_ev(n.operand))
    raise ValueError("desteklenmeyen ifade")

def run(girdi):
    v = _ev(ast.parse(girdi.strip().replace(",", ".").replace("^", "**"), mode="eval").body)
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(round(v, 10))
''', [("2+2", "4"), ("(3+5)*2", "16"), ("10/4", "2.5"), ("2^10", "1024")]),
    "metin_istatistik": ("Metnin kelime, cümle ve karakter sayısını verir", '''
import re

def run(girdi):
    kelime = len(girdi.split())
    cumle = len([c for c in re.split(r"[.!?]+", girdi) if c.strip()])
    return f"kelime={kelime} cümle={cumle} karakter={len(girdi)}"
''', [("Merhaba dünya. Nasılsın?", "kelime=3 cümle=2 karakter=24")]),
    "ozetle": ("Metni en sık geçen kelimelere göre en önemli iki cümleyle özetler", '''
import re
from collections import Counter

def run(girdi):
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\\s+", girdi.strip()) if c.strip()]
    if len(cumleler) <= 2:
        return " ".join(cumleler)
    sayac = Counter(k for k in re.findall(r"\\w+", girdi.lower()) if len(k) > 3)
    puan = {i: sum(sayac[k] for k in re.findall(r"\\w+", c.lower())) for i, c in enumerate(cumleler)}
    secilen = sorted(sorted(puan, key=lambda i: -puan[i])[:2])
    return " ".join(cumleler[i] for i in secilen)
''', [("Tek cümle.", "Tek cümle."),
      ("Kedi evde uyur. Kedi balık sever ve kedi oyun oynar. Hava güzel. Kedi mutlu bir kedi.",
       "Kedi balık sever ve kedi oyun oynar. Kedi mutlu bir kedi.")]),
}
