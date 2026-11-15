"""Kademeli hafıza araması: metadata → tam metin → vektör → yeniden sıralama → bütçeli bağlam.

Vektörler yerel ve ücretsizdir: karakter üçlülerinin karma (hashing) vektörü. Bir sinir ağı
embedding'i değildir; yazım benzerliğini iyi, eş anlamlılığı zayıf yakalar. İçerik
değişmedikçe vektör yeniden üretilmez.
"""
import hashlib
import json
import math
import zlib

from .db import DB, now
from .providers import est_tokens

DIM = 1024


def embed(text: str) -> list[float]:
    v = [0.0] * DIM
    t = f"  {text.lower()}  "
    for i in range(len(t) - 2):
        v[zlib.crc32(t[i:i + 3].encode("utf-8")) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def cosine(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


class Retrieval:
    def __init__(self, db: DB):
        self.db = db
        self.embed_calls = 0  # yeniden embedding üretilmediğini ölçmek için

    def _vector(self, row) -> list[float]:
        h = hashlib.sha256(row["content"].encode("utf-8")).hexdigest()
        cached = self.db.one("SELECT * FROM memory_embeddings WHERE memory_id=?", (row["id"],))
        if cached and cached["content_hash"] == h:
            return json.loads(cached["vector"])
        self.embed_calls += 1
        vec = embed(row["content"])
        self.db.run("INSERT INTO memory_embeddings VALUES(?,?,?) ON CONFLICT(memory_id) DO UPDATE "
                    "SET content_hash=excluded.content_hash, vector=excluded.vector",
                    (row["id"], h, json.dumps([round(x, 5) for x in vec])))
        return vec

    def search(self, query: str, *, task_id=None, layers=None, token_budget=600,
               min_score=0.3, limit=5) -> list[dict]:
        """İlgili kayıtları döndürür ve hangi kayıtların kullanıldığını denetim için yazar."""
        # 1) metadata: katman süzgeci; düşük güvenilirlikli doğrulanmamış kayıtlar elenir
        sql, p = "SELECT * FROM memory WHERE (verified=1 OR confidence>=0.5)", []
        if layers:
            sql += f" AND layer IN ({','.join('?' * len(layers))})"
            p += list(layers)
        pool = self.db.all(sql, p)
        words = {w for w in query.lower().split() if len(w) > 2}
        qv = embed(query)
        scored = []
        for r in pool:
            low = r["content"].lower()
            text = (sum(w in low for w in words) / len(words)) if words else 0.0  # 2) tam metin
            vec = cosine(qv, self._vector(r))                                    # 3) vektör
            score = 0.5 * vec + 0.3 * text + 0.1 * r["verified"] + 0.1 * r["confidence"]  # 4)
            if max(vec, text) >= min_score:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        out, used = [], 0
        for score, r in scored[:limit]:                                          # 5) bütçe
            cost = est_tokens(r["content"])
            if used + cost > token_budget:
                continue
            used += cost
            out.append({**r, "score": round(score, 3)})
        self.db.run("INSERT INTO memory_retrievals(ts,task_id,query,memory_ids,sent_tokens,"
                    "pool_tokens) VALUES(?,?,?,?,?,?)",
                    (now(), task_id, query[:300], ",".join(r["id"] for r in out), used,
                     sum(est_tokens(r["content"]) for r in pool)))
        return out

    @staticmethod
    def context(rows) -> str:
        """6) Modele, eski bilginin doğrulanması gerektiğini açıkça bildirir."""
        return "\n".join(
            f"- [{r['id']}, {'doğrulanmış' if r['verified'] else 'DOĞRULANMAMIŞ'}, {r['layer']}] "
            f"{r['content']}" for r in rows)
