# ============================================================
# Observability Agent — Traces · Circuit Breaker · Métriques
# ============================================================
# 100% déterministe — zéro appel LLM
#
# Commandes :
#   python agents/observability-agent.py traces         → appels LLM récents
#   python agents/observability-agent.py metrics        → métriques par agent
#   python agents/observability-agent.py cost           → estimation coût tokens
#   python agents/observability-agent.py circuit        → état circuit breaker
#   python agents/observability-agent.py memory         → épisodes mémoire
#   python agents/observability-agent.py prompts list   → prompts versionnés
#   python agents/observability-agent.py prompts rollback <name>
#   python agents/observability-agent.py dashboard      → rapport HTML
# ============================================================

import sys, os, json, glob, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

from prompt_store import PromptStore

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOGS_DIR  = os.path.join(FRAMEWORK, "logs")
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")
TRACES    = os.path.join(LOGS_DIR, "traces.jsonl")
CB_STATE  = os.path.join(LOGS_DIR, "circuit_breaker_state.json")
CACHE     = os.path.join(LOGS_DIR, "llm_cache.json")
MEMORY    = os.path.join(FRAMEWORK, "memory", "episodes.jsonl")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

COST_INPUT  = 0.59 / 1_000_000
COST_OUTPUT = 0.79 / 1_000_000


