# ============================================================
# Observability Agent — Traces · Circuit Breaker · Mémoire · Prompts
# ============================================================
# Absorbe : observability-agent (ancien) · resilience-agent · memory-agent · prompt-versioning-agent
#
# Commandes :
#   python agents/observability-agent.py traces          → analyse des traces LLM
#   python agents/observability-agent.py traces anomalies → détecte les appels lents/erreurs
#   python agents/observability-agent.py circuit         → état du circuit breaker
#   python agents/observability-agent.py circuit reset   → reset du circuit breaker
#   python agents/observability-agent.py memory stats    → stats de la mémoire épisodique
#   python agents/observability-agent.py memory history TC-023 → historique d'un TC
#   python agents/observability-agent.py prompts list    → liste des prompts versionnés
#   python agents/observability-agent.py prompts show P  → détails d'un prompt
#   python agents/observability-agent.py dashboard       → dashboard HTML complet
# ============================================================

import sys, os, json, glob, re, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

try:
    import circuit_breaker as _cb
except ImportError:
    _cb = None
try:
    import memory_store as _mem
except ImportError:
    _mem = None
try:
    import prompt_store as _ps
except ImportError:
    _ps = None

FRAMEWORK   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRACES_FILE = os.path.join(FRAMEWORK, "logs", "traces.jsonl")
MEMORY_FILE = os.path.join(FRAMEWORK, "memory", "episodes.jsonl")
CB_STATE    = os.path.join(FRAMEWORK, "logs", "circuit_breaker_state.json")
DOCS_DIR    = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


# ── Traces — Analyse des appels LLM ───────────────────────────────────────

