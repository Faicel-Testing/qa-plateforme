# QA Platform — API pytest-bdd + AI Agents

[![CI](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci-api-pytest.yml/badge.svg)](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci-api-pytest.yml)
[![Tests](https://img.shields.io/badge/Tests-51%20BDD-blue)](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci-api-pytest.yml)
[![Pass](https://img.shields.io/badge/Pass-48%2F51-brightgreen)](https://faicel-testing.github.io/qa-plateforme/api-pytest-framework/)
[![Allure Report](https://img.shields.io/badge/Allure-Report-orange)](https://faicel-testing.github.io/qa-plateforme/api-pytest-framework/)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![pytest-bdd](https://img.shields.io/badge/pytest--bdd-7.3-green)](https://github.com/pytest-dev/pytest-bdd)
[![LLM](https://img.shields.io/badge/LLM-Groq%20LLaMA%203.3-purple)](https://console.groq.com/)
[![Agents](https://img.shields.io/badge/AI%20Agents-31-blueviolet)](#les-31-agents-ia)

> **pytest-bdd + Requests + Groq AI** — Un framework de test API qui se pilote, s'analyse et se documente lui-même.
> **31 agents IA** · 12 techniques IA · GO/NO-GO production · Prédiction d'échecs · Circuit Breaker · Mémoire épisodique · Notification Slack/Teams

---

## Vue d'ensemble

```
Spec métier  →  Features Gherkin  →  Tests API  →  Allure Report  →  Jira TCs
     ↑                                                    ↓
     └──────────────── 31 agents IA pilotent tout ────────┘
         Triage · RCA · Patch · Prédiction · Gate · Slack/Teams
```

51 cas de test BDD couvrant l'API REST [restful-booker](https://restful-booker.herokuapp.com), avec
synchronisation automatique Jira, pipeline CI/CD GitHub Actions, rapports Allure et une couche complète
d'**intelligence artificielle** : triage automatique des échecs, analyse de cause racine, prédiction
d'instabilité, circuit breaker, mémoire épisodique, versioning des prompts.

---

## Rapport Allure — Live

> **[Voir le rapport en direct](https://faicel-testing.github.io/qa-plateforme/api-pytest-framework/)** — mis à jour automatiquement à chaque push sur `main`.

![Allure Report](docs/allure-screenshot.png)

*Rapport Allure : Quality Gate intégré (PASSED/FAILED) — KPIs Pass Rate · Fail Rate · Flaky Rate — généré automatiquement par `kpi-agent.py`*

---

## Quality Gate

Le **Quality Gate** est calculé automatiquement par `kpi-agent.py` à chaque exécution.

| Critère | Seuil | Valeur actuelle | Statut |
|---------|-------|-----------------|--------|
| Pass Rate | ≥ 90% | 88.2% | ❌ |
| Fail Rate | ≤ 5% | 5.5% | ❌ |
| Anomaly Rate | ≤ 10% | 11.8% | ❌ |
| Flaky Rate | ≤ 20% | 0.0% | ✅ |
| Automation Coverage | ≥ 80% | 100.0% | ✅ |
| **Verdict** | | **2/5 critères** | **FAILED** |

```bash
python agents/kpi-agent.py
allure generate allure-results -o allure-report --clean
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        api-pytest-framework                                  │
│                    QA Automation + AI Agents Platform                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  TRIGGER LAYER                                                               │
│  git push ──► .github/workflows/ci-api-pytest.yml ◄── cron lun-ven 06h UTC  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TEST LAYER  (pytest-bdd + Gherkin)                                          │
│  features/*.feature  →  tests/test_*_bdd.py  →  pages/ (requests HTTP)      │
│  51 TCs  |  48 PASS  |  3 FAIL  |  JSON Schema validation                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  REPORTING LAYER                                                             │
│  allure-results/ (JSON) → allure generate → allure-report/ (HTML)           │
│  GitHub Artifacts : allure-results + allure-report (rétention 30 jours)     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AI AGENT LAYER  (30 agents · Groq LLaMA 3.3 70B · Ollama fallback)         │
│                                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐    │
│  │  EXÉCUTION &    │  │  ANALYSE IA      │  │  QUALITÉ & PRODUCTION   │    │
│  │  GÉNÉRATION     │  │                  │  │                         │    │
│  │                 │  │ triage-agent     │  │ smoke-regression-agent  │    │
│  │ api-spec-agent  │  │  Confidence Score│  │ release-advisor-agent   │    │
│  │ api-generate-   │  │ rca-agent        │  │  Self-Consistency (×3)  │    │
│  │   agent         │  │  Chain of Thought│  │ kpi-agent               │    │
│  │ api-execute-    │  │ bug-analyzer     │  │  Quality Gate           │    │
│  │   agent         │  │  CoT + Patch     │  │ report-agent            │    │
│  │ api-reporter-   │  │ coverage-agent   │  │                         │    │
│  │   agent         │  │ flaky-agent      │  └─────────────────────────┘    │
│  │ tc-generator-   │  │ verifier-agent   │                                  │
│  │   agent         │  │  Adversarial     │  ┌─────────────────────────┐    │
│  │ qa-agent        │  │ qa-agent         │  │  GIT & GITHUB           │    │
│  └─────────────────┘  └──────────────────┘  │                         │    │
│                                              │ git-agent               │    │
│  ┌─────────────────────────────────────┐    │  Conventional Commits   │    │
│  │  RÉSILIENCE & MÉMOIRE              │    │ github-agent            │    │
│  │                                     │    │  CI/CD · PR · Release   │    │
│  │ observability-agent  LLM tracing    │    └─────────────────────────┘    │
│  │ resilience-agent     Circuit Breaker│                                    │
│  │ memory-agent         Episodic Memory│    ┌─────────────────────────┐    │
│  │ prompt-versioning-   Semver prompts │    │  JIRA & GESTION         │    │
│  │   agent              A/B testing   │    │                         │    │
│  │ predictive-agent     Failure pred. │    │ jira-agent              │    │
│  └─────────────────────────────────────┘    │ jira-ticket-agent       │    │
│                                              │ sprint-agent            │    │
│  ┌──────────────────────────────────────┐   │ status-agent            │    │
│  │  SUPPORT MODULES (partagés)          │   │ user-stories-agent      │    │
│  │  llm.py · tracer.py                  │   │ test-case-agent         │    │
│  │  circuit_breaker.py · memory_store.py│   └─────────────────────────┘    │
│  │  prompt_store.py · jira_fetcher.py   │                                   │
│  └──────────────────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  INTEGRATION LAYER                                                           │
│  Jira Cloud (HBAPI · 51 TCs · Sprint board)   GitHub (CI · PR · Releases)  │
│  Groq API (LLaMA 3.3 70B)   Ollama (fallback local)                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Les 31 agents IA

### Catégorie 1 — Exécution & Génération

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `api-spec-agent.py` | `python agents/api-spec-agent.py` | Structured Output | Lit une spec métier, extrait les User Stories, génère les features Gherkin |
| `api-generate-agent.py` | `python agents/api-generate-agent.py` | Structured Output | Détecte les lacunes de couverture et génère les scénarios manquants |
| `api-execute-agent.py` | `python agents/api-execute-agent.py` | Structured Output | Orchestre l'exécution complète avec analyse des résultats |
| `api-reporter-agent.py` | `python agents/api-reporter-agent.py` | CoT + Structured Output | Génère un rapport professionnel depuis les résultats Allure |
| `tc-generator-agent.py` | `python agents/tc-generator-agent.py` | Structured Output | Génère des cas de test structurés (positifs, négatifs, edge cases) |
| `qa-agent.py` | `python agents/qa-agent.py` | CoT + Structured Output | Lit les résultats Allure + features Gherkin — score qualité 0-100, tags manquants, scénarios à ajouter |

### Catégorie 2 — Analyse IA

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `triage-agent.py` | `python agents/triage-agent.py` | **Confidence Scoring** | Classifie chaque échec : real_bug / flaky / env_issue / false_positive avec score 0-1 |
| `rca-agent.py` | `python agents/rca-agent.py` | **Chain of Thought** | Remonte la cause racine en 3 étapes, groupe les échecs par cause commune |
| `bug-analyzer.py` | `python agents/bug-analyzer.py` | CoT + Structured Output | Analyse les échecs Allure, génère un patch de correction, applique si `safe_to_autofix` |
| `coverage-agent.py` | `python agents/coverage-agent.py` | CoT | Analyse la couverture API, identifie les endpoints non testés |
| `flaky-agent.py` | `python agents/flaky-agent.py detect` | Structured Output | Détecte les tests instables sur N runs, calcule un score de flakiness, quarantaine Jira |
| `verifier-agent.py` | `python agents/verifier-agent.py` | **Adversarial Prompting** | Second agent qui tente de RÉFUTER les résultats du triage — verdict VALID/INVALID/WARNING |

### Catégorie 3 — Qualité & Production

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `smoke-regression-agent.py` | `python agents/smoke-regression-agent.py gono-go` | Structured Output | Lance @smoke + @critical, émet un verdict GO/NO-GO, crée un bug Jira si bloquant |
| `release-advisor-agent.py` | `python agents/release-advisor-agent.py` | **Self-Consistency (×3)** | 3 appels LLM indépendants + vote majoritaire → recommandation GO/NO-GO robuste |
| `kpi-agent.py` | `python agents/kpi-agent.py` | Structured Output | Quality Gate + dashboard HTML KPI + widget Allure ENVIRONMENT |
| `report-agent.py` | `python agents/report-agent.py` | CoT | Pipeline complet : run → analyse → rapport HTML avec résumé narratif LLM |

### Catégorie 4 — Jira & Gestion

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `jira-agent.py` | `python agents/jira-agent.py` | Structured Output | Setup projet Jira + matrice de traçabilité US ↔ TCs |
| `jira-ticket-agent.py` | `python agents/jira-ticket-agent.py` | Structured Output | Crée des tickets Bug structurés depuis les échecs Allure |
| `sprint-agent.py` | `python agents/sprint-agent.py board` | — | Affiche le tableau Kanban, le backlog, déplace les issues |
| `status-agent.py` | `python agents/status-agent.py sync` | — | Lit les résultats Allure et met à jour les statuts des TCs Jira |
| `user-stories-agent.py` | `python agents/user-stories-agent.py` | Structured Output | Génère 8 User Stories dans Jira depuis une spec API |
| `test-case-agent.py` | `python agents/test-case-agent.py` | Structured Output | Gestion TCs Jira + génération Gherkin depuis les issues |

### Catégorie 5 — Résilience & Mémoire

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `observability-agent.py` | `python agents/observability-agent.py` | **Observability/Tracing** | Monitore chaque appel LLM (durée, tokens, confiance) — détecte anomalies et dérives |
| `resilience-agent.py` | `python agents/resilience-agent.py` | **Circuit Breaker** | 3 états (CLOSED/OPEN/HALF_OPEN) + fallback chain : Groq → Ollama → cache → défaut |
| `memory-agent.py` | `python agents/memory-agent.py` | **Episodic Memory** | Stocke et interroge l'historique des runs — injecte le contexte passé dans les prompts |
| `prompt-versioning-agent.py` | `python agents/prompt-versioning-agent.py` | **Prompt Versioning** | Versioning semver des prompts + rollback + A/B testing |
| `predictive-agent.py` | `python agents/predictive-agent.py predict` | **Predictive Analytics** | Calcule failure_probability + tendance (dégradant/stable/volatile) par TC depuis l'historique |

### Catégorie 6 — Git & GitHub

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `git-agent.py` | `python agents/git-agent.py` | Structured Output | Génère un message Conventional Commits via LLM, commit + push + release |
| `github-agent.py` | `python agents/github-agent.py ci run` | Structured Output | CI/CD, PRs, releases, issues, changelog via `gh` CLI |

### Catégorie 7 — Notifications

| Agent | Commande | Technique IA | Ce qu'il fait |
|-------|----------|-------------|---------------|
| `notification-agent.py` | `python agents/notification-agent.py` | Structured Output | Envoie un résumé LLM du run vers Slack ou Teams via Incoming Webhook |

### Modules support (partagés)

| Module | Rôle |
|--------|------|
| `llm.py` | Couche d'abstraction LLM — Groq (LLaMA 3.3 70B) + fallback Ollama. Un seul point d'entrée pour tous les agents |
| `tracer.py` | Instrumente chaque appel LLM → `memory/traces.jsonl` (durée, tokens, confiance, erreurs) |
| `circuit_breaker.py` | Machine d'états CLOSED/OPEN/HALF_OPEN — fail fast + cooldown configurable |
| `memory_store.py` | Lecture/écriture de `memory/episodes.jsonl` — historique structuré par agent et par TC |
| `prompt_store.py` | Stockage et récupération des prompts versionnés par agent |
| `jira_fetcher_agent.py` | Client Jira REST v3 réutilisable — issues, transitions, sprints |
| `create_story.py` | Création directe de stories dans Jira |

---

## Les 12 techniques IA implémentées

| # | Technique | Agent(s) |
|---|-----------|---------|
| 1 | **Structured Output** — JSON garanti, retry si invalide | Tous les agents |
| 2 | **Chain of Thought** — Raisonnement 3 étapes avant conclusion | `rca-agent`, `bug-analyzer`, `coverage-agent` |
| 3 | **Confidence Scoring** — Score 0-1, &lt;0.70 → revue humaine | `triage-agent`, `flaky-agent` |
| 4 | **Adversarial Prompting** — 2ème agent qui tente de réfuter | `verifier-agent` |
| 5 | **Self-Consistency** — N appels + vote majoritaire | `release-advisor-agent` |
| 6 | **Observability/Tracing** — Trace JSONL de chaque appel LLM | `observability-agent` + `tracer.py` |
| 7 | **Prompt Versioning** — Semver + rollback + A/B test | `prompt-versioning-agent` + `prompt_store.py` |
| 8 | **Circuit Breaker** — Fail fast + fallback chain | `resilience-agent` + `circuit_breaker.py` |
| 9 | **Episodic Memory** — Historique injecté dans les prompts | `memory-agent` + `memory_store.py` |
| 10 | **Predictive Analytics** — Failure probability + tendance | `predictive-agent` |
| 11 | **Context Engineering** — `get_context_for(tc_id)` formaté pour LLM | `memory_store.py` |
| 12 | **Fallback Chain** — Groq → Ollama → Cache → Défaut | `llm.py` |

---

## Pipeline CI/CD GitHub Actions

```
git push api-pytest-framework/**
        │
        ▼
  ci-api-pytest.yml
        ├── Setup Python 3.12 + pip install
        ├── pytest tests/ --alluredir=allure-results
        ├── kpi-agent.py env ──────────────► environment.properties Allure
        ├── [IA] triage-agent.py ──────────► Classification des échecs (Confidence Scoring)
        ├── [IA] rca-agent.py ─────────────► Root Cause Analysis (Chain of Thought)
        ├── [IA] jira-ticket-agent.py ─────► Tickets Bug automatiques
        ├── [IA] release-advisor-agent.py ─► Verdict Go/No-Go (Self-Consistency ×3)
        ├── allure generate → allure-report/
        ├── Upload artifacts (30 jours)
        └── [notify] Email Gmail → faicel.ganem@gmail.com
```

**Déclencheurs :** `push` main/feature · `pull_request` · `workflow_dispatch` · `schedule` lun-ven 06h00 UTC

---

## Stack technique

```
Tests            pytest-bdd 7.3 + Gherkin (Python 3.12)
HTTP Client      requests 2.32
Assertions       assert natif + jsonschema 4.23
Reporting        Allure 2.36 (HTML) + allure-pytest
LLM primaire     Groq Cloud (llama-3.3-70b-versatile)
LLM fallback     Ollama local (llama3, mistral)
Mémoire          JSON Lines (memory/episodes.jsonl)
Traçabilité      JSON Lines (memory/traces.jsonl)
Gestion projet   Jira Cloud REST API v3 + Agile API
CI/CD            GitHub Actions + gh CLI
```

---

## Démarrage rapide

### 1. Prérequis

```bash
python >= 3.12
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Renseigner dans .env :
#   BASE_URL         → https://restful-booker.herokuapp.com
#   GROQ_API_KEY     → clé gratuite sur console.groq.com
#   JIRA_BASE_URL    → https://ton-site.atlassian.net
#   JIRA_EMAIL       → ton email Atlassian
#   JIRA_TOKEN       → token sur id.atlassian.com/manage-profile/security/api-tokens
#   JIRA_PROJECT     → clé du projet (ex: HBAPI)
```

### 3. Lancer les tests

```bash
pytest tests/ -v --alluredir=allure-results
allure serve allure-results --port 5050
```

### 4. Pipeline IA complet

```bash
# Triage des échecs
python agents/triage-agent.py

# Root Cause Analysis
python agents/rca-agent.py

# Vérification adversariale
python agents/verifier-agent.py

# Décision Go/No-Go (Self-Consistency × 3)
python agents/release-advisor-agent.py

# Dashboard KPI + Quality Gate
python agents/kpi-agent.py

# Sync Jira + tickets bugs
python agents/status-agent.py sync
python agents/jira-ticket-agent.py
```

### 5. Prédiction et mémoire

```bash
# Prédire les échecs futurs
python agents/predictive-agent.py predict

# Rapport prédictif HTML
python agents/predictive-agent.py report

# Consulter la mémoire épisodique
python agents/memory-agent.py history --tc=HBAPI-11

# Versioning des prompts
python agents/prompt-versioning-agent.py list
python agents/prompt-versioning-agent.py compare triage-agent 1.0.0 1.1.0
```

---

## Commandes par catégorie

```bash
# ── EXÉCUTION & GÉNÉRATION ──────────────────────────────────────────────────
python agents/api-spec-agent.py              # Spec → User Stories + Features Gherkin
python agents/api-generate-agent.py          # Scénarios manquants détectés par IA
python agents/api-execute-agent.py           # Exécution orchestrée + analyse
python agents/tc-generator-agent.py          # Génération TCs (Structured Output)
python agents/qa-agent.py                    # Analyse qualité suite BDD

# ── ANALYSE IA ───────────────────────────────────────────────────────────────
python agents/triage-agent.py                # Classification échecs (Confidence Scoring)
python agents/rca-agent.py                   # Root Cause Analysis (Chain of Thought)
python agents/bug-analyzer.py                # Analyse + patch automatique
python agents/coverage-agent.py              # Couverture API
python agents/flaky-agent.py detect --runs=3 # Détection tests instables
python agents/flaky-agent.py report          # Rapport flaky
python agents/verifier-agent.py              # Vérification adversariale (VALID/INVALID)

# ── QUALITÉ & PRODUCTION ────────────────────────────────────────────────────
python agents/smoke-regression-agent.py smoke    # 5 TCs @smoke
python agents/smoke-regression-agent.py gono-go  # Verdict GO/NO-GO
python agents/release-advisor-agent.py           # Self-Consistency (3 votes)
python agents/kpi-agent.py                       # Dashboard KPI + Quality Gate
python agents/kpi-agent.py dashboard             # docs/kpi-dashboard.html
python agents/report-agent.py                    # Pipeline run→rapport complet

# ── RÉSILIENCE & MÉMOIRE ────────────────────────────────────────────────────
python agents/observability-agent.py             # Monitoring appels LLM
python agents/resilience-agent.py status         # État Circuit Breaker
python agents/resilience-agent.py test           # Test fallback chain
python agents/memory-agent.py history            # Historique épisodique
python agents/memory-agent.py context --tc=TC-ID # Contexte formaté pour LLM
python agents/prompt-versioning-agent.py list    # Versions des prompts
python agents/prompt-versioning-agent.py ab-test # A/B test deux versions
python agents/predictive-agent.py predict        # Prédiction failure_probability
python agents/predictive-agent.py gate           # Prédiction Quality Gate
python agents/predictive-agent.py trends         # Tendances historiques
python agents/predictive-agent.py report         # docs/predictive-report.html

# ── JIRA ────────────────────────────────────────────────────────────────────
python agents/status-agent.py sync               # Allure → Jira statuts
python agents/status-agent.py report             # Rapport synchronisation
python agents/sprint-agent.py board              # Tableau Kanban
python agents/sprint-agent.py backlog            # Backlog complet
python agents/jira-agent.py                      # Traçabilité Jira ↔ Features
python agents/jira-ticket-agent.py               # Tickets Bug automatiques
python agents/user-stories-agent.py              # Génère 8 User Stories Jira
python agents/test-case-agent.py                 # Gestion TCs Jira

# ── GIT & GITHUB ────────────────────────────────────────────────────────────
python agents/git-agent.py                       # Commit + push (Conventional Commits LLM)
python agents/git-agent.py --release=v1.4.0      # Commit + push + release
python agents/github-agent.py ci run             # Déclencher CI
python agents/github-agent.py ci watch           # Suivre l'exécution
python agents/github-agent.py pr create          # Créer une PR
python agents/github-agent.py release create v1.4.0
python agents/github-agent.py changelog          # Générer changelog

# ── NOTIFICATIONS ────────────────────────────────────────────────────────────
python agents/notification-agent.py              # Résumé LLM → Slack
python agents/notification-agent.py teams        # Résumé LLM → Teams
python agents/notification-agent.py --dry-run    # Aperçu sans envoi
```

---

## Structure du projet

```
api-pytest-framework/
├── agents/                              # 30 agents IA + 7 modules support
│   │
│   ├── # ── SUPPORT (partagés) ─────────────────────────────
│   ├── llm.py                           # Abstraction LLM (Groq + Ollama fallback)
│   ├── tracer.py                        # Instrumentation appels LLM → JSONL
│   ├── circuit_breaker.py               # Machine d'états 3 niveaux
│   ├── memory_store.py                  # Lecture/écriture mémoire épisodique
│   ├── prompt_store.py                  # Stockage prompts versionnés
│   ├── jira_fetcher_agent.py            # Client Jira REST partagé
│   ├── create_story.py                  # Helper création stories Jira
│   │
│   ├── # ── EXÉCUTION & GÉNÉRATION ─────────────────────────
│   ├── api-spec-agent.py                # Spec → Features Gherkin
│   ├── api-generate-agent.py            # Génération scénarios manquants
│   ├── api-execute-agent.py             # Orchestration exécution
│   ├── api-reporter-agent.py            # Rapport professionnel
│   ├── tc-generator-agent.py            # Génération TCs (Structured Output)
│   ├── qa-agent.py                      # Analyse qualité BDD
│   │
│   ├── # ── ANALYSE IA ─────────────────────────────────────
│   ├── triage-agent.py                  # Classification (Confidence Scoring)
│   ├── rca-agent.py                     # Root Cause Analysis (CoT)
│   ├── bug-analyzer.py                  # Patch automatique (CoT + Structured Output)
│   ├── coverage-agent.py                # Couverture API (CoT)
│   ├── flaky-agent.py                   # Flaky detection + quarantaine Jira
│   ├── verifier-agent.py                # Vérification adversariale
│   │
│   ├── # ── QUALITÉ & PRODUCTION ───────────────────────────
│   ├── smoke-regression-agent.py        # Smoke/Critical/Regression + GO/NO-GO
│   ├── release-advisor-agent.py         # Self-Consistency (×3 votes)
│   ├── kpi-agent.py                     # Dashboard KPI + Quality Gate
│   ├── report-agent.py                  # Pipeline run→rapport complet
│   │
│   ├── # ── RÉSILIENCE & MÉMOIRE ───────────────────────────
│   ├── observability-agent.py           # Monitoring LLM (traces, anomalies)
│   ├── resilience-agent.py              # Circuit Breaker monitoring
│   ├── memory-agent.py                  # Mémoire épisodique (écriture/lecture)
│   ├── prompt-versioning-agent.py       # Semver prompts + A/B testing
│   ├── predictive-agent.py              # Failure probability + tendances
│   │
│   ├── # ── JIRA ────────────────────────────────────────────
│   ├── jira-agent.py                    # Traçabilité + setup projet
│   ├── jira-ticket-agent.py             # Tickets Bug automatiques
│   ├── sprint-agent.py                  # Board/backlog/move
│   ├── status-agent.py                  # Allure → Jira sync
│   ├── user-stories-agent.py            # Génère 8 US dans Jira
│   ├── test-case-agent.py               # Gestion TCs Jira + Gherkin
│   │
│   ├── # ── GIT & GITHUB ────────────────────────────────────
│   │   ├── git-agent.py                 # Commit/Push/Release LLM
│   │   └── github-agent.py              # CI/CD · PR · Release · Changelog
│   │
│   └── # ── NOTIFICATIONS ───────────────────────────────────
│       └── notification-agent.py        # Résumé LLM → Slack / Teams webhook
│
├── memory/                              # Persistance IA
│   ├── episodes.jsonl                   # Historique des runs d'agents (Episodic Memory)
│   └── traces.jsonl                     # Traces des appels LLM (Observability)
│
├── docs/                                # Rapports générés
│   ├── kpi-dashboard.html               # Dashboard KPI (kpi-agent)
│   └── predictive-report.html           # Rapport prédictif (predictive-agent)
│
├── features/                            # Scénarios Gherkin (8 suites)
│   ├── steps/                           # Step definitions Python
│   └── *.feature
├── pages/                               # Page Object Model API
│   ├── base_api.py
│   ├── auth_page.py
│   ├── booking_page.py
│   └── health_page.py
├── tests/                               # Runners pytest-bdd (51 TCs)
├── payloads/                            # Corps de requêtes
├── schemas/                             # JSON Schema validation
├── RAG/                                 # Base de connaissances QA
│   └── qa-knowledge.md
├── .github/workflows/
│   └── ci-api-pytest.yml
├── config.py
├── conftest.py
├── pytest.ini
├── requirements.txt
└── .env.example
```

---

## Couverture de tests

| Suite | TCs | Statut |
|-------|-----|--------|
| Auth (POST /auth) | 5 | ✅ 5 Terminé |
| Health Check (GET /ping) | 3 | ✅ 3 Terminé |
| Booking List (GET /booking) | 5 | ✅ 5 Terminé |
| Booking Get (GET /booking/{id}) | 6 | ✅ 6 Terminé |
| Booking Create (POST /booking) | 8 | ✅ 8 Terminé |
| Booking Update (PUT /booking/{id}) | 8 | ⚠️ 5 Terminé / 3 En cours |
| Booking Patch (PATCH /booking/{id}) | 8 | ✅ 8 Terminé |
| Booking Delete (DELETE /booking/{id}) | 8 | ✅ 8 Terminé |
| **Total** | **51** | **48 ✅ / 3 ⚠️** |

---

## Pourquoi ce framework

| Problème classique | Ce framework |
|--------------------|--------------|
| Triage manuel des échecs (45 min/run) | `triage-agent` classifie en &lt;10s avec score de confiance |
| Chercher la cause racine à la main | `rca-agent` Root Cause Analysis via Chain of Thought |
| Corriger les bugs un par un | `bug-analyzer` génère un patch et l'applique si `safe_to_autofix` |
| Ne pas savoir si un test est flaky | `flaky-agent` calcule un score d'instabilité sur N runs |
| Décision de release subjective | `release-advisor-agent` Self-Consistency (3 votes LLM) |
| Pipeline qui s'arrête si le LLM tombe | `resilience-agent` Circuit Breaker + fallback Ollama |
| Ne pas voir venir les prochains échecs | `predictive-agent` calcule failure_probability par TC |
| Prompts qui changent silencieusement | `prompt-versioning-agent` semver + rollback + A/B test |
| Pas de mémoire entre les runs | `memory-agent` épisodes persistés, injectés dans les prompts |
| Coût LLM invisible | `observability-agent` trace chaque appel (tokens, durée, confiance) |
| Notifier l'équipe après chaque run | `notification-agent` → résumé LLM sur Slack/Teams |
| Mettre à jour Jira manuellement | `status-agent` sync Allure → Jira en 1 commande |
| Créer des commits descriptifs | `git-agent` Conventional Commits via LLM |
| Présenter les KPIs au client | `kpi-agent` → dashboard HTML + widget Allure ENVIRONMENT |

---

*Framework développé avec pytest-bdd · Requests · Groq AI · Ollama · Jira Cloud API · GitHub Actions*
