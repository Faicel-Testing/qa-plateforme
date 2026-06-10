# ============================================================
# Memory Agent — Requêtes sur la mémoire épisodique
# ============================================================
# Exploite memory/episodes.jsonl pour analyser les patterns
# sur plusieurs runs d'agents.
#
# Usage:
#   python agents/memory-agent.py history TC-023   → historique d'un TC
#   python agents/memory-agent.py recurring         → TCs qui échouent souvent
#   python agents/memory-agent.py trends            → tendances par agent
#   python agents/memory-agent.py inject TC-023     → contexte à injecter dans un prompt
#   python agents/memory-agent.py seed              → génère des épisodes de démo
#   python agents/memory-agent.py report            → rapport HTML complet
# ============================================================

import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
import memory_store as mem

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"


# ── Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*60}{E}")

def trend_arrow(values: list) -> str:
    if len(values) < 2: return "→"
    delta = values[-1] - values[0]
    if delta > 0.05:  return f"{G}↑ hausse{E}"
    if delta < -0.05: return f"{R}↓ baisse{E}"
    return f"{Y}→ stable{E}"

def confidence_bar(score: float, width: int = 15) -> str:
    if score is None: return "░" * width + " —"
    filled = int(score * width)
    color  = G if score >= 0.8 else Y if score >= 0.65 else R
    return f"{color}{'█'*filled}{'░'*(width-filled)}{E} {int(score*100)}%"

def category_badge(cat: str) -> str:
    colors = {
        "real_bug":      R, "flaky": Y, "env_issue": C,
        "false_positive": G, "VALID": G, "INVALID": R,
        "WARNING": Y, "GO": G, "NO-GO": R,
    }
    return f"{colors.get(cat, Y)}{cat}{E}"


# ── Commandes ──────────────────────────────────────────────────────────────

def cmd_history(tc_id: str):
    print_header(f"HISTORIQUE ÉPISODIQUE — {tc_id.upper()}")

    history = mem.get_tc_history(tc_id, last_n=20)
    if not history:
        print(f"{Y}  Aucun historique pour {tc_id}.{E}")
        print(f"  Lance des agents d'abord ou : python agents/memory-agent.py seed")
        return

    print(f"  {len(history)} run(s) trouvé(s)\n")
    print(f"  {'Date':<12} {'Agent':<25} {'Catégorie':<15} {'Confiance'}")
    print(f"  {'-'*65}")

    confidences = []
    for h in history:
        cat  = h.get("category", h.get("verdict", "?"))
        conf = h.get("confidence")
        if conf is not None:
            confidences.append(conf)
        print(f"  {h['ts'][:10]:<12} {C}{h['agent']:<25}{E} "
              f"{category_badge(cat):<15}  {confidence_bar(conf, 10)}")

    if confidences:
        avg = sum(confidences) / len(confidences)
        print(f"\n  Confiance moyenne  : [{confidence_bar(avg)}]")
        print(f"  Tendance           : {trend_arrow(confidences)}")

    # LLM : analyse du pattern
    print(f"\n{C}  Analyse LLM du pattern historique...{E}")
    context = mem.get_context_for(tc_id)
    messages = [{
        "role": "user",
        "content": (
            f"{context}\n\n"
            f"Analyse ce pattern historique et dis :\n"
            f"1. Ce TC est-il vraiment flaky ou un vrai bug récurrent ?\n"
            f"2. Quelle action recommandes-tu (corriger, quarantaine, surveiller) ?"
        )
    }]
    analysis = llm.chat_cot(messages)
    print()
    for line in analysis.split("\n"):
        if line.strip().startswith("ÉTAPE") or line.strip().startswith("CONCLUSION"):
            print(f"  {Y}{line}{E}")
        elif line.strip():
            print(f"  {line}")


