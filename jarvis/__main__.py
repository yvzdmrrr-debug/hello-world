"""Komut satırı: `python -m jarvis` (sohbet) ya da `python -m jarvis panel`."""
import json
import sys

from . import VERSION
from .core import Jarvis, format_report
from .llm import LLMUnavailable
from .security import ApprovalRequired, Denied, Stopped
from .skills import SkillError

HELP = """Komutlar:
  <hedef>               Hedef ver (örn: (12+8)*3  |  özetle: <metin>  |  serbest soru)
  durum                 Sistem durumu ve metrikler
  skills                Skill kataloğu
  skill-uret <ihtiyaç>  Yeni Skill üret, test et, kur (LLM gerekir)
  hatirla <metin>       Kullanıcı hafızasına kaydet
  ara <kelime>          Hafızada ara
  disa-aktar            Hafızayı JSON olarak yazdır
  sil <kayıt-no>        Hafıza kaydını sil (onay ister)
  onaylar               Bekleyen onaylar
  onay <no> | red <no>  Onayla / reddet
  dur | devam           Sistemi durdur / devam ettir
  yardim | cik"""


def command(j: Jarvis, line: str) -> str:
    cmd, _, arg = line.strip().partition(" ")
    arg = arg.strip()
    if cmd in ("yardim", "yardım", "help"):
        return HELP
    if cmd == "durum":
        s = j.status()
        b = s["bilesenler"]
        rows = [f"JARVIS SUPREME v{s['surum']} — {'DURDURULDU' if s['durduruldu'] else 'çalışıyor'}",
                f"LLM: {'bağlı' if s['llm']['bagli'] else 'bağlı değil'} ({s['llm']['model']})"]
        for label, key in (("Departman", "departman"), ("Bilişsel sistem", "bilissel"),
                           ("Evrim motoru", "motor")):
            rows.append(f"{label}: {b[key]['toplam']} (kodla çalışan {b[key]['KOD']}, "
                        f"LLM ile {b[key]['LLM']}, planlanan {b[key]['PLAN']})")
        rows.append("Metrikler: " + json.dumps(s["metrikler"], ensure_ascii=False))
        return "\n".join(rows)
    if cmd == "skills":
        return "\n".join(f"{k['name']} v{k['version']} — {k['description']} "
                         f"[{k['test_status']}, {k['uses']} kullanım]"
                         for k in j.skills.catalog()) or "Skill yok."
    if cmd == "skill-uret" and arg:
        r = j.evolve_skill(arg)
        if r["ok"]:
            return f"'{r['name']}' v{r['version']} kuruldu; {len(r['results'])} test geçti."
        return (f"'{r['name']}' kurulmadı. Bulgular: {r['issues']}. Başarısız testler: "
                f"{[t for t in r['results'] if not t['ok']]}")
    if cmd == "hatirla" and arg:
        return "Kaydedildi: " + j.memory.add("kullanici", arg, "kullanici", verified=True,
                                             confidence=1.0)
    if cmd == "ara" and arg:
        return "\n".join(f"[{m['id']}] ({m['layer']}) {m['content'][:200]}"
                         for m in j.memory.search(arg)) or "Sonuç yok."
    if cmd == "disa-aktar":
        return j.memory.export()
    if cmd == "sil" and arg:
        j.memory.delete(arg)
        return "Silindi."
    if cmd == "onaylar":
        return "\n".join(f"{a['id']}: {a['action']} — {a['detail']}"
                         for a in j.security.pending()) or "Bekleyen onay yok."
    if cmd in ("onay", "red") and arg.isdigit():
        ok = j.security.decide(int(arg), cmd == "onay")
        return ("Onaylandı; işlemi yeniden çalıştırın." if cmd == "onay" else "Reddedildi.") \
            if ok else "Böyle bekleyen bir onay yok."
    if cmd == "dur":
        j.security.stop()
        return "Sistem durduruldu."
    if cmd == "devam":
        j.security.resume()
        return "Sistem devam ediyor."
    return format_report(j.handle(line))


def safe(j: Jarvis, line: str) -> str:
    try:
        return command(j, line)
    except (ApprovalRequired, Denied, Stopped, SkillError, LLMUnavailable, KeyError) as e:
        return f"Yapılamadı: {e}"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    j = Jarvis(".")
    if argv and argv[0] == "panel":
        from .dashboard import serve
        port = int(argv[1]) if len(argv) > 1 else 8040
        print(f"Panel: http://127.0.0.1:{port}  (durdurmak için Ctrl+C)")
        try:
            serve(j, port).serve_forever()
        except KeyboardInterrupt:
            print()
        return
    if argv:
        print(safe(j, " ".join(argv)))
        return
    print(f"JARVIS SUPREME v{VERSION} — 'yardim' yazın, çıkmak için 'cik'.")
    while True:
        try:
            line = input("siz> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line in ("cik", "çık", "exit", "quit"):
            break
        if line:
            print(safe(j, line))


if __name__ == "__main__":
    main()
