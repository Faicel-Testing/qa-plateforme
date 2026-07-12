# Agents IA — perf_k6_qacart

Framework : **k6 1.1 + JavaScript**
Application : **QACart Todo** — qacart-todo.herokuapp.com — 3 scénarios (smoke, load, stress) sur l'API auth réelle
Agents : **JavaScript/Node** (même écosystème que le framework testé) — même pattern que `ui_cypress_bdd/scripts/agents/`

---

## Architecture — 10 agents

```
pipeline-agent.js          ← Orchestrateur maître
├── runner-agent.js        ← Exécution k6 run + parsing summary-export
├── codegen-agent.js       ← Génération de scénarios k6 depuis Jira
├── bug-agent.js           ← Boucle agentique : analyse + recalibration de seuils
├── quality-agent.js       ← Triage des seuils dépassés, RCA, vérification adversariale
├── advisor-agent.js       ← Vote GO/NO-GO, prédiction, mémoire épisodique
├── reporting-agent.js     ← KPI, dashboard HTML Chart.js, Slack/Teams
├── planning-agent.js      ← Couverture des types de charge (smoke/load/stress/soak/spike), stories/sprints Jira
├── ci-agent.js            ← Git commit (message LLM), PR, release, statut CI
└── observability-agent.js ← Traces LLM, circuit breaker, coûts, prompts versionnés
```

---

## Modules partagés (copiés depuis ui_cypress_bdd/scripts/agents, corrigés ici)

| Fichier | Rôle |
|---|---|
| `llm.js` | Provider Groq/Ollama, patterns chat/cot/structured/confident/adversarial/self-consistent — **corrigé** : préserve `id`/`type` des `tool_calls` Groq (bug pré-existant dans les autres frameworks, invisible sur les boucles à 1 tour) |
| `jira-fetcher.js` | Client Jira REST (stories, issues, epics, commentaires) |
| `shared/tracer.js` | Traces JSONL des appels LLM (logs/traces.jsonl) |
| `shared/memory-store.js` | Mémoire épisodique (memory/episodes.jsonl) |
| `shared/prompt-store.js` | Versioning semver des prompts (prompts/*.json) |
| `shared/circuit-breaker.js` | CLOSED/OPEN/HALF_OPEN + cache SHA256 des réponses LLM |

---

## Ce qui change vs un framework fonctionnel (BDD)

Il n'y a pas de "test qui échoue" au sens Allure ici — il y a des **seuils k6 dépassés** (`thresholds` dans `reports/summary-*.json`, `true` = dépassé). Toute la couche agents lit cette source à la place d'`allure-results/` :

| Concept fonctionnel (Cypress/Playwright/RestAssured) | Équivalent perf (k6) |
|---|---|
| Test en échec (`status: failed`) | Seuil dépassé (`metric.thresholds[expr] === true`) |
| Catégorie de triage (`real_bug`, `flaky`...) | `backend_degradation`, `test_config_too_aggressive`, `network_flakiness`, `env_shared_demo` |
| Pass rate / Fail rate | p95 de latence, taux d'erreur, checks pass rate |
| Réparation de code de test | Recalibration de seuil/palier de VUs (jamais l'app testée) |
| Couverture par tags Gherkin (`@smoke`, `@negative`...) | Couverture par type de charge (`smoke`, `load`, `stress`, `soak`, `spike`) |

`bug-agent.js` a un périmètre d'écriture restreint (`ALLOWED_PREFIXES = ['k6/scenarios', 'k6/lib', 'k6/config']`) — il ne peut recalibrer que les scénarios k6, jamais l'application testée.

---

## Commandes rapides

```bash
# Status framework
node scripts/agents/pipeline-agent.js status

# Lancer le scénario smoke
node scripts/agents/runner-agent.js smoke

# Pipeline complet
node scripts/agents/pipeline-agent.js full

# Pipeline rapide (run + triage + dashboard + gate)
node scripts/agents/pipeline-agent.js quick

# Triage des seuils dépassés
node scripts/agents/quality-agent.js triage

# Vote GO/NO-GO release
node scripts/agents/advisor-agent.js advise

# Dashboard KPI
node scripts/agents/reporting-agent.js dashboard

# Voir les prompts versionnés
node scripts/agents/observability-agent.js prompts list
```

---

## Pipelines disponibles

| Pipeline | Commande | Étapes |
|---|---|---|
| **Full** | `pipeline-agent.js full` | planning → run → quality → bug → reporting (dashboard) → advisor → observability → ci |
| **Quick** | `pipeline-agent.js quick` | run → triage → dashboard → gate |
| **Report** | `pipeline-agent.js report` | quality full → bug report → dashboard → observability report (sans run) |
| **Status** | `pipeline-agent.js status` | vérifie la présence de tous les agents et artefacts |

---

## 3 scénarios — qacart-todo.herokuapp.com (API auth réelle)

| Scénario | Charge | Requêtes | Checks | p95 | Seuils |
|---|---|---|---|---|---|
| `smoke.js` | 1 VU × 5 itérations | 15 | 15/15 (100%) | 275ms | ✅ |
| `load.js` | 5→8 VUs, ~80s | 653 | 653/653 (100%) | 485ms | ✅ |
| `stress.js` | 10→20 VUs, ~90s | 1218 | 1218/1218 (100%) | 1596ms | ❌ `http_req_duration p(95)<1500` |

Résultat run réel local (3 exécutions consécutives) : le dépassement en `stress` est **réel et non masqué** (dégradation backend sous charge, dyno Heroku gratuit partagé) — classé `backend_degradation` par `quality-agent.js triage` (confiance 80%), voté **GO** à l'unanimité par `advisor-agent.js advise` car non-bloquant (smoke/load intacts).

---

## Prompts versionnés — `prompts/`

| Fichier | Agent | Pattern |
|---|---|---|
| `triage_classify.json` | quality-agent | chat_confident |
| `rca_analyze.json` | quality-agent | chat_cot |
| `repair_patch.json` | bug-agent | tool use (agentic loop) |
| `tc_generate_perf.json` | codegen-agent | chat |
| `release_vote.json` | advisor-agent | chat_self_consistent |
| `predict_gate.json` | advisor-agent | chat_structured |
| `flaky_analyze.json` | quality-agent | chat |
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
| Seuils dépassés en `smoke`/`load` (bloquant) | 0 |
| Seuils dépassés en `stress` (non-bloquant, infra partagée) | toléré, tracé |
| Confiance LLM | ≥ 0.70 |

---

## Sécurité

- `.env` → **JAMAIS commité** (contient GROQ_API_KEY)
- Push toujours avec : `git -c http.sslVerify=false push origin main` (contournement PKIX documenté du repo)