def load_traces(limit: int = 200) -> list:
    if not os.path.exists(TRACES_FILE):
        return []
    traces = []
    with open(TRACES_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                traces.append(json.loads(line.strip()))
            except Exception:
                pass
    return traces[-limit:]


def cmd_traces(mode: str = "summary"):
    print(f"\n{W}OBSERVABILITY AGENT — LLM Traces [{mode}]{E}\n")
    traces = load_traces()

    if not traces:
        print(f"{Y}  Aucune trace dans logs/traces.jsonl.{E}")
        return {}

    total     = len(traces)
    errors    = sum(1 for t in traces if t.get("error"))
    durations = [t.get("duration_ms", 0) for t in traces if t.get("duration_ms")]
    avg_dur   = round(sum(durations) / len(durations)) if durations else 0
    tokens    = sum(t.get("tokens", 0) for t in traces)
    cost_est  = round(tokens * 0.00059 / 1000, 4)
    fn_counts = {}
    for t in traces:
        fn = t.get("fn", "unknown")
        fn_counts[fn] = fn_counts.get(fn, 0) + 1

    print(f"  Total appels  : {total}")
    print(f"  Erreurs       : {R if errors else G}{errors}{E}")
    print(f"  Duree moyenne : {avg_dur}ms")
    print(f"  Tokens totaux : {tokens}")
    print(f"  Cout estime   : ~${cost_est}")
    print(f"\n  Par fonction :")
    for fn, count in sorted(fn_counts.items(), key=lambda x: -x[1]):
        print(f"    {C}{fn:<25}{E} {count}")

    if mode in ("anomalies", "all"):
        slow   = [t for t in traces if t.get("duration_ms", 0) > 10000]
        errors_list = [t for t in traces if t.get("error")]
        if slow:
            print(f"\n{Y}  Appels lents (> 10s) : {len(slow)}{E}")
            for t in slow[-3:]:
                print(f"  {Y}!{E} {t.get('fn','?')} — {t.get('duration_ms',0)}ms")
        if errors_list:
            print(f"\n{R}  Erreurs ({len(errors_list)}) :{E}")
            for t in errors_list[-3:]:
                print(f"  {R}x{E} {t.get('fn','?')} — {t.get('error','')[:80]}")

    if mode == "analyze":
        fn_summary = "\n".join([f"  {fn}: {count}" for fn, count in fn_counts.items()])
        messages = [{"role": "user", "content": (
            f"Analyse ces metriques LLM et propose 3 optimisations :\n\n"
            f"Total: {total} | Erreurs: {errors} | Duree moy: {avg_dur}ms | Cout: ${cost_est}\n\n"
            f"Distribution:\n{fn_summary}"
        )}]
        analysis = llm.chat(messages)
        print(f"\n{W}  Analyse :{E}")
        for line in analysis.strip().split("\n"):
            print(f"  {line}")

    return {"total": total, "errors": errors, "avg_duration_ms": avg_dur, "cost_est": cost_est}


# ── Circuit Breaker ────────────────────────────────────────────────────────

def cmd_circuit(action: str = "status"):
    print(f"\n{W}OBSERVABILITY AGENT — Circuit Breaker [{action}]{E}\n")

    if not _cb:
        print(f"{Y}  Module circuit_breaker non disponible.{E}")
        return

    if action == "reset":
        try:
            cb = _cb.get_circuit_breaker()
            cb._state["state"] = "CLOSED"
            cb._state["failure_count"] = 0
            cb._state["last_failure_time"] = None
            _cb._save_state(cb._state)
            print(f"  {G}Circuit Breaker reinitialise -> CLOSED{E}")
        except Exception as e:
            print(f"  {R}Erreur reset : {e}{E}")
        return

    try:
        cb    = _cb.get_circuit_breaker()
        state = cb._state.get("state", "UNKNOWN")
        stats = cb._state.get("stats", {})
        state_color = G if state == "CLOSED" else R if state == "OPEN" else Y

        print(f"  Etat         : {state_color}{W}{state}{E}")
        print(f"  Failures     : {cb._state.get('failure_count', 0)}")
        print(f"  Seuil        : {cb._state.get('failure_threshold', 3)}")
        print(f"  Last failure : {cb._state.get('last_failure_time', 'N/A')}")
        print(f"\n  Stats :")
        for key, val in stats.items():
            print(f"    {C}{key:<22}{E} {val}")

        if state == "OPEN":
            print(f"\n{R}  [WARN] Circuit OUVERT — appels LLM bloqués.{E}")
            print(f"  Lancez : python agents/observability-agent.py circuit reset")
        elif state == "HALF_OPEN":
            print(f"\n{Y}  [INFO] Circuit HALF_OPEN — recuperation en cours.{E}")
    except Exception as e:
        print(f"  {R}Erreur lecture : {e}{E}")


# ── Memory — Mémoire épisodique ────────────────────────────────────────────

def load_episodes() -> list:
    if not os.path.exists(MEMORY_FILE):
        return []
    episodes = []
    with open(MEMORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                episodes.append(json.loads(line.strip()))
            except Exception:
                pass
    return episodes


def cmd_memory(action: str = "stats", query: str = None):
    print(f"\n{W}OBSERVABILITY AGENT — Episodic Memory [{action}]{E}\n")
    episodes = load_episodes()

    if not episodes:
        print(f"{Y}  Aucun episode dans memory/episodes.jsonl.{E}")
        return

    if action == "stats":
        agents = {}
        for ep in episodes:
            agent = ep.get("agent", "unknown")
            agents[agent] = agents.get(agent, 0) + 1

        print(f"  Total episodes : {len(episodes)}")
        print(f"\n  Par agent :")
        for agent, count in sorted(agents.items(), key=lambda x: -x[1]):
            print(f"    {C}{agent:<25}{E} {count}")

        print(f"\n  5 derniers episodes :")
        for ep in episodes[-5:]:
            ts    = ep.get("ts", "?")[:19]
            agent = ep.get("agent", "?")
            summ  = ep.get("summary", "")[:60]
            print(f"    {Y}{ts}{E}  {C}{agent:<20}{E}  {summ}")

    elif action == "history" and query:
        matches = [ep for ep in episodes if query.lower() in str(ep).lower()]
        if not matches:
            print(f"{Y}  Aucun episode pour '{query}'.{E}")
            return
        print(f"  {len(matches)} episode(s) pour '{query}' :\n")
        for ep in matches[-10:]:
            ts   = ep.get("ts", "?")[:19]
            agent = ep.get("agent", "?")
            summ  = ep.get("summary", "")[:80]
            print(f"  {Y}{ts}{E}  {C}{agent:<20}{E}  {summ}")

    elif action == "clear":
        open(MEMORY_FILE, "w").close()
        print(f"  {G}Memoire effacee.{E}")


# ── Prompts — Versioning ────────────────────────────────────────────────────

def cmd_prompts(action: str = "list", prompt_name: str = None):
    print(f"\n{W}OBSERVABILITY AGENT — Prompt Versioning [{action}]{E}\n")
    prompts_dir = os.path.join(FRAMEWORK, "prompts")

    if action == "list":
        if not os.path.exists(prompts_dir):
            print(f"{Y}  Aucun dossier prompts/.{E}")
            return
        files = [f for f in os.listdir(prompts_dir) if f.endswith(".json")]
        if not files:
            print(f"{Y}  Aucun prompt versionne.{E}")
            return
        print(f"  {len(files)} prompt(s) :")
        for fname in sorted(files):
            name = os.path.splitext(fname)[0]
            fpath = os.path.join(prompts_dir, fname)
            try:
                data    = json.load(open(fpath, encoding="utf-8"))
                version = data.get("current_version", "?")
                calls   = data.get("metrics", {}).get("calls", 0)
                print(f"    {C}{name:<30}{E} v{version}  {calls} appels")
            except Exception:
                print(f"    {C}{name}{E}")

    elif action == "show" and prompt_name:
        fpath = os.path.join(prompts_dir, f"{prompt_name}.json")
        if not os.path.exists(fpath):
            print(f"{R}  Prompt '{prompt_name}' introuvable.{E}")
            return
        data = json.load(open(fpath, encoding="utf-8"))
        print(f"  Nom     : {prompt_name}")
        print(f"  Version : {data.get('current_version','?')}")
        print(f"  Appels  : {data.get('metrics',{}).get('calls',0)}")
        history = data.get("history", [])
        if history:
            print(f"\n  Historique ({len(history)} versions) :")
            for h in history[-3:]:
                print(f"    v{h.get('version','?')}  {h.get('timestamp','?')[:19]}")


# ── Dashboard HTML ─────────────────────────────────────────────────────────

def cmd_dashboard():
    print(f"\n{W}OBSERVABILITY AGENT — Dashboard HTML{E}")
    traces   = load_traces()
    episodes = load_episodes()

    total    = len(traces)
    errors   = sum(1 for t in traces if t.get("error"))
    durations = [t.get("duration_ms", 0) for t in traces if t.get("duration_ms")]
    avg_dur  = round(sum(durations) / len(durations)) if durations else 0
    tokens   = sum(t.get("tokens", 0) for t in traces)
    cost     = round(tokens * 0.00059 / 1000, 4)

    fn_counts = {}
    for t in traces:
        fn = t.get("fn", "unknown")
        fn_counts[fn] = fn_counts.get(fn, 0) + 1
    fn_rows = "".join(
        f"<tr><td>{fn}</td><td style='text-align:right'>{c}</td></tr>"
        for fn, c in sorted(fn_counts.items(), key=lambda x: -x[1])
    )

    cb_state = "N/A"; cb_failures = 0
    if os.path.exists(CB_STATE):
        try:
            cb_data     = json.load(open(CB_STATE, encoding="utf-8"))
            cb_state    = cb_data.get("state", "UNKNOWN")
            cb_failures = cb_data.get("failure_count", 0)
        except Exception:
            pass
    cb_color = {"CLOSED": "#27ae60", "OPEN": "#e74c3c", "HALF_OPEN": "#e67e22"}.get(cb_state, "#95a5a6")

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Observability Dashboard</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f5f5f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:25px}}
  .stat{{display:inline-block;background:#fff;border-radius:8px;padding:18px 28px;margin:8px;
         box-shadow:0 2px 6px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:32px;font-weight:bold}}
  .cb{{display:inline-block;padding:8px 18px;border-radius:6px;color:#fff;font-weight:bold;background:{cb_color}}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;
         box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:10px}}
  th{{background:#2c3e50;color:#fff;padding:9px 12px;text-align:left}}
  td{{padding:8px 12px;border-bottom:1px solid #ecf0f1}}
</style>
</head>
<body>
<h1>Observability Dashboard</h1>
<div>
  <div class="stat"><div class="stat-val" style="color:#2c3e50">{total}</div>Appels LLM</div>
  <div class="stat"><div class="stat-val" style="color:{'#e74c3c' if errors else '#27ae60'}">{errors}</div>Erreurs</div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{avg_dur}ms</div>Durée moy</div>
  <div class="stat"><div class="stat-val" style="color:#9b59b6">{tokens}</div>Tokens</div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">${cost}</div>Coût</div>
  <div class="stat"><div class="stat-val" style="color:#2c3e50">{len(episodes)}</div>Épisodes</div>
</div>
<h2>Distribution LLM</h2>
<table><tr><th>Fonction</th><th>Appels</th></tr>{fn_rows}</table>
<h2>Circuit Breaker</h2>
<div class="cb">{cb_state}</div>
<span style="margin-left:12px;color:#666">Failures: {cb_failures}</span>
<p style="color:#999;font-size:12px;margin-top:30px">Généré par Observability Agent</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "observability-dashboard.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  {G}Dashboard : docs/observability-dashboard.html{E}")


# ── Main ───────────────────────────────────────────────────────────────────

def print_help():
    print(f"""
{W}OBSERVABILITY AGENT — Traces · Circuit Breaker · Mémoire · Prompts{E}

  python agents/observability-agent.py traces             Resume des traces LLM
  python agents/observability-agent.py traces anomalies   Appels lents / erreurs
  python agents/observability-agent.py traces analyze     Analyse LLM + recommandations
  python agents/observability-agent.py circuit            Etat du circuit breaker
  python agents/observability-agent.py circuit reset      Remet le circuit a CLOSED
  python agents/observability-agent.py memory stats       Stats memoire episodique
  python agents/observability-agent.py memory history TC  Historique d'un TC / agent
  python agents/observability-agent.py memory clear       Efface la memoire
  python agents/observability-agent.py prompts list       Prompts versionnes
  python agents/observability-agent.py prompts show NOM   Details d'un prompt
  python agents/observability-agent.py dashboard          Dashboard HTML complet

{W}Modules absorbes :{E} observability-agent (old) · resilience-agent · memory-agent · prompt-versioning-agent
""")


if __name__ == "__main__":
    cmd   = sys.argv[1] if len(sys.argv) > 1 else "help"
    sub   = sys.argv[2] if len(sys.argv) > 2 else None
    param = sys.argv[3] if len(sys.argv) > 3 else None

    if cmd == "traces":
        cmd_traces(sub or "summary")
    elif cmd == "circuit":
        cmd_circuit(sub or "status")
    elif cmd == "memory":
        cmd_memory(sub or "stats", param)
    elif cmd == "prompts":
        cmd_prompts(sub or "list", param)
    elif cmd == "dashboard":
        cmd_dashboard()
    else:
        print_help()