def cmd_recurring():
    print_header("TCS RÉCURRENTS — Patterns de défaillance")

    recurring = mem.get_recurring_failures(min_occurrences=2)
    if not recurring:
        print(f"{Y}  Aucun TC récurrent (minimum 2 occurrences).{E}")
        return

    # Trier par fréquence décroissante
    sorted_tcs = sorted(recurring.items(), key=lambda x: -x[1]["count"])

    print(f"  {len(sorted_tcs)} TC(s) récurrent(s) détecté(s)\n")
    print(f"  {'TC':<10} {'Runs':>5} {'Dominant':<15} {'Confiance':>12} {'Tendance'}")
    print(f"  {'-'*60}")

    flaky_candidates = []
    for tc, s in sorted_tcs:
        dom  = s["dominant_category"]
        conf = s.get("avg_confidence")
        cc   = confidence_bar(conf, 10)
        dom_color = R if dom in ("real_bug","INVALID","NO-GO") else Y

        print(f"  {C}{tc:<10}{E} {s['count']:>5}  "
              f"{dom_color}{dom:<15}{E} {cc}")

        if dom == "flaky" and s["count"] >= 3:
            flaky_candidates.append(tc)

    if flaky_candidates:
        print(f"\n  {Y}{W}Candidats à la quarantaine ({len(flaky_candidates)}) :{E}")
        for tc in flaky_candidates:
            print(f"  {Y}→ {tc} (flaky ≥3 runs){E}")


def cmd_trends():
    print_header("TENDANCES PAR AGENT")

    episodes = mem.load_all_episodes()
    if not episodes:
        print(f"{Y}  Aucun épisode en mémoire.{E}")
        return

    # Grouper par agent
    by_agent: dict = {}
    for ep in episodes:
        a = ep.get("agent","?")
        by_agent.setdefault(a, []).append(ep)

    for agent, eps in sorted(by_agent.items()):
        confs = []
        for ep in eps:
            for r in ep.get("results",[]):
                if r.get("confidence") is not None:
                    confs.append(r["confidence"])

        avg  = sum(confs)/len(confs) if confs else None
        last_runs = [ep["ts"][:10] for ep in eps[-3:]]

        print(f"\n  {C}{W}{agent}{E}")
        print(f"  {len(eps)} run(s) | {len(confs)} résultats avec confidence")
        if avg is not None:
            print(f"  Conf. moyenne : [{confidence_bar(avg)}]")
            print(f"  Tendance      : {trend_arrow(confs[-10:] if len(confs)>10 else confs)}")
        print(f"  Derniers runs : {' | '.join(last_runs)}")


def cmd_inject(tc_id: str):
    """Affiche le contexte mémoriel prêt à être injecté dans un prompt."""
    print_header(f"INJECTION DE CONTEXTE — {tc_id.upper()}")

    context = mem.get_context_for(tc_id)
    print(f"\n{Y}  ── Contexte à injecter dans le prompt ────────────{E}")
    print(f"  {context}")
    print(f"{Y}  ────────────────────────────────────────────────────{E}")
    print(f"\n{C}  Utilisation dans un agent :{E}")
    print(f'  context = mem.get_context_for("{tc_id}")')
    print(f'  messages = [{{"role":"user","content": context + "\\n\\n" + prompt}}]')


