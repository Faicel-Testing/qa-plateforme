# Agents IA — ui_selenium_bdd

Framework : **Selenium 4 + Cucumber 7 + TestNG 7.9 + Java 17 + Maven**  
Application : **automationexercise.com** — 26 cas de test  
Agents : **Python** (appellent Maven via subprocess, lisent les résultats Allure JSON)

---

## Architecture — 10 agents

```
pipeline-agent.py          ← Orchestrateur maître
├── runner-agent.py        ← Exécution Maven + détection flaky
├── codegen-agent.py       ← Génération Java (feature, steps, page objects)
├── bug-agent.py           ← Triage, RCA, patch correctif Java
├── quality-agent.py       ← KPI, gate, flaky, vérification cohérence
├── advisor-agent.py       ← Vote GO/NO-GO, prédiction, recommandations
├── reporting-agent.py     ← Allure report, dashboard HTML, Slack/Teams
├── planning-agent.py      ← Catalogue 26 TCs, couverture, gaps, Jira
├── ci-agent.py            ← Git commit (sans .env), push SSL, PR, release
└── observability-agent.py ← Traces, circuit breaker, coûts LLM, prompts
```

---

## Shared modules (copiés depuis api-pytest-framework)

| Fichier | Rôle |
|---|---|
| `llm.py` | 6 patterns LLM : chat, cot, structured, confident, self_consistent, adversarial |
| `prompt_store.py` | Versioning semver des prompts JSON |
| `circuit_breaker.py` | CLOSED / OPEN / HALF_OPEN — protection LLM |
| `tracer.py` | Traces JSONL + spans |
| `memory_store.py` | Mémoire épisodique (épisodes.jsonl) |
| `jira_fetcher_agent.py` | Client Jira REST |

---

## Commandes rapides

```bash
# Status framework
python agents/pipeline-agent.py status

# Lancer les tests @smoke + gate
python agents/pipeline-agent.py smoke

# Pipeline complet
python agents/pipeline-agent.py full

# Pipeline nightly (regression + rapport)
python agents/pipeline-agent.py nightly

# Générer feature + steps + page pour TC1 et TC2
python agents/codegen-agent.py full --tc 1 2

# Voir les 26 TCs et leur statut d'automatisation
python agents/planning-agent.py tc

# Triage automatique des échecs
python agents/bug-agent.py triage

# Vote GO/NO-GO release
python agents/advisor-agent.py release

# Rapport Allure + Slack
python agents/reporting-agent.py publish

# Voir les prompts versionnés
python agents/observability-agent.py prompts list
```

---

## Pipelines disponibles

| Pipeline | Commande | Étapes |
|---|---|---|
| **Full** | `pipeline-agent.py full` | planning → codegen → run → quality → bug → report → advisor → ci |
| **Quick** | `pipeline-agent.py quick` | run → triage → kpi → gate |
| **Smoke** | `pipeline-agent.py smoke` | run @smoke → gate → notify |
| **Nightly** | `pipeline-agent.py nightly` | regression → flaky → analyze → report → predict → jira sync |
| **Gate** | `pipeline-agent.py gate` | vérification quality gate seule |
| **Report** | `pipeline-agent.py report` | KPI + dashboards (sans run) |

---

## 26 TCs — automationexercise.com

| Tag | TCs |
|---|---|
| `@smoke` | TC1, TC2, TC8, TC9 |
| `@critical` | TC12, TC14, TC15, TC16 |
| `@auth` | TC1-TC5 |
| `@cart` | TC11-TC13, TC17, TC20, TC22 |
| `@order` | TC14-TC16, TC23, TC24 |
| `@products` | TC8, TC9, TC18-TC21 |
| `@negative` | TC3, TC5 |

---

## Prompts versionnés — `prompts/`

| Fichier | Agent | Pattern |
|---|---|---|
| `triage_classify.json` | bug-agent | chat_structured |
| `rca_analyze.json` | bug-agent | chat_cot |
| `repair_patch.json` | bug-agent | chat_structured |
| `tc_generate.json` | codegen-agent | chat |
| `release_vote.json` | advisor-agent | chat_structured |
| `predict_gate.json` | advisor-agent | chat_confident |
| `flaky_analyze.json` | quality-agent | chat_self_consistent |
| `qa_notify.json` | reporting-agent | chat |

Gestion :
```bash
python agents/observability-agent.py prompts list
python agents/observability-agent.py prompts rollback triage_classify
python agents/observability-agent.py prompts versions rca_analyze
```

---

## Quality Gate

| Métrique | Seuil |
|---|---|
| Pass rate | ≥ 90% |
| Fail rate | ≤ 5% |
| Confiance LLM | ≥ 0.70 |

---

## Sécurité

- `.env` → **JAMAIS commité** (contient GROQ_API_KEY)
- `ci-agent.py` bloque automatiquement tout stage de `.env`, `*.properties`
- Push toujours avec : `git -c http.sslVerify=false push origin main`
