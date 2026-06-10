# ============================================================
# Prompt Store — Stockage et versioning des prompts LLM
# ============================================================
# Chaque prompt est stocké dans prompts/<name>.json avec :
#   - version active (current)
#   - historique complet des versions
#   - métriques collectées (calls, avg_confidence)
#
# Utilisé par les agents pour charger leurs prompts :
#   from prompt_store import PromptStore
#   store = PromptStore()
#   prompt = store.get("triage_classify")  → version active
# ============================================================

import os, json, re
from datetime import datetime

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROMPTS_DIR  = os.path.join(FRAMEWORK, "prompts")

os.makedirs(PROMPTS_DIR, exist_ok=True)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _bump(version: str, part: str = "patch") -> str:
    """Incrémente un numéro de version semver (major.minor.patch)."""
    parts = [int(x) for x in version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    if part == "major": parts[0] += 1; parts[1] = 0; parts[2] = 0
    elif part == "minor": parts[1] += 1; parts[2] = 0
    else: parts[2] += 1
    return ".".join(str(p) for p in parts)


class PromptStore:

    def __init__(self, prompts_dir: str = PROMPTS_DIR):
        self.dir = prompts_dir
        os.makedirs(self.dir, exist_ok=True)

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, f"{name}.json")

    def _load(self, name: str) -> dict | None:
        p = self._path(name)
        if not os.path.exists(p):
            return None
        return json.load(open(p, encoding="utf-8"))

    def _save(self, name: str, data: dict):
        with open(self._path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Lecture ────────────────────────────────────────────────────────

    def get(self, name: str, version: str = None) -> str | None:
        """Retourne le contenu du prompt (version active si version=None)."""
        data = self._load(name)
        if not data:
            return None
        if version is None:
            version = data["current_version"]
        for entry in data["history"]:
            if entry["version"] == version:
                return entry["content"]
        return None

    def get_meta(self, name: str) -> dict | None:
        """Retourne les métadonnées complètes du prompt."""
        return self._load(name)

    def list_all(self) -> list:
        """Liste tous les prompts disponibles avec leur version active."""
        result = []
        for f in sorted(os.listdir(self.dir)):
            if f.endswith(".json"):
                data = json.load(open(os.path.join(self.dir, f), encoding="utf-8"))
                result.append({
                    "name":            data["name"],
                    "current_version": data["current_version"],
                    "description":     data.get("description",""),
                    "agent":           data.get("agent",""),
                    "nb_versions":     len(data["history"]),
                    "metrics":         data.get("metrics", {}),
                })
        return result

    def list_versions(self, name: str) -> list:
        """Liste l'historique des versions d'un prompt."""
        data = self._load(name)
        if not data:
            return []
        current = data["current_version"]
        return [
            {**e, "is_current": e["version"] == current}
            for e in data["history"]
        ]

    # ── Création / mise à jour ─────────────────────────────────────────

    def create(self, name: str, content: str, description: str = "",
               agent: str = "", tags: list = None) -> str:
        """Crée un nouveau prompt (version 1.0.0). Erreur si déjà existant."""
        if self._load(name):
            raise ValueError(f"Prompt '{name}' existe déjà — utilise save() pour une nouvelle version.")
        version = "1.0.0"
        data = {
            "name":            name,
            "description":     description,
            "agent":           agent,
            "tags":            tags or [],
            "current_version": version,
            "metrics":         {"calls": 0, "avg_confidence": None, "last_used": None},
            "history": [{
                "version":    version,
                "content":    content,
                "created_at": _now(),
                "note":       "Version initiale",
            }]
        }
        self._save(name, data)
        return version

    def save(self, name: str, content: str, note: str = "",
             bump: str = "patch") -> str:
        """Sauvegarde une nouvelle version (auto-bump semver).
        bump = 'major' | 'minor' | 'patch'
        """
        data = self._load(name)
        if not data:
            return self.create(name, content, note)

        new_version = _bump(data["current_version"], bump)
        data["history"].append({
            "version":    new_version,
            "content":    content,
            "created_at": _now(),
            "note":       note or f"Auto-save depuis bump={bump}",
        })
        data["current_version"] = new_version
        self._save(name, data)
        return new_version

    def promote(self, name: str, version: str):
        """Définit une version existante comme version active."""
        data = self._load(name)
        if not data:
            raise ValueError(f"Prompt '{name}' introuvable.")
        versions = [e["version"] for e in data["history"]]
        if version not in versions:
            raise ValueError(f"Version {version} introuvable. Disponibles : {versions}")
        data["current_version"] = version
        self._save(name, data)

    def rollback(self, name: str) -> str:
        """Revient à la version précédente."""
        data = self._load(name)
        if not data or len(data["history"]) < 2:
            raise ValueError(f"Pas de version précédente pour '{name}'.")
        current = data["current_version"]
        history = data["history"]
        for i, e in enumerate(history):
            if e["version"] == current and i > 0:
                prev = history[i - 1]["version"]
                data["current_version"] = prev
                self._save(name, data)
                return prev
        raise ValueError("Impossible de trouver la version précédente.")

    # ── Métriques ──────────────────────────────────────────────────────

    def record_usage(self, name: str, confidence: float = None):
        """Enregistre un usage du prompt (appelé par les agents)."""
        data = self._load(name)
        if not data:
            return
        m = data.setdefault("metrics", {"calls": 0, "avg_confidence": None, "last_used": None})
        m["calls"] = m.get("calls", 0) + 1
        m["last_used"] = _now()
        if confidence is not None:
            prev = m.get("avg_confidence") or confidence
            n    = m["calls"]
            m["avg_confidence"] = round((prev * (n - 1) + confidence) / n, 3)
        self._save(name, data)
