"""Yerel Dashboard: gerçek durumu veritabanından okur. Yalnızca 127.0.0.1'e bağlanır."""
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import registry
from .core import Jarvis, format_report

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#16181d;--mut:#667085;--line:#e3e6ec;--ok:#157f4b;
--warn:#a35a00;--bad:#b3261e;--acc:#2f5bd8}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--fg:#e8eaf0;
--mut:#98a1b3;--line:#2a2f3a;--ok:#4cc38a;--warn:#f0a94a;--bad:#ff7b72;--acc:#7da2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:16px}
h1{font-size:22px;margin:0}h2{font-size:15px;margin:0 0 10px;color:var(--mut);
text-transform:uppercase;letter-spacing:.04em}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;
margin-bottom:16px}.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;
overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}
td,th{text-align:left;padding:4px 8px 4px 0;border-bottom:1px solid var(--line);
vertical-align:top}th{color:var(--mut);font-weight:500}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;
border:1px solid currentColor}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.mut{color:var(--mut)}button,input{font:inherit;padding:6px 12px;border-radius:8px;
border:1px solid var(--line);background:var(--card);color:var(--fg)}
button{cursor:pointer}button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}
form.row{display:flex;gap:8px}form.row input{flex:1;min-width:0}form{display:inline}
pre{white-space:pre-wrap;margin:10px 0 0;font-size:13px}
.big{font-size:24px;font-weight:600}
.bar{display:flex;align-items:center;gap:8px;font-size:13px;margin:4px 0}
.bar span{flex:0 0 38%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar i{display:block;height:10px;min-width:2px;border-radius:5px;background:var(--acc)}
.bar b{font-weight:500;color:var(--mut)}
"""

STATE_CLASS = {"TAMAMLANDI": "ok", "BAŞARISIZ": "bad", "ENGELLENDİ": "warn",
               "ONAY BEKLİYOR": "warn", "KOD": "ok", "LLM": "warn", "PLAN": "mut"}


def e(x) -> str:
    return html.escape(str(x if x is not None else "—"))


def pill(text) -> str:
    return f'<span class="pill {STATE_CLASS.get(text, "mut")}">{e(text)}</span>'


def table(headers, rows) -> str:
    if not rows:
        return '<p class="mut">Kayıt yok.</p>'
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def render(j: Jarvis, report: str = "") -> str:
    s = j.status()
    m, b = s["metrikler"], s["bilesenler"]
    llm_ok = s["llm"]["bagli"]
    comp = table(["Grup", "Toplam", "Kodla çalışan", "LLM ile", "Planlanan"], [
        [n, b[k]["toplam"], b[k]["KOD"], b[k]["LLM"], b[k]["PLAN"]]
        for n, k in (("Departman", "departman"), ("Bilişsel sistem", "bilissel"),
                     ("Evrim motoru", "motor"))])
    detail = "".join(
        f"<details><summary>{title}</summary>" + table(["Ad", "Durum"],
            [[e(i[0]), pill(i[1])] for i in items]) + "</details>"
        for title, items in (("Departmanlar", registry.DEPARTMENTS),
                             ("Bilişsel sistemler", registry.COGNITIVE),
                             ("Evrim motorları", registry.ENGINES)))
    approvals = table(["No", "İşlem", "Ayrıntı", ""], [
        [a["id"], e(a["action"]), e(a["detail"]),
         f'<form method="post" action="/approve"><input type="hidden" name="id" value="{a["id"]}">'
         f'<button class="pri">Onayla</button></form> '
         f'<form method="post" action="/reject"><input type="hidden" name="id" value="{a["id"]}">'
         f'<button>Reddet</button></form>'] for a in s["onaylar"]])
    stop_btn = ('<form method="post" action="/resume"><button class="pri">Devam ettir</button></form>'
                if s["durduruldu"] else
                '<form method="post" action="/stop"><button>Sistemi durdur</button></form>')
    rate = lambda v: "—" if v is None else f"%{v}"
    ek, kb = s["ekonomi"], s["kabul"]

    def bars(rows, label, value, unit=""):
        top = max((r[value] or 0 for r in rows), default=0) or 1
        return "".join(
            f'<div class="bar"><span>{e(r[label])}</span><i style="width:{(r[value] or 0) / top * 60:.1f}%">'
            f'</i><b>{(r[value] or 0):,.4g}{unit}</b></div>' for r in rows) or '<p class="mut">Kayıt yok.</p>'
    prices = {m["id"]: j.economy.price(m["id"]) for m in s["modeller"]}

    def price_cell(mid):
        p = prices[mid]
        return e(f"{p['input_per_m']} / {p['output_per_m']}") if p else '<span class="warn">bilinmiyor</span>'
    llm_section = f"""
<h2 style="margin:20px 0 10px">LLM Komuta Merkezi</h2>
<div class="grid">
<div class="card"><h2>Token ve maliyet</h2><div class="big">{ek["maliyet"]:.4f} USD</div>
{table(["Gösterge", "Değer"], [["İstek sayısı", ek["istek"]], ["Giriş tokenı", ek["giris"]],
 ["Çıkış tokenı", ek["cikis"]], ["Bugün harcanan", f'{ek["gunluk_harcanan"]:.4f} USD'],
 ["Günlük kalan bütçe", f'{ek["gunluk_kalan"]:.4f} USD'],
 ["Bu ay harcanan", f'{ek["aylik_harcanan"]:.4f} USD'],
 ["Aylık kalan bütçe", f'{ek["aylik_kalan"]:.4f} USD'], ["Devredilen görev", ek["devir"]],
 ["Tahmini (kesin olmayan) kayıt", ek["tahmini"]],
 ["Fiyatı bilinmeyen kayıt", ek["fiyati_bilinmeyen"]]])}</div>
<div class="card"><h2>Model bazlı harcama (USD)</h2>{bars(ek["model_bazli"], "model_id", "maliyet")}
<h2 style="margin-top:14px">Günlük token (giriş + çıkış)</h2>
{bars([{"gun": g["gun"], "t": (g["giris"] or 0) + (g["cikis"] or 0)} for g in ek["gunluk"]], "gun", "t")}</div>
<div class="card"><h2>Sağlayıcılar</h2>{table(["Ad", "Tür", "Durum", "Son hata"],
 [[e(p["name"]), e(p["kind"]), e(p["status"]), e(p["last_error"] or "")] for p in s["llm"]["saglayicilar"]])}
<h2 style="margin-top:14px">Görev devirleri</h2>{table(["Kimden", "Kime", "Neden"],
 [[e(d["from_model"]), e(d["to_model"]), e(d["reason"])] for d in s["devirler"]])}</div>
</div><br>
<div class="card"><h2>Model kataloğu</h2>{table(["Model", "Seviye", "Tür", "Fiyat (giriş / çıkış, USD/1M)", "Kota"],
 [[e(m["id"]), m["tier"], e(m["kind"]), price_cell(m["id"]),
   "uygun" if j.economy.quota_ok(m["id"]) else '<span class="warn">dolu</span>'] for m in s["modeller"]])}</div><br>
<div class="card"><h2>V40 kabul durumu — doğrulanan {kb["dogrulanan"]}/{kb["toplam"]} (%{kb["yuzde"]})</h2>
<details><summary>30 kabul testi</summary>{table(["No", "Senaryo", "Durum"],
 [[t["no"], e(t["baslik"]), f'<span class="{"ok" if t["durum"] == "Doğrulandı" else "bad" if "başarısız" in t["durum"] else "warn"}">{e(t["durum"])}</span>']
  for t in kb["testler"]])}</details></div>"""
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Paneli</title><style>{CSS}</style><main>
<header><div><h1>JARVIS SUPREME <span class="mut">v{e(s["surum"])}</span></h1>
<span class="{'bad' if s['durduruldu'] else 'ok'}">{'● Durduruldu' if s['durduruldu'] else '● Çalışıyor'}</span>
 · <span class="{'ok' if llm_ok else 'warn'}">LLM: {'bağlı' if llm_ok else 'bağlı değil'} ({e(s["llm"]["model"])})</span>
</div>{stop_btn}</header>
<div class="card"><h2>Hedef ver</h2><form class="row" method="post" action="/task">
<input name="goal" placeholder="Örn: (12+8)*3 ya da özetle: ..." required>
<button class="pri">Gönder</button></form>{f'<pre>{e(report)}</pre>' if report else ''}</div><br>
<div class="grid">
<div class="card"><h2>Metrikler</h2><div class="big">{m["gorev_toplam"]} görev</div>
{table(["Gösterge", "Değer"], [["Görev başarı oranı", rate(m["gorev_basari_orani"])],
 ["Skill sayısı", m["skill_sayisi"]], ["Skill çalıştırma", m["skill_calistirma"]],
 ["Skill başarı oranı", rate(m["skill_basari_orani"])],
 ["Reddedilen işlem", m["guvenlik_olaylari"]], ["Bekleyen onay", m["bekleyen_onay"]]])}</div>
<div class="card"><h2>Bileşenler</h2>{comp}{detail}</div>
<div class="card"><h2>Onay bekleyenler</h2>{approvals}</div>
</div><br>
<div class="card"><h2>Son görevler</h2>{table(["Hedef", "Departman", "Durum", "Sonuç"],
 [[e(t["goal"][:80]), e(t["department"]), pill(t["status"]), e((t["result"] or "")[:120])]
  for t in s["gorevler"]])}</div><br>
<div class="grid">
<div class="card"><h2>Skill kataloğu</h2>{table(["Ad", "Sürüm", "Test", "Kullanım"],
 [[e(k["name"]), k["version"], e(k["test_status"]), k["uses"]] for k in s["skills"]])}</div>
<div class="card"><h2>Hafıza katmanları</h2>{table(["Katman", "Kayıt"],
 [[e(k), v] for k, v in s["hafiza"].items()])}</div>
<div class="card"><h2>Denetim kaydı</h2>{table(["Zaman", "İşlem", "Sonuç"],
 [[e(a["ts"][11:19]), e(a["action"]), e(a["outcome"])] for a in s["denetim"]])}</div>
</div>{llm_section}</main></html>"""


def make_handler(j: Jarvis):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body: str, ctype="text/html; charset=utf-8", code=200):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/api/status":
                self._send(json.dumps(j.status(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/":
                self._send(render(j))
            else:
                self._send("Bulunamadı", code=404)

        def do_POST(self):
            from urllib.parse import parse_qs
            # Başka sitelerden gelen form gönderimlerini reddet (CSRF koruması).
            origin = self.headers.get("Origin")
            if origin and origin.split("//")[-1] != self.headers.get("Host"):
                return self._send("Reddedildi", code=403)
            n = int(self.headers.get("Content-Length") or 0)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf-8")).items()}
            report = ""
            if self.path == "/task" and form.get("goal"):
                report = format_report(j.handle(form["goal"]))
            elif self.path == "/stop":
                j.security.stop()
            elif self.path == "/resume":
                j.security.resume()
            elif self.path in ("/approve", "/reject") and form.get("id", "").isdigit():
                j.security.decide(int(form["id"]), self.path == "/approve")
            else:
                return self._send("Geçersiz istek", code=400)
            self._send(render(j, report))
    return Handler


def serve(j: Jarvis, port: int = 8040) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(j))
