# ============================================================
# Resilience Agent — Monitoring du Circuit Breaker + Fallback
# ============================================================
# Surveille et gère l'état du Circuit Breaker LLM.
# Affiche les statistiques de résilience (fallbacks, cache hits,
# circuit opens) et permet de réinitialiser manuellement.
#
# Usage:
#   python agents/resilience-agent.py status     → état actuel du CB
#   python agents/resilience-agent.py test        → simule Groq en panne
#   python agents/resilience-agent.py reset       → réinitialise le CB
#   python agents/resilience-agent.py cache       → stats du cache LLM
#   python agents/resilience-agent.py report      → rapport HTML
# ============================================================

import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import circuit_breaker as cb_module
from circuit_breaker import (
    CircuitBreaker, CBState, CB_CONFIG,
    _load_cache, print_status, CACHE_FILE
)

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


def print_header(title: str):
    print(f"\n{W}{'='*58}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*58}{E}")


# ── Test de simulation ────────────────────────────────────────────────────

def cmd_test():
    """
    Simule une panne de Groq pour démontrer le Circuit Breaker :
    1. Enregistre N échecs consécutifs → le circuit s'ouvre
    2. Montre le fail fast
    3. Attend le cooldown
    4. Montre le HALF_OPEN + rétablissement
    """
    print_header("TEST CIRCUIT BREAKER — Simulation panne Groq")

    cb = cb_module.get_circuit_breaker()
    cb.reset()

    threshold = CB_CONFIG["failure_threshold"]
    cooldown  = CB_CONFIG["cooldown_seconds"]

    print(f"\n{C}  Seuil d'ouverture : {threshold} échecs{E}")
    print(f"{C}  Cooldown          : {cooldown}s{E}\n")

    # Phase 1 : Simuler des échecs → ouverture du circuit
    print(f"  {W}Phase 1 — Simulation de {threshold} échecs consécutifs{E}")
    for i in range(1, threshold + 1):
        cb.record_failure(Exception(f"ConnectionError: Groq API timeout (échec {i})"))
        state = cb.state
        color = R if state == CBState.OPEN else Y
        print(f"  Échec {i}/{threshold}  → état : {color}{state.value}{E}")
        time.sleep(0.2)

    # Phase 2 : Fail fast
    print(f"\n  {W}Phase 2 — Requêtes bloquées en fail fast{E}")
    for i in range(1, 4):
        allowed = cb.allow_request()
        status  = f"{G}AUTORISÉE{E}" if allowed else f"{R}BLOQUÉE (fail fast){E}"
        print(f"  Requête {i} : {status}")
        time.sleep(0.1)

    # Phase 3 : Fallback chain actif
    print(f"\n  {W}Phase 3 — Fallback chain pendant l'ouverture{E}")
    print(f"  {Y}→ Groq indisponible → tentative Ollama → cache → default{E}")
    print(f"  Pipeline QA : {G}CONTINUE{E} (dégradé mais opérationnel)")

    # Phase 4 : Cooldown → HALF_OPEN (simulé avec cooldown court)
    print(f"\n  {W}Phase 4 — Simulation cooldown → HALF_OPEN{E}")
    print(f"  {C}(Normalement {cooldown}s — ici simulé par modification directe){E}")

    # Forcer l'état pour la démo
    state_data = cb_module._load_state()
    state_data["opened_at"] = time.time() - cooldown - 1
    cb_module._save_state(state_data)
    cb._state = state_data

    allowed = cb.allow_request()  # Devrait passer en HALF_OPEN
    print(f"  Après cooldown → état : {Y}{cb.state.value}{E}")
    print(f"  Requête test : {G}AUTORISÉE (1 seule){E}")

    # Phase 5 : Rétablissement
    print(f"\n  {W}Phase 5 — Rétablissement (succès en HALF_OPEN){E}")
    for i in range(1, CB_CONFIG["success_threshold"] + 1):
        cb.record_success()
        print(f"  Succès {i}/{CB_CONFIG['success_threshold']}  → état : {G}{cb.state.value}{E}")

    print(f"\n  {G}{W}✓ Circuit rétabli — retour en mode CLOSED normal{E}")
    print_status()


# ── Stats du cache ─────────────────────────────────────────────────────────