def load_traces(n: int = 50) -> list:
    if not os.path.exists(TRACES):
        return []
    lines = []
    with open(TRACES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except Exception:
                    pass
    return lines[-n:]


def cmd_traces(n: int = 20):
    print(f"\n{W}OBSERVABILITY — Dernières {n} traces LLM{E}\n")
    traces = load_traces(n)
    if not traces:
        print(f"  {Y}Aucune trace. Lance un agent pour générer des traces.{E}")
        return
    for t in traces[-n:]:
        ok    = t.get("success", True)
        color = G if ok else R
        fn    = t.get("fn", "?")[:25]
        dur   = t.get("durationMs", 0)
        conf  = t.get("confidence")
        conf_str = f" conf={conf:.2f}" if conf is not None else ""
        print(f"  {color}{'✓' if ok else '✗'}{E} {fn:<26} {dur:>5}ms{conf_str}")


def cmd_metrics():
    print(f"\n{W}OBSERVABILITY — Métriques par agent{E}\n")
    traces = load_traces(500)
    if not traces:
        print(f"  {Y}Aucune trace disponible.{E}")
        return
    by_agent = {}
    for t in traces:
        agent = t.get("fn", "unknown").split("_")[0]
        by_agent.setdefault(agent, {"calls":0,"errors":0,"total_ms":0,"confidences":[]})
        by_agent[agent]["calls"] += 1
        if not t.get("success", True):
            by_agent[agent]["errors"] += 1
        by_agent[agent]["total_ms"] += t.get("durationMs", 0)
        if t.get("confidence") is not None:
            by_agent[agent]["confidences"].append(t["confidence"])

    print(f"  {'Agent':<20} {'Appels':>7} {'Erreurs':>8} {'Avg ms':>8} {'Avg conf':>10}")
    print(f"  {'-'*60}")
    for agent, m in sorted(by_agent.items()):
        avg_ms   = int(m["total_ms"] / m["calls"]) if m["calls"] else 0
        avg_conf = round(sum(m["confidences"]) / len(m["confidences"]), 2) if m["confidences"] else "—"
        err_color = R if m["errors"] > 0 else G
        print(f"  {agent:<20} {m['calls']:>7} {err_color}{m['errors']:>8}{E} {avg_ms:>8} {str(avg_conf):>10}")


def cmd_cost():
    print(f"\n{W}OBSERVABILITY — Estimation coût LLM{E}")
    print(f"  Tarif Groq : ${COST_INPUT*1e6:.2f}/M tokens input · ${COST_OUTPUT*1e6:.2f}/M tokens output\n")
    traces = load_traces(1000)
    if not traces:
        print(f"  {Y}Aucune trace.{E}")
        return
    total_in  = sum(t.get("promptLen", 0) // 4 for t in traces)
    total_out = sum(t.get("responseLen", 0) // 4 for t in traces)
    cost = total_in * COST_INPUT + total_out * COST_OUTPUT
    print(f"  Appels totaux : {len(traces)}")
    print(f"  Tokens input  : ~{total_in:,}")
    print(f"  Tokens output : ~{total_out:,}")
    print(f"  Coût estimé   : {G}${cost:.4f}{E}")


def cmd_circuit():
    print(f"\n{W}OBSERVABILITY — Circuit Breaker{E}\n")
    if not os.path.exists(CB_STATE):
        print(f"  {Y}Pas d'état CB (aucun appel LLM encore).{E}")
        return
    with open(CB_STATE, encoding="utf-8") as f:
        cb = json.load(f)
    state = cb.get("state", "CLOSED")
    color = G if state == "CLOSED" else (Y if state == "HALF_OPEN" else R)
    print(f"  État : {color}{W}{state}{E}")
    print(f"  Échecs consécutifs : {cb.get('failure_count', 0)}")
    if cb.get("opened_at"):
        print(f"  Ouvert depuis : {cb['opened_at']}")
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"  Cache LLM : {len(cache)} entrées")


def cmd_memory(n: int = 10):
    print(f"\n{W}OBSERVABILITY — Mémoire épisodique (derniers {n}){E}\n")
    if not os.path.exists(MEMORY):
        print(f"  {Y}Aucun épisode en mémoire.{E}")
        return
    episodes = []
    with open(MEMORY, encoding="utf-8") as f:
        for line in f:
            try:
                episodes.append(json.loads(line.strip()))
            except Exception:
                pass
    for ep in episodes[-n:]:
        ts    = ep.get("timestamp", "?")[:16]
        agent = ep.get("agent", "?")
        summ  = ep.get("summary", "?")[:60]
        print(f"  {C}{ts}{E} [{agent}] {summ}")


def cmd_prompts(sub: str = "list", name: str = None):
    _ps = PromptStore()
    if sub == "list":
        print(f"\n{W}OBSERVABILITY — Prompts versionnés{E}\n")
        prompts = _ps.list_all()
        if not prompts:
            print(f"  {Y}Aucun prompt dans prompts/.{E}")
            return
        print(f"  {'Nom':<22} {'Version':>9} {'Appels':>8} {'Avg conf':>10} {'Desc'}")
        print(f"  {'-'*75}")
        for p in prompts:
            m = p.get("metrics", {})
            calls = m.get("calls", 0)
            conf  = f"{m['avg_confidence']:.2f}" if m.get("avg_confidence") else "—"
            print(f"  {p['name']:<22} {p['current_version']:>9} {calls:>8} {conf:>10}  {p.get('description','')[:35]}")
    elif sub == "rollback" and name:
        try:
            prev = _ps.rollback(name)
            print(f"  {G}Rollback '{name}' → v{prev}{E}")
        except Exception as ex:
            print(f"  {R}Erreur : {ex}{E}")
    elif sub == "versions" and name:
        versions = _ps.list_versions(name)
        for v in versions:
            marker = " ← current" if v.get("is_current") else ""
            print(f"  v{v['version']}  {v.get('created_at','?')[:10]}  {v.get('note','')}{marker}")


def cmd_dashboard():
    print(f"\n{W}OBSERVABILITY — Rapport HTML{E}")
    traces  = load_traces(1000)
    n_calls = len(traces)
    errors  = sum(1 for t in traces if not t.get("success", True))
    total_ms = sum(t.get("durationMs", 0) for t in traces)
    avg_ms  = int(total_ms / n_calls) if n_calls else 0

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Observability — ui_selenium_bdd</title>
<style>body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',sans-serif;padding:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;text-align:center}}
.metric{{font-size:2em;font-weight:bold;margin:8px 0}}h1{{color:#58a6ff}}</style></head>
<body><h1>📡 Observability Dashboard — ui_selenium_bdd</h1>
<p style="color:#8b949e">Généré le {time.strftime('%Y-%m-%d %H:%M')}</p>
<div class="grid">
  <div class="card"><div class="metric" style="color:#58a6ff">{n_calls}</div><div>Appels LLM totaux</div></div>
  <div class="card"><div class="metric" style="color:#e74c3c">{errors}</div><div>Erreurs</div></div>
  <div class="card"><div class="metric" style="color:#2ecc71">{avg_ms}ms</div><div>Durée moyenne</div></div>
  <div class="card"><div class="metric" style="color:#f39c12">${(n_calls * avg_ms / 1000 * 0.001):.4f}</div><div>Coût estimé</div></div>
</div></body></html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "observability-report.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}Rapport : docs/observability-report.html{E}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Observability Agent")
    parser.add_argument("command", choices=["traces","metrics","cost","circuit","memory","prompts","dashboard"])
    parser.add_argument("sub", nargs="?", default="list")
    parser.add_argument("name", nargs="?", default=None)
    parser.add_argument("-n", type=int, default=20)
    args = parser.parse_args()

    if args.command == "traces":    cmd_traces(args.n)
    elif args.command == "metrics": cmd_metrics()
    elif args.command == "cost":    cmd_cost()
    elif args.command == "circuit": cmd_circuit()
    elif args.command == "memory":  cmd_memory(args.n)
    elif args.command == "prompts": cmd_prompts(args.sub, args.name)
    elif args.command == "dashboard": cmd_dashboard()
