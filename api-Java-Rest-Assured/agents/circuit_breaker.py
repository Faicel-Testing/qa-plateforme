# ============================================================
# Circuit Breaker + Fallback — Résilience des appels LLM
# ============================================================
# Pattern disjoncteur électrique appliqué aux appels LLM.
#
# États du Circuit Breaker :
#   CLOSED    → tout passe normalement
#   OPEN      → fail fast immédiat (cooldown en cours)
#   HALF_OPEN → 1 requête test pour vérifier si le service est rétabli
#
# Fallback chain (ordre de priorité) :
#   1. Groq API     (primaire)
#   2. Ollama local (secondaire si disponible)
#   3. Cache        (réponse de la dernière requête similaire)
#   4. Default      (réponse de secours prédéfinie)
#
# Utilisé par llm.py — transparent pour tous les agents.
# ============================================================

import os, json, time, hashlib
from enum import Enum
from datetime import datetime

FRAMEWORK  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS_DIR   = os.path.join(FRAMEWORK, "logs")
CACHE_FILE = os.path.join(LOGS_DIR, "llm_cache.json")
CB_FILE    = os.path.join(LOGS_DIR, "circuit_breaker_state.json")

os.makedirs(LOGS_DIR, exist_ok=True)

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


class CBState(Enum):
    CLOSED    = "CLOSED"     # Normal — tout passe
    OPEN      = "OPEN"       # Disjoncteur ouvert — fail fast
    HALF_OPEN = "HALF_OPEN"  # Test de rétablissement


# ── Configuration ──────────────────────────────────────────────────────────

CB_CONFIG = {
    "failure_threshold":  3,      # Nb d'échecs avant ouverture
    "success_threshold":  2,      # Nb de succès en HALF_OPEN pour refermer
    "cooldown_seconds":   30,     # Durée d'attente avant HALF_OPEN
    "cache_max_entries":  200,    # Nb max d'entrées en cache
    "cache_ttl_seconds":  3600,   # TTL du cache (1h)
}


# ── Persistance de l'état ──────────────────────────────────────────────────

def _load_state() -> dict:
    if not os.path.exists(CB_FILE):
        return {
            "state":           CBState.CLOSED.value,
            "failure_count":   0,
            "success_count":   0,
            "last_failure_ts": None,
            "opened_at":       None,
            "stats": {
                "total_calls":     0,
                "groq_calls":      0,
                "ollama_calls":    0,
                "cache_hits":      0,
                "default_hits":    0,
                "circuit_opens":   0,
                "fast_fails":      0,
            }
        }
    return json.load(open(CB_FILE, encoding="utf-8"))

