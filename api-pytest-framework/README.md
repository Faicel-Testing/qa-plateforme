# QA Platform — API pytest-bdd + AI Agents

[![CI](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci-api-pytest.yml/badge.svg)](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci-api-pytest.yml)
[![Tests](https://img.shields.io/badge/Tests-51%20BDD-blue)](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci-api-pytest.yml)
[![Pass](https://img.shields.io/badge/Pass-48%2F51-brightgreen)](https://faicel-testing.github.io/qa-plateforme/api-pytest-framework/)
[![Allure Report](https://img.shields.io/badge/Allure-Report-orange)](https://faicel-testing.github.io/qa-plateforme/api-pytest-framework/)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![pytest-bdd](https://img.shields.io/badge/pytest--bdd-7.3-green)](https://github.com/pytest-dev/pytest-bdd)
[![LLM](https://img.shields.io/badge/LLM-Groq%20LLaMA%203.3-purple)](https://console.groq.com/)
[![Agents](https://img.shields.io/badge/AI%20Agents-10-blueviolet)](#les-10-agents-ia)

---

## Vue d'ensemble

Framework de test API pour l'application **Hotel Booking** (restful-booker.herokuapp.com).

- **51 scénarios BDD** couvrant les 8 endpoints (POST /auth, CRUD /booking, GET /ping)
- **10 agents IA** organisés par domaine, chacun avec des sous-commandes
- **6 patterns LLM** : `chat`, `chat_cot` (Chain of Thought), `chat_structured`, `chat_confident`, `chat_self_consistent`, `chat_adversarial`
- **8 prompt templates versionnés** (semver) dans `prompts/` — modifiables sans toucher au code
- **PromptStore câblé** dans les agents : `record_usage()` alimente les métriques (calls, avg_confidence) à chaque run
- **Circuit Breaker** 3 états pour la résilience LLM (CLOSED / OPEN / HALF_OPEN)
- **Agentic Loop** : AGENT_MAX_ITER=5, hard cap 20

---

## Architecture

```
api-pytest-framework/
├── agents/                    # 10 agents IA + 6 modules partagés
│   ├── runner-agent.py        # Exécution tests : run, smoke, critical, regression, gono-go, baseline
│   ├── bug-agent.py           # Bugs : triage, rca, repair, report, loop (agentic)
│   ├── codegen-agent.py       # Génération : spec, generate, tc, coverage, full
│   ├── quality-agent.py       # Qualité : analyze, kpi, flaky, verify, gate
│   ├── reporting-agent.py     # Rapports : generate, serve, open, notify, publish
│   ├── advisor-agent.py       # Décisions : release, predict, recommend, report
│   ├── observability-agent.py # Observabilité : traces, circuit, memory, prompts, dashboard
│   ├── ci-agent.py            # CI/CD : commit, push, pr, ci, release, changelog
│   ├── planning-agent.py      # Planning : setup, stories, sprint, tc, tickets, sync
│   ├── pipeline-agent.py      # Orchestrateur : full, quick, nightly, report, gate, status
│   ├── llm.py                 # 6 patterns LLM (Groq / LLaMA 3.3 70B)
│   ├── circuit_breaker.py     # Résilience LLM (CLOSED/OPEN/HALF_OPEN)
│   ├── memory_store.py        # Mémoire épisodique (JSONL)
│   ├── prompt_store.py        # Versioning sémantique des prompts (semver)
│   ├── tracer.py              # Traçabilité des appels LLM
│   └── jira_fetcher_agent.py  # Client Jira (stories, bugs, sprints)
├── prompts/                   # 8 prompt templates versionnés (semver)
│   ├── triage_classify.json   # Classification échecs API (4 catégories)
│   ├── rca_analyze.json       # Root Cause Analysis (CoT)
│   ├── tc_generate.json       # Génération de scénarios BDD
│   ├── release_vote.json      # Décision GO/NO-GO release
│   ├── qa_notify.json         # Notifications QA narratives
│   ├── repair_patch.json      # Patch correctif automatique
│   ├── predict_gate.json      # Prédiction quality gate prochain run
│   └── flaky_analyze.json     # Analyse causes flakiness
├── features/                  # 8 fichiers .feature Gherkin
├── steps/                     # Step definitions pytest-bdd
├── docs/                      # KPI dashboard HTML, specs JSON
├── allure-results/            # Résultats de test Allure
├── agents.md                  # Convention CLAUDE.md — guide agents IA sur ce repo
└── pytest.ini                 # Configuration pytest
```

---

## Les 10 Agents IA

| Agent | Rôle | Commandes clés |
|-------|------|----------------|
| **runner-agent** | Exécute les tests pytest-bdd | `smoke`, `critical`, `regression`, `gono-go`, `baseline` |
| **bug-agent** | Triage, RCA et réparation autonome | `triage`, `rca`, `repair`, `loop` |
| **codegen-agent** | Génère specs, TCs et code de test | `spec`, `generate`, `tc`, `coverage`, `full` |
| **quality-agent** | KPI, flaky, vérification, gate | `analyze`, `kpi`, `flaky`, `verify`, `gate` |
| **reporting-agent** | Allure HTML + Slack/Teams | `generate`, `serve`, `notify`, `publish` |
| **advisor-agent** | Décision release + prédiction | `release`, `predict`, `recommend` |
| **observability-agent** | Traces, circuit breaker, mémoire | `traces`, `circuit`, `memory`, `prompts`, `dashboard` |
| **ci-agent** | Git, GitHub PR, GitHub Actions | `commit`, `push`, `pr`, `ci`, `release`, `changelog` |
| **planning-agent** | Jira : US, sprints, TCs, tickets | `setup`, `stories`, `sprint`, `tc`, `tickets`, `sync` |
| **pipeline-agent** | Orchestrateur maître | `full`, `quick`, `nightly`, `report`, `gate`, `status` |

---

## Quality Gates

| Pipeline | Marker | Pass Rate | Fail Rate Max |
|----------|--------|-----------|---------------|
| Smoke | `@smoke` | ≥ 90% | ≤ 5% |
| Critical | `@critical` | ≥ 90% | ≤ 5% |
| Regression | `@regression` | ≥ 90% | ≤ 5% |
| Nightly | toutes | ≥ 90% | ≤ 5% |

---

## Démarrage rapide

```bash
# Installation
pip install -r requirements.txt

# Pipeline rapide (smoke + gate)
python agents/pipeline-agent.py quick

# Pipeline complet
python agents/pipeline-agent.py full

# Tests seuls
python agents/runner-agent.py smoke
python agents/runner-agent.py regression

# KPI dashboard
python agents/quality-agent.py kpi

# Rapport Allure
python agents/reporting-agent.py publish

# Agentic bug loop
python agents/bug-agent.py loop

# Statut du pipeline
python agents/pipeline-agent.py status
```

---

## Variables d'environnement

```env
GROQ_API_KEY=...           # LLM Groq (obligatoire)
JIRA_URL=...               # URL Jira Cloud
JIRA_EMAIL=...             # Email Jira
JIRA_TOKEN=...             # Token API Jira
SLACK_WEBHOOK_URL=...      # Notifications Slack (optionnel)
TEAMS_WEBHOOK_URL=...      # Notifications Teams (optionnel)
AGENT_MAX_ITER=5           # Iterations agentic loop (défaut: 5, max: 20)
```

---

## Patterns LLM

| Pattern | Méthode | Usage |
|---------|---------|-------|
| Standard | `llm.chat()` | Génération texte simple |
| Chain of Thought | `llm.chat_cot()` | Analyse complexe, triage, RCA |
| Structured Output | `llm.chat_structured()` | Génération JSON garantie (retry x3) |
| Confidence Scoring | `llm.chat_confident()` | Décisions critiques avec score 0–1 |
| Self-Consistency | `llm.chat_self_consistent()` | Vote majoritaire release N=3 |
| Adversarial | `llm.chat_adversarial()` | 3 phases : proposant → critique → arbitre |

---

## Prompt Store

Les prompts LLM sont externalisés dans `prompts/` et versionnés en semver. Chaque agent charge son template via `PromptStore.get("nom")` avec fallback inline si le fichier est absent.

| Template | Agent | Pattern LLM | Variables clés |
|----------|-------|-------------|----------------|
| `triage_classify` | bug-agent | `chat_confident` | test_name, tc, status, error_message, stack_trace |
| `rca_analyze` | bug-agent | `chat_cot` | test_name, tc, suite, error_message, stack_trace, other_tcs |
| `repair_patch` | bug-agent | `chat_cot` | test_name, tc, error_message, stack_trace, source_context |
| `release_vote` | advisor-agent | `chat_self_consistent` | context_str |
| `predict_gate` | advisor-agent | `chat_structured` | context_str |
| `tc_generate` | codegen-agent | `chat_structured` | us_id, us_title, us_description |
| `qa_notify` | reporting-agent | `chat` | run_summary, pass_rate, failed_count |
| `flaky_analyze` | quality-agent | `chat` | flaky_list, runs |

**Modifier un prompt sans toucher au code :**

```bash
# Voir les métriques d'usage
python agents/observability-agent.py prompts

# Inspecter les versions
python agents/observability-agent.py prompts list

# Rollback vers la version précédente
python agents/observability-agent.py prompts rollback triage_classify
```

Les métriques `calls` et `avg_confidence` s'alimentent automatiquement à chaque run via `_ps.record_usage()`.

---

## Auteur

**Faicel Ghanem** — QA Automation Architect  
[GitHub](https://github.com/Faicel-Testing) · [LinkedIn](https://linkedin.com/in/faicel-ghanem)