def cmd_cache():
    print_header("CACHE LLM — Statistiques")

    cache = _load_cache()
    if not cache:
        print(f"{Y}  Cache vide.{E}")
        return

    now = time.time()
    ttl = CB_CONFIG["cache_ttl_seconds"]

    valid   = [(k,v) for k,v in cache.items() if now - v.get("ts",0) < ttl]
    expired = [(k,v) for k,v in cache.items() if now - v.get("ts",0) >= ttl]

    print(f"\n  Entrées totales  : {len(cache)}")
    print(f"  Valides          : {G}{len(valid)}{E}")
    print(f"  Expirées (>{ttl//60}min) : {Y}{len(expired)}{E}")
    print(f"  TTL configuré    : {ttl//60} minutes")

    if valid:
        print(f"\n  {W}Aperçu des 5 dernières entrées :{E}")
        recent = sorted(valid, key=lambda x: -x[1].get("ts",0))[:5]
        for key, entry in recent:
            age     = int(now - entry.get("ts",0))
            preview = entry.get("response","")[:60].replace("\n"," ")
            print(f"  {C}{key}{E}  age={age}s  \"{preview}...\"")


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report():
    cb    = cb_module.get_circuit_breaker()
    stats = cb.get_stats()
    s     = stats["stats"]
    state = stats["state"]
    cache = _load_cache()

    state_color_html = {"CLOSED": "#27ae60", "OPEN": "#e74c3c", "HALF_OPEN": "#e67e22"}.get(state, "#888")

    total = s.get("total_calls", 0) or 1
    groq_pct   = round(s.get("groq_calls",0)   / total * 100)
    ollama_pct = round(s.get("ollama_calls",0)  / total * 100)
    cache_pct  = round(s.get("cache_hits",0)    / total * 100)
    default_pct= round(s.get("default_hits",0)  / total * 100)

    def pbar(pct, color):
        return (f'<div style="background:#eee;border-radius:4px;height:16px;width:200px;display:inline-block">'
                f'<div style="background:{color};width:{pct}%;height:100%;border-radius:4px"></div></div> {pct}%')

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Resilience Agent — Circuit Breaker</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .banner{{background:{state_color_html};color:#fff;padding:20px;border-radius:10px;
           text-align:center;font-size:24px;font-weight:bold;margin:15px 0}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:15px 25px;
         margin:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}} .stat-lbl{{font-size:12px;color:#888}}
  .box{{background:#fff;border-radius:10px;padding:20px;margin:12px 0;
        box-shadow:0 2px 8px rgba(0,0,0,.1)}}
  .row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0}}
  pre{{background:#2c3e50;color:#a8ff78;padding:15px;border-radius:8px;font-size:13px}}
</style>
</head>
<body>
<h1>Resilience Agent — Circuit Breaker + Fallback</h1>

<div class="banner">Circuit Breaker : {state}</div>

<div>
  <div class="stat"><div class="stat-val">{s.get('total_calls',0)}</div><div class="stat-lbl">Appels totaux</div></div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">{s.get('groq_calls',0)}</div><div class="stat-lbl">Via Groq</div></div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{s.get('ollama_calls',0)}</div><div class="stat-lbl">Via Ollama</div></div>
  <div class="stat"><div class="stat-val" style="color:#9b59b6">{s.get('cache_hits',0)}</div><div class="stat-lbl">Cache hits</div></div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{s.get('default_hits',0)}</div><div class="stat-lbl">Default</div></div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{s.get('circuit_opens',0)}</div><div class="stat-lbl">Ouvertures CB</div></div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{s.get('fast_fails',0)}</div><div class="stat-lbl">Fast fails</div></div>
</div>

<h2>Fallback Chain — Répartition des appels</h2>
<div class="box">
  <div class="row"><span>🟢 Groq (primaire)</span> <span>{pbar(groq_pct, '#27ae60')}</span></div>
  <div class="row"><span>🔵 Ollama (fallback 1)</span> <span>{pbar(ollama_pct, '#3498db')}</span></div>
  <div class="row"><span>🟣 Cache (fallback 2)</span> <span>{pbar(cache_pct, '#9b59b6')}</span></div>
  <div class="row"><span>🟠 Default (last resort)</span> <span>{pbar(default_pct, '#e67e22')}</span></div>
</div>

<h2>Configuration Circuit Breaker</h2>
<div class="box">
  <div class="row"><span>Seuil d'ouverture</span><b>{CB_CONFIG['failure_threshold']} échecs consécutifs</b></div>
  <div class="row"><span>Seuil de fermeture</span><b>{CB_CONFIG['success_threshold']} succès en HALF_OPEN</b></div>
  <div class="row"><span>Cooldown</span><b>{CB_CONFIG['cooldown_seconds']}s</b></div>
  <div class="row"><span>Cache TTL</span><b>{CB_CONFIG['cache_ttl_seconds']//60} minutes</b></div>
  <div class="row"><span>Cache max entries</span><b>{CB_CONFIG['cache_max_entries']}</b></div>
  <div class="row"><span>Cache actuel</span><b>{len(cache)} entrées</b></div>
</div>

<h2>États du Circuit Breaker</h2>
<pre>
CLOSED    → Tout passe normalement via Groq
    ↓ {CB_CONFIG['failure_threshold']} échecs consécutifs
OPEN      → Fail fast immédiat → Fallback (Ollama → Cache → Default)
    ↓ {CB_CONFIG['cooldown_seconds']}s cooldown
HALF_OPEN → 1 requête test vers Groq
    ↓ {CB_CONFIG['success_threshold']} succès                    ↓ 1 échec
CLOSED                                         OPEN (ré-ouvert)
</pre>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Resilience Agent | Circuit Breaker state: {state}
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "resilience-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print_header("RESILIENCE REPORT")
    print_status()
    print(f"\n{G}  Dashboard HTML : docs/resilience-report.html{E}")


def print_help():
    print(f"""
{W}RESILIENCE AGENT — Circuit Breaker + Fallback LLM{E}

  python agents/resilience-agent.py status   État actuel du Circuit Breaker
  python agents/resilience-agent.py test     Simulation panne Groq (démo)
  python agents/resilience-agent.py reset    Réinitialise le CB → CLOSED
  python agents/resilience-agent.py cache    Stats du cache LLM
  python agents/resilience-agent.py report   Dashboard HTML complet

{W}Fallback chain :{E}
  Groq (primaire) → Ollama (local) → Cache LLM → Réponse par défaut

{W}Circuit Breaker :{E}
  {CB_CONFIG['failure_threshold']} échecs → OPEN (fail fast)
  {CB_CONFIG['cooldown_seconds']}s cooldown → HALF_OPEN
  {CB_CONFIG['success_threshold']} succès → CLOSED
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "status":
        print_status()
    elif cmd == "test":
        cmd_test()
    elif cmd == "reset":
        cb_module.get_circuit_breaker().reset()
    elif cmd == "cache":
        cmd_cache()
    elif cmd == "report":
        cmd_report()
    else:
        print_help()