def _save_state(state: dict):
    with open(CB_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── Cache LLM ──────────────────────────────────────────────────────────────

def _cache_key(messages: list) -> str:
    """Hash des messages pour la clé de cache."""
    content = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _load_cache() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        return json.load(open(CACHE_FILE, encoding="utf-8"))
    except Exception:
        return {}

def _save_cache(cache: dict):
    # Limiter la taille du cache
    if len(cache) > CB_CONFIG["cache_max_entries"]:
        oldest_keys = sorted(cache, key=lambda k: cache[k].get("ts", 0))
        for k in oldest_keys[:50]:
            del cache[k]
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def cache_get(messages: list) -> str | None:
    """Retourne une réponse en cache si disponible et non expirée."""
    cache = _load_cache()
    key   = _cache_key(messages)
    entry = cache.get(key)
    if not entry:
        return None
    age = time.time() - entry.get("ts", 0)
    if age > CB_CONFIG["cache_ttl_seconds"]:
        return None
    return entry.get("response")

def cache_set(messages: list, response: str):
    """Met en cache une réponse LLM."""
    cache = _load_cache()
    key   = _cache_key(messages)
    cache[key] = {"response": response, "ts": time.time()}
    _save_cache(cache)


# ── Circuit Breaker ────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Disjoncteur pour les appels LLM.
    Usage :
        cb = CircuitBreaker()
        if cb.allow_request():
            try:
                result = call_groq(...)
                cb.record_success()
            except Exception as e:
                cb.record_failure(e)
        else:
            # fail fast → utiliser fallback
    """

    def __init__(self):
        self._state = _load_state()

    @property
    def state(self) -> CBState:
        return CBState(self._state["state"])

    def allow_request(self) -> bool:
        """True si la requête peut passer, False si fail fast."""
        s = self._state

        if s["state"] == CBState.CLOSED.value:
            return True

        if s["state"] == CBState.OPEN.value:
            # Vérifier si le cooldown est passé
            opened_at = s.get("opened_at") or 0
            elapsed   = time.time() - opened_at
            if elapsed >= CB_CONFIG["cooldown_seconds"]:
                self._transition(CBState.HALF_OPEN)
                print(f"  {Y}[CB] HALF_OPEN — test de rétablissement...{E}")
                return True
            remaining = int(CB_CONFIG["cooldown_seconds"] - elapsed)
            print(f"  {R}[CB] OPEN — fail fast (cooldown: {remaining}s restantes){E}")
            s["stats"]["fast_fails"] = s["stats"].get("fast_fails", 0) + 1
            _save_state(s)
            return False

        if s["state"] == CBState.HALF_OPEN.value:
            return True  # Laisse passer 1 requête test

        return True

    def record_success(self):
        """Enregistre un succès — peut refermer le circuit."""
        s = self._state
        s["failure_count"] = 0
        s["stats"]["total_calls"] = s["stats"].get("total_calls", 0) + 1

        if s["state"] == CBState.HALF_OPEN.value:
            s["success_count"] = s.get("success_count", 0) + 1
            if s["success_count"] >= CB_CONFIG["success_threshold"]:
                self._transition(CBState.CLOSED)
                print(f"  {G}[CB] CLOSED — service rétabli ✓{E}")
        _save_state(s)

    def record_failure(self, error: Exception = None):
        """Enregistre un échec — peut ouvrir le circuit."""
        s = self._state
        s["failure_count"]   = s.get("failure_count", 0) + 1
        s["success_count"]   = 0
        s["last_failure_ts"] = time.time()
        s["stats"]["total_calls"] = s["stats"].get("total_calls", 0) + 1

        if s["state"] == CBState.HALF_OPEN.value:
            # Échec en HALF_OPEN → ré-ouvrir immédiatement
            self._transition(CBState.OPEN)
            print(f"  {R}[CB] OPEN — rétablissement échoué, circuit ré-ouvert{E}")

        elif s["failure_count"] >= CB_CONFIG["failure_threshold"]:
            self._transition(CBState.OPEN)
            s["stats"]["circuit_opens"] = s["stats"].get("circuit_opens", 0) + 1
            print(f"  {R}[CB] OPEN — {s['failure_count']} échecs consécutifs{E}")
            if error:
                print(f"  {R}     Dernière erreur : {str(error)[:80]}{E}")

        _save_state(s)

    def _transition(self, new_state: CBState):
        s = self._state
        old = s["state"]
        s["state"] = new_state.value
        if new_state == CBState.OPEN:
            s["opened_at"]    = time.time()
            s["success_count"] = 0
        elif new_state == CBState.CLOSED:
            s["failure_count"]  = 0
            s["success_count"]  = 0
            s["opened_at"]      = None
        elif new_state == CBState.HALF_OPEN:
            s["success_count"]  = 0
        _save_state(s)

    def get_stats(self) -> dict:
        return {
            "state":         self._state["state"],
            "failure_count": self._state.get("failure_count", 0),
            "stats":         self._state.get("stats", {}),
        }

    def reset(self):
        """Réinitialise le circuit breaker (maintenance manuelle)."""
        self._transition(CBState.CLOSED)
        self._state["failure_count"] = 0
        _save_state(self._state)
        print(f"{G}  [CB] Circuit breaker réinitialisé → CLOSED{E}")


# ── Instance globale ───────────────────────────────────────────────────────

_circuit_breaker = CircuitBreaker()

def get_circuit_breaker() -> CircuitBreaker:
    return _circuit_breaker


# ── Réponse par défaut (last resort fallback) ──────────────────────────────

DEFAULT_RESPONSES = {
    "chat":             "Service LLM temporairement indisponible. Analyse manuelle requise.",
    "chat_cot":         "Service LLM temporairement indisponible. Analyse manuelle requise.",
    "chat_structured":  '{"error": "llm_unavailable", "message": "Service LLM indisponible"}',
    "chat_confident":   '{"response": "indisponible", "confidence": 0.0, "reasoning": "LLM unavailable", "needs_human_review": true}',
    "chat_adversarial": '{"verdict": "WARNING", "confidence": 0.0, "issues": ["LLM unavailable"], "summary": "Vérification impossible"}',
}

def get_default_response(fn: str) -> str:
    return DEFAULT_RESPONSES.get(fn, DEFAULT_RESPONSES["chat"])


# ── Status CLI ──────────────────────────────────────────────────────────────

def print_status():
    cb    = get_circuit_breaker()
    stats = cb.get_stats()
    state = stats["state"]
    s     = stats["stats"]

    state_color = G if state=="CLOSED" else R if state=="OPEN" else Y
    print(f"\n{W}CIRCUIT BREAKER STATUS{E}")
    print(f"  État    : {state_color}{W}{state}{E}")
    print(f"  Échecs  : {stats['failure_count']} / {CB_CONFIG['failure_threshold']} seuil")
    print(f"\n  {W}Statistiques :{E}")
    print(f"  Appels totaux   : {s.get('total_calls',0)}")
    print(f"  Appels Groq     : {s.get('groq_calls',0)}")
    print(f"  Appels Ollama   : {s.get('ollama_calls',0)}")
    print(f"  Cache hits      : {G}{s.get('cache_hits',0)}{E}")
    print(f"  Default hits    : {Y}{s.get('default_hits',0)}{E}")
    print(f"  Circuit opens   : {R}{s.get('circuit_opens',0)}{E}")
    print(f"  Fast fails      : {R}{s.get('fast_fails',0)}{E}")

    cache = _load_cache()
    print(f"\n  Cache LLM       : {len(cache)} entrées")
