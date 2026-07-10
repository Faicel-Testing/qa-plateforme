# Agents IA — ui_cypress_bdd

Framework : **Cypress 13.17 + @badeball/cypress-cucumber-preprocessor + JavaScript**
Application : **QACart Todo** — qacart-todo.herokuapp.com — 29 scénarios (9 features)
Agents : **JavaScript/Node** (même écosystème que le framework testé, pas de cross-langage) — même pattern que `ui_playwright_bdd/scripts/agents/`

---

## Architecture — 10 agents

```
pipeline-agent.js          ← Orchestrateur maître
├── runner-agent.js        ← Exécution cypress run + détection flaky
├── codegen-agent.js       ← Génération feature + steps + page objects JS
├── bug-agent.js           ← Boucle agentique : analyse + réparation
├── quality-agent.js       ← Triage, RCA, vérification adversariale
├── advisor-agent.js       ← Vote GO/NO-GO, prédiction, mémoire épisodique
├── reporting-agent.js     ← KPI, dashboard HTML, Slack/Teams, sync Jira, historique Trend
├── planning-agent.js      ← Couverture des 9 features, stories/sprints Jira
├── ci-agent.js            ← Git commit (message LLM), PR, release, statut CI
└── observability-agent.js ← Traces LLM, circuit breaker, coûts, prompts versionnés
```

---

## Modules partagés (copiés depuis ui_playwright_bdd/scripts/agents)

| Fichier | Rôle |
|---|---|
| `llm.js` | Provider Groq/Ollama, patterns chat/cot/structured/confident/adversarial/self-consistent |
| `jira-fetcher.js` | Client Jira REST (stories, issues, epics, commentaires) |
| `shared/tracer.js` | Traces JSONL des appels LLM (logs/traces.jsonl) |
| `shared/memory-store.js` | Mémoire épisodique (memory/episodes.jsonl) |
| `shared/prompt-store.js` | Versioning semver des prompts (prompts/*.json) |
| `shared/circuit-breaker.js` | CLOSED/OPEN/HALF_OPEN + cache SHA256 des réponses LLM |

---

## Commandes rapides

```bash
# Status framework
node scripts/agents/pipeline-agent.js status

# Lancer les tests @smoke
node scripts/agents/runner-agent.js smoke

# Pipeline complet
node scripts/agents/pipeline-agent.js full

# Pipeline rapide (run + triage + dashboard + gate)
node scripts/agents/pipeline-agent.js quick

# Triage automatique des échecs
node scripts/agents/bug-agent.js analyze

# Vote GO/NO-GO release
node scripts/agents/advisor-agent.js advise

# Dashboard KPI
node scripts/agents/reporting-agent.js dashboard

# Sauvegarder l'historique Allure (Trend)
node scripts/agents/reporting-agent.js history

# Voir les prompts versionnés
node scripts/agents/observability-agent.js prompts list
```

---

## Pipelines disponibles

| Pipeline | Commande | Étapes |
|---|---|---|
| **Full** | `pipeline-agent.js full` | planning → run → quality → bug → reporting (dashboard+sync) → advisor → observability → ci |
| **Quick** | `pipeline-agent.js quick` | run → triage → dashboard → gate |
| **Report** | `pipeline-agent.js report` | quality full → bug report → dashboard → observability report (sans run) |
| **Status** | `pipeline-agent.js status` | vérifie la présence de tous les agents et artefacts |

---

## 29 scénarios — qacart-todo.herokuapp.com

| Feature | Scénarios |
|---|---|
| `Id01_SignupTest.feature` | 1 |
| `Id01_SignupNegativeTest.feature` | 7 |
| `Id02_LoginTest.feature` | 1 |
| `Id05_LoginNegativeTest.feature` | 7 |
| `Id03_TodoTest.feature` | 1 |
| `Id03_TodoNegativeTest.feature` | 4 |
| `Id04_DeleteTodoTest.feature` | 1 |
| `Id04_DeleteTodoNegativeTest.feature` | 4 |
| `Id09_ApiSetupTest.feature` | 3 |

Résultat run réel local : **29/29 passent (100 %)**.

---

## Prompts versionnés — `prompts/`

| Fichier | Agent | Pattern |
|---|---|---|
| `triage_classify.json` | quality-agent | chat_confident |
| `rca_analyze.json` | quality-agent | chat_cot |
| `repair_patch.json` | bug-agent | tool use (agentic loop) |
| `tc_generate_ui.json` | codegen-agent | chat |
| `release_vote.json` | advisor-agent | chat_self_consistent |
| `predict_gate.json` | advisor-agent | chat_structured |
| `flaky_analyze.json` | runner-agent | chat |
| `qa_notify.json` | reporting-agent | chat |

Gestion :
```bash
node scripts/agents/observability-agent.js prompts list
node scripts/agents/observability-agent.js prompts rollback triage_classify
node scripts/agents/observability-agent.js prompts history rca_analyze
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
- Push toujours avec : `git -c http.sslVerify=false push origin main` (contournement PKIX documenté du repo)
