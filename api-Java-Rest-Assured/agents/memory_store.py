# ============================================================
# Memory Store — Mémoire épisodique des agents
# ============================================================
# Stocke chaque run d'agent comme un "épisode" dans
# memory/episodes.jsonl (format JSON Lines).
#
# Un épisode = une exécution d'agent avec ses résultats :
#   id, ts, agent, trigger, results[], summary, metrics
#
# Utilisé par les agents pour :
#   1. Enregistrer leurs résultats (record_episode)
#   2. Récupérer l'historique d'un TC (get_tc_history)
#   3. Injecter le contexte passé dans leurs prompts (get_context_for)
# ============================================================

import os, json, re, hashlib
from datetime import datetime

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MEMORY_DIR   = os.path.join(FRAMEWORK, "memory")
EPISODES_FILE = os.path.join(MEMORY_DIR, "episodes.jsonl")

os.makedirs(MEMORY_DIR, exist_ok=True)


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _ep_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"ep_{ts}"


# ── Lecture / Écriture ────────────────────────────────────────────────────

def record_episode(
    agent:    str,
    results:  list,
    summary:  str = "",
    trigger:  str = "manual",
    metrics:  dict = None,
) -> str:
    """
    Enregistre un épisode dans memory/episodes.jsonl.
    Retourne l'ID de l'épisode créé.

    results : liste de dicts libres, ex:
      [{"tc": "tc-023", "category": "flaky", "confidence": 0.72}, ...]
    """
    ep = {
        "id":      _ep_id(),
        "ts":      _now(),
        "agent":   agent,
        "trigger": trigger,
        "results": results,
        "summary": summary,
        "metrics": metrics or {},
    }
    with open(EPISODES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(ep, ensure_ascii=False) + "\n")
    return ep["id"]


def load_all_episodes(agent: str = None, limit: int = None) -> list:
    """Charge tous les épisodes, optionnellement filtrés par agent."""
    if not os.path.exists(EPISODES_FILE):
        return []
    episodes = []
    with open(EPISODES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ep = json.loads(line)
                if agent is None or ep.get("agent") == agent:
                    episodes.append(ep)
            except json.JSONDecodeError:
                pass
    if limit:
        episodes = episodes[-limit:]
    return episodes


# ── Requêtes orientées TC ─────────────────────────────────────────────────

def get_tc_history(tc_id: str, last_n: int = 10) -> list:
    """
    Retourne l'historique d'un TC spécifique sur les N derniers épisodes.
    Retourne une liste de {ts, agent, category, confidence, ...}
    """
    tc_lower  = tc_id.lower()
    episodes  = load_all_episodes()
    history   = []

    for ep in episodes:
        for result in ep.get("results", []):
            if result.get("tc","").lower() == tc_lower:
                history.append({
                    "ts":         ep["ts"],
                    "episode_id": ep["id"],
                    "agent":      ep["agent"],
                    **result,
                })

    return history[-last_n:]


def get_recurring_failures(min_occurrences: int = 3) -> dict:
    """
    Identifie les TCs qui échouent au moins min_occurrences fois.
    Retourne {tc_id: {count, categories, avg_confidence, last_seen}}
    """
    episodes = load_all_episodes()
    tc_stats: dict = {}

    for ep in episodes:
        for r in ep.get("results", []):
            tc = r.get("tc")
            if not tc:
                continue
            if tc not in tc_stats:
                tc_stats[tc] = {
                    "count":          0,
                    "categories":     {},
                    "confidences":    [],
                    "last_seen":      ep["ts"],
                    "agents":         set(),
                }
            s = tc_stats[tc]
            s["count"] += 1
            s["last_seen"] = ep["ts"]
            s["agents"].add(ep["agent"])
            cat = r.get("category", r.get("verdict", "unknown"))
            s["categories"][cat] = s["categories"].get(cat, 0) + 1
            if r.get("confidence") is not None:
                s["confidences"].append(r["confidence"])

    # Calculer avg_confidence et filtrer
    recurring = {}
    for tc, s in tc_stats.items():
        if s["count"] >= min_occurrences:
            s["avg_confidence"] = (
                round(sum(s["confidences"]) / len(s["confidences"]), 3)
                if s["confidences"] else None
            )
            s["dominant_category"] = max(s["categories"], key=s["categories"].get)
            s["agents"] = list(s["agents"])
            recurring[tc] = s

    return recurring


# ── Injection de contexte (Context Engineering) ───────────────────────────

def get_context_for(tc_id: str, agent: str = None) -> str:
    """
    Retourne un résumé textuel de l'historique d'un TC,
    prêt à être injecté dans un prompt LLM.

    Exemple de sortie :
      "Historique TC-023 (5 runs) : flaky×3, real_bug×2
       Confiance moyenne : 0.74 | Tendance : baissière
       Dernier run (2026-06-09) : flaky via triage-agent"
    """
    history = get_tc_history(tc_id)
    if not history:
        return f"Aucun historique pour {tc_id}."

    categories = {}
    confidences = []
    for h in history:
        cat = h.get("category", h.get("verdict", "unknown"))
        categories[cat] = categories.get(cat, 0) + 1
        if h.get("confidence") is not None:
            confidences.append(h["confidence"])

    dominant  = max(categories, key=categories.get)
    cat_str   = ", ".join([f"{c}×{n}" for c, n in sorted(categories.items(), key=lambda x: -x[1])])
    avg_conf  = round(sum(confidences)/len(confidences), 2) if confidences else None
    last      = history[-1]

    # Tendance de confiance (hausse/baisse sur les 3 derniers)
    trend = ""
    if len(confidences) >= 3:
        recent = confidences[-3:]
        if recent[-1] > recent[0]:
            trend = "↑ hausse"
        elif recent[-1] < recent[0]:
            trend = "↓ baisse"
        else:
            trend = "→ stable"

    lines = [
        f"Historique {tc_id} ({len(history)} runs) : {cat_str}",
    ]
    if avg_conf is not None:
        lines.append(f"Confiance moyenne : {avg_conf}{(' | Tendance : ' + trend) if trend else ''}")
    lines.append(
        f"Dernier run ({last['ts'][:10]}) : {last.get('category', last.get('verdict','?'))} "
        f"via {last['agent']}"
    )
    return "\n".join(lines)


def get_agent_summary(agent: str, last_n: int = 5) -> str:
    """Résumé des N derniers runs d'un agent — pour injection dans son prochain run."""
    episodes = load_all_episodes(agent=agent, limit=last_n)
    if not episodes:
        return f"Aucun historique pour {agent}."

    lines = [f"Derniers {len(episodes)} runs de {agent} :"]
    for ep in reversed(episodes):
        nb = len(ep.get("results", []))
        lines.append(f"  {ep['ts'][:10]} — {ep.get('summary', f'{nb} résultats')}")
    return "\n".join(lines)
