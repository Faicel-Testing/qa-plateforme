# ============================================================
# Observability Agent — Analyse des traces d'appels LLM
# ============================================================
# Lit logs/traces.jsonl (écrit par tracer.py via llm.py)
# et produit des métriques, détecte les anomalies, génère un
# dashboard HTML.
#
# Usage:
#   python agents/observability-agent.py metrics   → métriques par agent
#   python agents/observability-agent.py anomalies → appels lents / erreurs
#   python agents/observability-agent.py cost       → estimation coût tokens
#   python agents/observability-agent.py report     → dashboard HTML complet
#   python agents/observability-agent.py clear      → vide les traces
# ============================================================

import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import tracer

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

# Seuils d'anomalie
SLOW_MS        = 8_000   # appel > 8s = lent
VERY_SLOW_MS   = 15_000  # appel > 15s = très lent
ERROR_BURST    = 3        # 3 erreurs consécutives = burst
LOW_CONFIDENCE = 0.65     # confidence < 65% = signal faible

# Coût estimé Groq (gratuit mais on montre le modèle)
# Llama-3.3-70b : ~$0.59/M input tokens, ~$0.79/M output tokens
COST_INPUT_PER_TOKEN  = 0.59 / 1_000_000
COST_OUTPUT_PER_TOKEN = 0.79 / 1_000_000
AVG_CHARS_PER_TOKEN   = 4


# ── Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{W}{'='*60}{E}")
    print(f"{W}  {title}{E}")
    print(f"{W}{'='*60}{E}")

def duration_color(ms: float) -> str:
    if ms >= VERY_SLOW_MS: return R
    if ms >= SLOW_MS:      return Y
    return G

def bar(value: float, max_value: float, width: int = 20) -> str:
    if max_value == 0: return "░" * width
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)