def cmd_seed():
    """
    Génère des épisodes de démonstration dans memory/episodes.jsonl.
    Simule plusieurs runs de triage-agent, rca-agent, release-advisor-agent.
    """
    print_header("SEED — Génération d'épisodes de démo")

    import random
    random.seed(42)

    episodes_data = [
        # Run 1 — il y a 7 jours
        ("triage-agent", "2026-06-03T08:00:00Z", [
            {"tc":"tc-023","name":"test_delete_without_token","category":"flaky","confidence":0.72},
            {"tc":"tc-045","name":"test_update_invalid_id","category":"real_bug","confidence":0.91},
            {"tc":"tc-012","name":"test_create_booking","category":"env_issue","confidence":0.65},
        ], "3 échecs : 1 flaky, 1 bug, 1 env"),

        # Run 2 — il y a 5 jours
        ("triage-agent", "2026-06-05T09:15:00Z", [
            {"tc":"tc-023","name":"test_delete_without_token","category":"flaky","confidence":0.68},
            {"tc":"tc-031","name":"test_patch_no_auth","category":"real_bug","confidence":0.88},
        ], "2 échecs : 1 flaky, 1 bug"),

        # Run 3 — il y a 3 jours
        ("triage-agent", "2026-06-07T10:30:00Z", [
            {"tc":"tc-023","name":"test_delete_without_token","category":"flaky","confidence":0.61},
            {"tc":"tc-045","name":"test_update_invalid_id","category":"real_bug","confidence":0.94},
            {"tc":"tc-056","name":"test_auth_expired","category":"real_bug","confidence":0.87},
        ], "3 échecs : 1 flaky, 2 bugs"),

        # Run 4 — hier
        ("triage-agent", "2026-06-09T07:45:00Z", [
            {"tc":"tc-023","name":"test_delete_without_token","category":"real_bug","confidence":0.79},
            {"tc":"tc-056","name":"test_auth_expired","category":"real_bug","confidence":0.92},
        ], "2 échecs : 2 bugs (TC-023 change de catégorie !)"),

        # RCA runs
        ("rca-agent", "2026-06-05T09:20:00Z", [
            {"tc":"tc-045","root_cause":"Token non propagé entre scénarios","confidence":0.85,
             "cause_category":"fixture","fix_priority":"high"},
        ], "RCA TC-045 : fixture scope issue"),

        ("rca-agent", "2026-06-07T10:35:00Z", [
            {"tc":"tc-045","root_cause":"Token non propagé entre scénarios","confidence":0.88,
             "cause_category":"fixture","fix_priority":"high"},
            {"tc":"tc-056","root_cause":"Token expiré après 15min de test","confidence":0.82,
             "cause_category":"config","fix_priority":"medium"},
        ], "RCA 2 TCs : fixture + token expiry"),

        # Release advisor runs
        ("release-advisor-agent", "2026-06-05T09:30:00Z", [
            {"verdict":"NO-GO","confidence":0.89,
             "reasoning":"2 tests critiques en échec sur auth"}
        ], "NO-GO — tests auth bloquants"),

        ("release-advisor-agent", "2026-06-09T08:00:00Z", [
            {"verdict":"GO","confidence":0.82,
             "reasoning":"Pass rate 92%, seul TC-023 flaky connu"}
        ], "GO — pass rate 92%"),
    ]

    for agent, ts, results, summary in episodes_data:
        ep_id = mem.record_episode(
            agent   = agent,
            results = results,
            summary = summary,
            trigger = "ci-push",
        )
        # Corriger le timestamp (normalement auto)
        episodes = mem.load_all_episodes()
        for ep in episodes:
            if ep["id"] == ep_id:
                ep["ts"] = ts
        # Réécrire
        with open(mem.EPISODES_FILE, "w", encoding="utf-8") as f:
            for ep in episodes:
                f.write(json.dumps(ep, ensure_ascii=False) + "\n")
        print(f"  {G}✓{E}  {agent:<30} {ts[:10]}  {summary[:45]}")

    print(f"\n  {G}{len(episodes_data)} épisodes générés dans memory/episodes.jsonl{E}")
    print(f"  Teste : python agents/memory-agent.py history TC-023")


# ── Rapport HTML ───────────────────────────────────────────────────────────

