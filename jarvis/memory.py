"""20 katmanlı kalıcı hafıza (V30: 1-12, V40: 13-20)."""
import json
import uuid

from .db import DB, now
from .security import Security

LAYERS = (
    "kullanici", "konusma", "gorev", "proje", "ajan", "skill", "deneyim", "hata_cozum",
    "strateji", "ortak", "anlamsal", "surum",
    # V40 ekleri
    "baglanti", "deney", "metrik", "guvenlik", "finans", "hedef", "kaynak", "meta_ogrenme",
)


class Memory:
    def __init__(self, db: DB, security: Security):
        self.db, self.sec = db, security

    def add(self, layer: str, content: str, source: str, *, task_id=None,
            verified=False, confidence=0.5, access="kullanici") -> str:
        if layer not in LAYERS:
            raise ValueError(f"Bilinmeyen hafıza katmanı: {layer}")
        if not verified and confidence > 0.7:
            confidence = 0.7  # doğrulanmamış bilgi kesin gerçek olarak saklanamaz
        self.sec.check("memory.write", layer)
        mid = uuid.uuid4().hex[:12]
        self.db.run("INSERT INTO memory VALUES(?,?,?,?,?,?,?,?,1,?)",
                    (mid, layer, content, source, now(), task_id, int(verified),
                     confidence, access))
        return mid

    def get(self, mid: str):
        return self.db.one("SELECT * FROM memory WHERE id=?", (mid,))

    def search(self, query: str, layer: str | None = None, limit: int = 10) -> list[dict]:
        """Kelime eşleşmesine dayalı arama (anlamsal vektör araması değildir)."""
        words = [w for w in query.lower().split() if len(w) > 1]
        sql, params = "SELECT * FROM memory", []
        if layer:
            sql += " WHERE layer=?"
            params.append(layer)
        rows = self.db.all(sql + " ORDER BY created DESC", params)
        scored = [(sum(w in r["content"].lower() for w in words), r) for r in rows]
        return [r for s, r in sorted(scored, key=lambda x: -x[0]) if s > 0][:limit]

    def correct(self, mid: str, content: str, *, verified: bool | None = None):
        row = self.get(mid)
        if not row:
            raise KeyError(mid)
        v = row["verified"] if verified is None else int(verified)
        self.db.run("UPDATE memory SET content=?, verified=?, version=version+1 WHERE id=?",
                    (content, v, mid))

    def delete(self, mid: str):
        self.sec.check("memory.delete", mid)  # kullanıcı onayı ister
        self.db.run("DELETE FROM memory WHERE id=?", (mid,))

    def export(self) -> str:
        self.sec.check("memory.export")
        return json.dumps(self.db.all("SELECT * FROM memory ORDER BY created"),
                          ensure_ascii=False, indent=2)

    def counts(self) -> dict:
        got = {r["layer"]: r["n"] for r in
               self.db.all("SELECT layer, COUNT(*) n FROM memory GROUP BY layer")}
        return {layer: got.get(layer, 0) for layer in LAYERS}
