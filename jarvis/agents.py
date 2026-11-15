"""Dinamik ajan fabrikası (Bölüm 9). Ajan = sınırlı Skill listesi olan uzmanlık birimi."""
from .db import DB, now
from .security import Security
from .skills import Skills, SkillError


class Agents:
    def __init__(self, db: DB, security: Security, skills: Skills):
        self.db, self.sec, self.skills = db, security, skills

    def create(self, name: str, mission: str, expertise: str, skills: list[str],
               criteria: str) -> dict:
        missing = [s for s in skills if not self.skills.get(s)]
        if missing:
            raise SkillError(f"Ajan için eksik Skill: {', '.join(missing)}")
        if self.get(name):
            raise SkillError(f"Bu adda ajan zaten var: {name}")
        self.sec.check("agent.create", name)
        self.db.run("INSERT INTO agents VALUES(?,?,?,?,?,?,?,0,0)",
                    (name, mission, expertise, ",".join(skills), "skill", criteria, now()))
        return self.get(name)

    def get(self, name: str):
        return self.db.one("SELECT * FROM agents WHERE name=?", (name,))

    def all(self) -> list[dict]:
        return self.db.all("SELECT * FROM agents ORDER BY name")

    def run(self, name: str, skill: str, text: str) -> str:
        """Ajan yalnızca kendisine tanımlanmış Skill'leri kullanabilir (en az yetki)."""
        agent = self.get(name)
        if not agent:
            raise SkillError(f"Ajan bulunamadı: {name}")
        if skill not in agent["skills"].split(","):
            raise SkillError(f"'{name}' ajanının '{skill}' Skill'ine yetkisi yok")
        self.db.run("UPDATE agents SET runs=runs+1 WHERE name=?", (name,))
        out = self.skills.run(skill, text)
        self.db.run("UPDATE agents SET successes=successes+1 WHERE name=?", (name,))
        return out