def cmd_report():
    episodes  = mem.load_all_episodes()
    recurring = mem.get_recurring_failures(min_occurrences=2)

    by_agent: dict = {}
    for ep in episodes:
        by_agent.setdefault(ep.get("agent","?"), []).append(ep)

    # Timeline rows
    timeline_rows = ""
    for ep in reversed(episodes[-30:]):
        nb = len(ep.get("results",[]))
        timeline_rows += f"""
        <tr style="font-size:12px">
          <td style="color:#888">{ep['ts'][:16]}</td>
          <td style="color:#3498db;font-weight:bold">{ep.get('agent','?')}</td>
          <td style="color:#888">{ep.get('trigger','?')}</td>
          <td style="text-align:center">{nb}</td>
          <td style="color:#555">{ep.get('summary','')[:60]}</td>
        </tr>"""

    # Recurring TCs rows
    recurring_rows = ""
    for tc, s in sorted(recurring.items(), key=lambda x: -x[1]["count"]):
        dom   = s["dominant_category"]
        color = {"real_bug":"#e74c3c","flaky":"#e67e22","env_issue":"#3498db"}.get(dom,"#888")
        conf  = s.get("avg_confidence")
        conf_str = f"{int(conf*100)}%" if conf else "—"
        recurring_rows += f"""
        <tr>
          <td style="font-family:monospace;font-weight:bold">{tc}</td>
          <td style="text-align:center">{s['count']}</td>
          <td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-size:12px">{dom}</span></td>
          <td style="text-align:center">{conf_str}</td>
          <td style="color:#888">{s['last_seen'][:10]}</td>
          <td style="color:#3498db">{', '.join(s['agents'][:2])}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Memory Agent — Mémoire Épisodique</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:15px 25px;
         margin:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center}}
  .stat-val{{font-size:28px;font-weight:bold}} .stat-lbl{{font-size:12px;color:#888}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
         overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:12px}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-size:12px}}
  td{{padding:9px 12px;border-bottom:1px solid #ecf0f1;vertical-align:middle}}
  tr:hover{{background:#f8f9fa}}
  .concept{{background:#fff;border-left:4px solid #3498db;padding:12px 16px;
            border-radius:0 8px 8px 0;margin:8px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
</style>
</head>
<body>
<h1>Memory Agent — Mémoire Épisodique</h1>
<p style="color:#666">Les agents se souviennent de leurs runs passés — chaque exécution enrichit la mémoire collective.</p>

<div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{len(episodes)}</div><div class="stat-lbl">Épisodes</div></div>
  <div class="stat"><div class="stat-val" style="color:#9b59b6">{len(by_agent)}</div><div class="stat-lbl">Agents actifs</div></div>
  <div class="stat"><div class="stat-val" style="color:#e74c3c">{len(recurring)}</div><div class="stat-lbl">TCs récurrents</div></div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">{sum(len(ep.get("results",[])) for ep in episodes)}</div><div class="stat-lbl">Résultats stockés</div></div>
</div>

<h2>Concept — Mémoire Épisodique</h2>
<div class="concept">
  <b>Sans mémoire</b> : chaque run repart de zéro — TC-023 classé "flaky" 5× sans jamais le savoir.<br>
  <b>Avec mémoire</b> : le prochain agent voit l'historique et donne une réponse plus précise :<br>
  <code style="background:#f0f0f0;padding:2px 6px;border-radius:3px">
    "TC-023 (4 runs) : flaky×3, real_bug×1 | Conf. moy : 0.70 | Tendance : ↓ baisse"
  </code>
</div>

<h2>TCs récurrents (≥2 occurrences)</h2>
<table>
  <tr><th>TC</th><th>Occurrences</th><th>Catégorie dominante</th><th>Conf. moy.</th><th>Dernier run</th><th>Agents</th></tr>
  {recurring_rows or '<tr><td colspan="6" style="text-align:center;color:#888">Aucun TC récurrent</td></tr>'}
</table>

<h2>Timeline des épisodes (30 derniers)</h2>
<table>
  <tr><th>Timestamp</th><th>Agent</th><th>Trigger</th><th>Résultats</th><th>Résumé</th></tr>
  {timeline_rows or '<tr><td colspan="5" style="text-align:center;color:#888">Aucun épisode</td></tr>'}
</table>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Memory Agent | Source : memory/episodes.jsonl ({len(episodes)} épisodes)
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "memory-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print_header("MEMORY REPORT")
    print(f"  {len(episodes)} épisodes | {len(recurring)} TCs récurrents")
    print(f"{G}  Dashboard HTML : docs/memory-report.html{E}")


def print_help():
    print(f"""
{W}MEMORY AGENT — Mémoire Épisodique des agents{E}

  python agents/memory-agent.py seed              Génère des épisodes de démo
  python agents/memory-agent.py history TC-023    Historique d'un TC + analyse LLM
  python agents/memory-agent.py recurring         TCs qui échouent souvent
  python agents/memory-agent.py trends            Tendances de confiance par agent
  python agents/memory-agent.py inject TC-023     Contexte prêt pour injection prompt
  python agents/memory-agent.py report            Dashboard HTML

{W}Mémoire épisodique — valeur :{E}
  Sans : chaque run repart de zéro
  Avec : l'agent voit que TC-023 est flaky depuis 5 runs
         → décision plus précise, tendance de confiance, quarantaine suggérée

{W}Intégration dans un agent :{E}
  from memory_store import get_context_for, record_episode
  context = get_context_for("tc-023")   # injecte dans le prompt
  record_episode("mon-agent", results)  # enregistre après le run
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "seed":
        cmd_seed()
    elif cmd == "history" and arg:
        cmd_history(arg)
    elif cmd == "recurring":
        cmd_recurring()
    elif cmd == "trends":
        cmd_trends()
    elif cmd == "inject" and arg:
        cmd_inject(arg)
    elif cmd == "report":
        cmd_report()
    else:
        print_help()
