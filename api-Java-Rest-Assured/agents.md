# Agents IA — api-Java-Rest-Assured

Framework : **RestAssured 5.4 + Cucumber 7 + TestNG 7.9 + Java 17 + Maven**
Application : **restful-booker.herokuapp.com** — 51 scénarios (8 features)
Agents : **Python** (appellent Maven via subprocess, lisent les résultats Allure JSON)

---

## Architecture — 10 agents

```
pipeline-agent.py          ← Orchestrateur maître
├── runner-agent.py        ← Exécution Maven + détection flaky
├── codegen-agent.py       ← Génération Java (feature, steps, client)
├── bug-agent.py           ← Triage, RCA, patch correctif Java
├── quality-agent.py       ← KPI, gate, flaky, vérification cohérence
├── advisor-agent.py       ← Vote GO/NO-GO, prédiction, recommandations
├── reporting-agent.py     ← Allure report, dashboard HTML, Slack/Teams
├── planning-agent.py      ← Catalogue 8 features / 51 scénarios, couverture, gaps, Jira
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
| `memory_store.py` | Mémoire épisodique (episodes.jsonl) |
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

# Générer un nouveau feature + steps
python agents/codegen-agent.py feature <nom> <endpoint>

# Voir la couverture des 51 scénarios
python agents/planning-agent.py coverage

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
| **Full** | `pipeline-agent.py full` | planning → run → quality → bug → report → advisor → ci |
| **Quick** | `pipeline-agent.py quick` | run → triage → kpi → gate |
| **Smoke** | `pipeline-agent.py smoke` | run @smoke → gate → notify |
| **Nightly** | `pipeline-agent.py nightly` | run complet → flaky → analyze → report → predict → jira sync |
| **Gate** | `pipeline-agent.py gate` | vérification quality gate seule |
| **Report** | `pipeline-agent.py report` | KPI + dashboards (sans run) |

---

## 51 scénarios — restful-booker.herokuapp.com

| Feature | Endpoint | Scénarios |
|---|---|---|
| `auth.feature` | `POST /auth` | 5 |
| `booking_list.feature` | `GET /booking` | 7 |
| `booking_get.feature` | `GET /booking/{id}` | 7 |
| `booking_create.feature` | `POST /booking` | 12 |
| `booking_update.feature` | `PUT /booking/{id}` | 6 |
| `booking_patch.feature` | `PATCH /booking/{id}` | 7 |
| `booking_delete.feature` | `DELETE /booking/{id}` | 6 |
| `health_check.feature` | `GET /ping` | 1 |

| Tag | Scénarios (mesurés) |
|---|---|
| `@smoke` | 9 |
| `@critical` | 8 |
| `@auth` | 4 |
| `@securite` | 4 |

---

## Prompts versionnés — `prompts/`

| Fichier | Agent | Pattern |
|---|---|---|
| `triage_classify.json` | bug-agent | chat_confident |
| `rca_analyze.json` | bug-agent | chat_cot |
| `repair_patch.json` | bug-agent | chat_structured |
| `tc_generate.json` | codegen-agent | chat |
| `release_vote.json` | advisor-agent | chat_self_consistent |
| `predict_gate.json` | advisor-agent | chat_structured |
| `flaky_analyze.json` | quality-agent | chat |
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