def _estimate_tokens(chars: int) -> int:
    return max(1, chars // AVG_CHARS_PER_TOKEN)

def _p95(values: list) -> float:
    if not values: return 0
    s = sorted(values)
    idx = int(len(s) * 0.95)
    return s[min(idx, len(s)-1)]


# ── Métriques par agent ────────────────────────────────────────────────────

def cmd_metrics():
    print_header("MÉTRIQUES PAR AGENT — Observability")

    traces = tracer.load_traces()
    if not traces:
        print(f"{Y}  Aucune trace dans logs/traces.jsonl{E}")
        print(f"  Lance un agent d'abord, ex: python agents/triage-agent.py triage")
        return {}

    print(f"  {len(traces)} appels LLM tracés\n")

    # Grouper par agent
    by_agent = {}
    for t in traces:
        a = t.get("agent", "unknown")
        by_agent.setdefault(a, []).append(t)

    # Grouper par fonction
    by_fn = {}
    for t in traces:
        f = t.get("fn", "?")
        by_fn.setdefault(f, []).append(t)

    # ── Par agent ─────────────────────────────────────────────────────
    print(f"  {W}{'Agent':<28} {'Appels':>6} {'Succès':>7} {'Moy (ms)':>9} {'P95 (ms)':>9} {'Erreurs':>8}{E}")
    print(f"  {'-'*72}")

    max_calls = max(len(v) for v in by_agent.values()) if by_agent else 1
    agent_stats = {}

    for agent, ts in sorted(by_agent.items(), key=lambda x: -len(x[1])):
        nb       = len(ts)
        ok       = sum(1 for t in ts if t.get("success"))
        errors   = nb - ok
        durations = [t["duration_ms"] for t in ts if "duration_ms" in t]
        avg_ms   = sum(durations) / len(durations) if durations else 0
        p95_ms   = _p95(durations)
        dc       = duration_color(avg_ms)
        ec       = R if errors else G
        b        = bar(nb, max_calls, 15)

        print(f"  {C}{agent:<28}{E} {nb:>6}  {G}{ok:>6}{E}  "
              f"{dc}{avg_ms:>8.0f}{E}  {dc}{p95_ms:>8.0f}{E}  {ec}{errors:>7}{E}  {b}")

        agent_stats[agent] = {"nb": nb, "ok": ok, "errors": errors,
                               "avg_ms": avg_ms, "p95_ms": p95_ms, "durations": durations}

    # ── Par fonction LLM ──────────────────────────────────────────────
    print(f"\n  {W}{'Fonction LLM':<22} {'Appels':>6} {'Moy (ms)':>9} {'P95 (ms)':>9}{E}")
    print(f"  {'-'*50}")

    for fn, ts in sorted(by_fn.items(), key=lambda x: -len(x[1])):
        durations = [t["duration_ms"] for t in ts if "duration_ms" in t]
        avg_ms = sum(durations) / len(durations) if durations else 0
        p95_ms = _p95(durations)
        dc     = duration_color(avg_ms)
        print(f"  {Y}{fn:<22}{E} {len(ts):>6}  {dc}{avg_ms:>8.0f}{E}  {dc}{p95_ms:>8.0f}{E}")

    return {"by_agent": agent_stats, "by_fn": by_fn, "traces": traces}


# ── Détection d'anomalies ─────────────────────────────────────────────────

def cmd_anomalies():
    print_header("ANOMALIES DÉTECTÉES")

    traces = tracer.load_traces()
    if not traces:
        print(f"{Y}  Aucune trace.{E}")
        return []

    anomalies = []

    # 1. Appels lents
    for t in traces:
        ms = t.get("duration_ms", 0)
        if ms >= SLOW_MS:
            level = "TRÈS LENT" if ms >= VERY_SLOW_MS else "LENT"
            anomalies.append({
                "type":    level,
                "agent":   t.get("agent","?"),
                "fn":      t.get("fn","?"),
                "detail":  f"{ms:.0f}ms",
                "ts":      t.get("ts",""),
            })

    # 2. Erreurs consécutives (burst)
    consecutive = 0
    for t in traces:
        if not t.get("success"):
            consecutive += 1
            if consecutive >= ERROR_BURST:
                anomalies.append({
                    "type":   "ERROR BURST",
                    "agent":  t.get("agent","?"),
                    "fn":     t.get("fn","?"),
                    "detail": f"{consecutive} erreurs consécutives",
                    "ts":     t.get("ts",""),
                })
        else:
            consecutive = 0

    # 3. Retries élevés
    for t in traces:
        if t.get("retries", 0) >= 2:
            anomalies.append({
                "type":   "RETRIES",
                "agent":  t.get("agent","?"),
                "fn":     t.get("fn","?"),
                "detail": f"{t['retries']} retries",
                "ts":     t.get("ts",""),
            })

    # 4. Confidence faible récurrente (même agent > 2 fois)
    low_conf_by_agent = {}
    for t in traces:
        c = t.get("confidence")
        if c is not None and c < LOW_CONFIDENCE:
            a = t.get("agent","?")
            low_conf_by_agent[a] = low_conf_by_agent.get(a, 0) + 1
    for agent, count in low_conf_by_agent.items():
        if count >= 2:
            anomalies.append({
                "type":   "LOW CONFIDENCE",
                "agent":  agent,
                "fn":     "chat_confident",
                "detail": f"{count}× confidence < {int(LOW_CONFIDENCE*100)}%",
                "ts":     "",
            })

    if not anomalies:
        print(f"{G}  Aucune anomalie détectée — tous les agents performent bien.{E}")
        return []

    TYPE_COLOR = {
        "LENT":           Y,
        "TRÈS LENT":      R,
        "ERROR BURST":    R,
        "RETRIES":        Y,
        "LOW CONFIDENCE": Y,
    }

    for a in anomalies:
        color = TYPE_COLOR.get(a["type"], Y)
        print(f"\n  {color}{W}[{a['type']}]{E}  {C}{a['agent']}{E} → {a['fn']}")
        print(f"  {a['detail']}  {a['ts'][:19] if a['ts'] else ''}")

    print(f"\n  {R if anomalies else G}{len(anomalies)} anomalie(s) détectée(s){E}")
    return anomalies


# ── Estimation du coût tokens ─────────────────────────────────────────────

def cmd_cost():
    print_header("ESTIMATION COÛT TOKENS")

    traces = tracer.load_traces()
    if not traces:
        print(f"{Y}  Aucune trace.{E}")
        return

    total_input_tokens  = sum(_estimate_tokens(t.get("prompt_len", 0))  for t in traces)
    total_output_tokens = sum(_estimate_tokens(t.get("response_len", 0)) for t in traces)
    total_tokens        = total_input_tokens + total_output_tokens
    cost_input  = total_input_tokens  * COST_INPUT_PER_TOKEN
    cost_output = total_output_tokens * COST_OUTPUT_PER_TOKEN
    cost_total  = cost_input + cost_output

    by_agent = {}
    for t in traces:
        a = t.get("agent","?")
        ti = _estimate_tokens(t.get("prompt_len",0))
        to = _estimate_tokens(t.get("response_len",0))
        if a not in by_agent:
            by_agent[a] = {"calls": 0, "input": 0, "output": 0}
        by_agent[a]["calls"]  += 1
        by_agent[a]["input"]  += ti
        by_agent[a]["output"] += to

    print(f"\n  {W}{'Agent':<28} {'Appels':>6} {'Tokens In':>10} {'Tokens Out':>11} {'Coût ~':>10}{E}")
    print(f"  {'-'*70}")

    max_tokens = max((v["input"]+v["output"]) for v in by_agent.values()) if by_agent else 1
    for agent, d in sorted(by_agent.items(), key=lambda x: -(x[1]["input"]+x[1]["output"])):
        tot  = d["input"] + d["output"]
        cost = d["input"] * COST_INPUT_PER_TOKEN + d["output"] * COST_OUTPUT_PER_TOKEN
        b    = bar(tot, max_tokens, 12)
        print(f"  {C}{agent:<28}{E} {d['calls']:>6}  {d['input']:>9}  {d['output']:>10}  "
              f"${cost:>8.4f}  {Y}{b}{E}")

    print(f"\n  {W}Total tokens  :{E} {total_tokens:,}  "
          f"(in:{total_input_tokens:,} / out:{total_output_tokens:,})")
    print(f"  {W}Coût estimé   :{E} ${cost_total:.4f}  "
          f"{G}(Groq llama-3.3-70b){E}")
    print(f"  {C}Note : estimation basée sur ~{AVG_CHARS_PER_TOKEN} chars/token{E}")


# ── Dashboard HTML ────────────────────────────────────────────────────────

def cmd_report():
    traces = tracer.load_traces()
    if not traces:
        print(f"{Y}  Aucune trace dans logs/traces.jsonl.{E}")
        return

    # Calcul des stats
    by_agent = {}
    for t in traces:
        a = t.get("agent","?")
        by_agent.setdefault(a, []).append(t)

    by_fn = {}
    for t in traces:
        f = t.get("fn","?")
        by_fn.setdefault(f, []).append(t)

    total_calls  = len(traces)
    total_errors = sum(1 for t in traces if not t.get("success"))
    error_rate   = total_errors / total_calls * 100 if total_calls else 0
    all_durations = [t["duration_ms"] for t in traces if "duration_ms" in t]
    avg_ms   = sum(all_durations) / len(all_durations) if all_durations else 0
    p95_ms   = _p95(all_durations)
    slow_cnt = sum(1 for d in all_durations if d >= SLOW_MS)

    total_input_tokens  = sum(_estimate_tokens(t.get("prompt_len",0))  for t in traces)
    total_output_tokens = sum(_estimate_tokens(t.get("response_len",0)) for t in traces)
    cost_total = (total_input_tokens  * COST_INPUT_PER_TOKEN +
                  total_output_tokens * COST_OUTPUT_PER_TOKEN)

    # Rows agents
    agent_rows = ""
    for agent, ts in sorted(by_agent.items(), key=lambda x: -len(x[1])):
        nb  = len(ts)
        ok  = sum(1 for t in ts if t.get("success"))
        err = nb - ok
        d   = [t["duration_ms"] for t in ts if "duration_ms" in t]
        avg = sum(d)/len(d) if d else 0
        p95 = _p95(d)
        rate = ok/nb*100 if nb else 0
        bar_w = int(rate / 5)
        bar_html = f'<div style="background:#eee;border-radius:4px;height:12px;width:100px;display:inline-block"><div style="background:{"#27ae60" if rate>=90 else "#e67e22" if rate>=70 else "#e74c3c"};width:{bar_w*5}%;height:100%;border-radius:4px"></div></div>'
        cost = sum(_estimate_tokens(t.get("prompt_len",0))*COST_INPUT_PER_TOKEN +
                   _estimate_tokens(t.get("response_len",0))*COST_OUTPUT_PER_TOKEN
                   for t in ts)
        agent_rows += f"""
        <tr>
          <td><b style="color:#3498db">{agent}</b></td>
          <td style="text-align:center">{nb}</td>
          <td style="text-align:center;color:{"#27ae60" if not err else "#e74c3c"}">{ok}/{nb}</td>
          <td>{bar_html} {rate:.0f}%</td>
          <td style="color:{"#e74c3c" if avg>=SLOW_MS else "#e67e22" if avg>=SLOW_MS/2 else "#27ae60"}">{avg:.0f}ms</td>
          <td style="color:{"#e74c3c" if p95>=VERY_SLOW_MS else "#e67e22" if p95>=SLOW_MS else "#333"}">{p95:.0f}ms</td>
          <td style="font-family:monospace">${cost:.4f}</td>
        </tr>"""

    # Rows fonctions
    fn_rows = ""
    for fn, ts in sorted(by_fn.items(), key=lambda x: -len(x[1])):
        d   = [t["duration_ms"] for t in ts if "duration_ms" in t]
        avg = sum(d)/len(d) if d else 0
        p95 = _p95(d)
        fn_color = {"chat": "#3498db", "chat_cot": "#9b59b6",
                    "chat_structured": "#27ae60", "chat_confident": "#e67e22",
                    "chat_adversarial": "#e74c3c"}.get(fn, "#555")
        fn_rows += f"""
        <tr>
          <td><span style="background:{fn_color};color:#fff;padding:2px 8px;border-radius:3px;font-size:12px">{fn}</span></td>
          <td style="text-align:center">{len(ts)}</td>
          <td style="color:{"#e74c3c" if avg>=SLOW_MS else "#e67e22" if avg>=SLOW_MS/2 else "#27ae60"}">{avg:.0f}ms</td>
          <td>{p95:.0f}ms</td>
        </tr>"""

    # Timeline des 20 derniers appels
    recent = traces[-20:]
    timeline_rows = ""
    for t in reversed(recent):
        ms   = t.get("duration_ms", 0)
        ok   = t.get("success", True)
        dot  = f'<span style="color:{"#27ae60" if ok else "#e74c3c"}">{"✓" if ok else "✗"}</span>'
        d_color = "#e74c3c" if ms>=SLOW_MS else "#e67e22" if ms>=SLOW_MS/2 else "#27ae60"
        conf = f'<span style="color:{"#e74c3c" if (t.get("confidence") or 1)<LOW_CONFIDENCE else "#333"}">{t["confidence"]:.2f}</span>' if t.get("confidence") else "—"
        timeline_rows += f"""
        <tr style="font-size:12px">
          <td style="color:#888">{t.get("ts","")[:19]}</td>
          <td>{dot}</td>
          <td style="color:#3498db">{t.get("agent","?")[:20]}</td>
          <td><span style="background:#eee;padding:1px 5px;border-radius:3px">{t.get("fn","?")}</span></td>
          <td style="color:{d_color};font-family:monospace">{ms:.0f}ms</td>
          <td>{conf}</td>
          <td style="color:#e74c3c;font-size:11px">{t.get("error","")[:40] if t.get("error") else ""}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Observability — LLM Traces Dashboard</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f0f2f5;color:#333;margin:0;padding:20px}}
  h1{{color:#2c3e50}} h2{{color:#34495e;margin-top:30px}}
  .stat{{display:inline-block;background:#fff;border-radius:10px;padding:18px 28px;margin:8px;
         box-shadow:0 2px 8px rgba(0,0,0,.1);text-align:center;min-width:110px}}
  .stat-val{{font-size:30px;font-weight:bold}}
  .stat-lbl{{font-size:12px;color:#888;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;
         box-shadow:0 2px 8px rgba(0,0,0,.1);margin-top:12px}}
  th{{background:#2c3e50;color:#fff;padding:10px 12px;text-align:left;font-size:13px}}
  td{{padding:9px 12px;border-bottom:1px solid #ecf0f1}}
  tr:hover{{background:#f8f9fa}}
  .legend{{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}}
  .leg{{padding:3px 10px;border-radius:4px;color:#fff;font-size:12px}}
</style>
</head>
<body>
<h1>Observability Agent — LLM Traces Dashboard</h1>

<div>
  <div class="stat"><div class="stat-val" style="color:#3498db">{total_calls}</div><div class="stat-lbl">Appels LLM</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#e74c3c' if error_rate>5 else '#27ae60'}">{error_rate:.1f}%</div><div class="stat-lbl">Taux d'erreur</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#e74c3c' if avg_ms>=SLOW_MS else '#e67e22' if avg_ms>=3000 else '#27ae60'}">{avg_ms:.0f}ms</div><div class="stat-lbl">Durée moyenne</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#e74c3c' if p95_ms>=VERY_SLOW_MS else '#e67e22' if p95_ms>=SLOW_MS else '#27ae60'}">{p95_ms:.0f}ms</div><div class="stat-lbl">P95 durée</div></div>
  <div class="stat"><div class="stat-val" style="color:#e67e22">{slow_cnt}</div><div class="stat-lbl">Appels lents (>{SLOW_MS//1000}s)</div></div>
  <div class="stat"><div class="stat-val" style="color:#9b59b6">{total_input_tokens+total_output_tokens:,}</div><div class="stat-lbl">Tokens totaux</div></div>
  <div class="stat"><div class="stat-val" style="color:#27ae60">${cost_total:.4f}</div><div class="stat-lbl">Coût estimé</div></div>
</div>

<div class="legend">
  <span class="leg" style="background:#3498db">chat — appel simple</span>
  <span class="leg" style="background:#9b59b6">chat_cot — Chain of Thought</span>
  <span class="leg" style="background:#27ae60">chat_structured — JSON garanti</span>
  <span class="leg" style="background:#e67e22">chat_confident — Confidence Score</span>
  <span class="leg" style="background:#e74c3c">chat_adversarial — Vérification</span>
</div>

<h2>Métriques par agent</h2>
<table>
  <tr><th>Agent</th><th>Appels</th><th>Succès</th><th>Taux succès</th><th>Moy (ms)</th><th>P95 (ms)</th><th>Coût ~</th></tr>
  {agent_rows}
</table>

<h2>Métriques par fonction LLM</h2>
<table>
  <tr><th>Fonction</th><th>Appels</th><th>Moy (ms)</th><th>P95 (ms)</th></tr>
  {fn_rows}
</table>

<h2>Timeline — 20 derniers appels</h2>
<table>
  <tr><th>Timestamp</th><th></th><th>Agent</th><th>Fonction</th><th>Durée</th><th>Confidence</th><th>Erreur</th></tr>
  {timeline_rows}
</table>

<p style="color:#999;font-size:12px;margin-top:30px">
  Généré par Observability Agent | Source : logs/traces.jsonl ({total_calls} entrées)
</p>
</body>
</html>"""

    out = os.path.join(DOCS_DIR, "observability-report.html")
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print_header("OBSERVABILITY REPORT")
    print(f"  Appels tracés  : {total_calls}")
    print(f"  Erreurs        : {total_errors} ({error_rate:.1f}%)")
    print(f"  Durée moyenne  : {avg_ms:.0f}ms  |  P95 : {p95_ms:.0f}ms")
    print(f"  Appels lents   : {slow_cnt}")
    print(f"  Tokens totaux  : {total_input_tokens+total_output_tokens:,}")
    print(f"  Coût estimé    : ${cost_total:.4f}")
    print(f"\n{G}  Dashboard HTML : docs/observability-report.html{E}")


def print_help():
    print(f"""
{W}OBSERVABILITY AGENT — Traces & Métriques LLM{E}

  python agents/observability-agent.py metrics    Métriques par agent/fonction
  python agents/observability-agent.py anomalies  Appels lents, erreurs, low confidence
  python agents/observability-agent.py cost       Estimation tokens et coût
  python agents/observability-agent.py report     Dashboard HTML complet
  python agents/observability-agent.py clear      Vide logs/traces.jsonl

{W}Comment ça fonctionne :{E}
  llm.py  →  tracer.py  →  logs/traces.jsonl  →  observability-agent.py

  Chaque appel LLM (chat, chat_cot, chat_structured, chat_confident,
  chat_adversarial) est automatiquement tracé sans modifier les agents.

{W}Seuils d'anomalie :{E}
  Lent        > {SLOW_MS//1000}s  |  Très lent > {VERY_SLOW_MS//1000}s
  Low conf    < {int(LOW_CONFIDENCE*100)}%  |  Error burst ≥ {ERROR_BURST} consécutives
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "metrics":
        cmd_metrics()
    elif cmd == "anomalies":
        cmd_anomalies()
    elif cmd == "cost":
        cmd_cost()
    elif cmd == "report":
        cmd_report()
    elif cmd == "clear":
        tracer.clear_traces()
        print(f"{G}  logs/traces.jsonl vidé.{E}")
    else:
        print_help()
