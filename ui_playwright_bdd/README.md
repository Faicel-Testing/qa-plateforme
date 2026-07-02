# UI Playwright BDD — Framework de test IA

> **Playwright · CucumberJS · TypeScript · Groq AI**  
> Framework BDD auto-piloté : génère, exécute, analyse, répare et documente les tests sans intervention manuelle.

📋 **[Stratégie de test complète →](docs/TEST_STRATEGY.md)**  
🤖 **[Guide agents IA →](agents.md)** — conventions CLAUDE.md, commandes, sécurité

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [10 Agents IA](#10-agents-ia)
4. [4 Modules partagés](#4-modules-partagés)
5. [Patterns LLM avancés](#patterns-llm-avancés)
6. [Suite de tests](#suite-de-tests)
7. [Analyse des coûts LLM](#analyse-des-coûts-llm)
8. [Gardes de coût](#gardes-de-coût)
9. [Circuit Breaker & Cache](#circuit-breaker--cache)
10. [Configuration](#configuration)
11. [Installation](#installation)
12. [Commandes tests](#commandes-tests)
13. [Commandes agents](#commandes-agents)
14. [Structure du projet](#structure-du-projet)
15. [Stack technique](#stack-technique)

---

## Vue d'ensemble

```
Spec métier (Jira)
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    PIPELINE AGENT                           │
  │              Orchestrateur maître — 3 modes                 │
  │         full · quick · report                               │
  └──┬───────┬───────┬───────┬───────┬───────┬───────┬─────────┘
     │       │       │       │       │       │       │
     ▼       ▼       ▼       ▼       ▼       ▼       ▼
  Codegen Runner Quality   CI  Planning Report Advisor Bug
     │       │       │       │       │       │       │   │
     └───────┴───────┴───────┴───────┴───────┴───────┴───┘
                             │
               ┌─────────────▼──────────────┐
               │       MODULES PARTAGÉS      │
               │  llm · tracer · cb · mem    │
               │       prompt-store          │
               └─────────────┬──────────────┘
                             │
                    Observability Agent
                  (métriques · coûts · CB)
```

Un seul `npm run agent:pipeline:full` orchestre l'intégralité du cycle QA.

---

## Architecture

### Séparation des responsabilités

| Couche | Rôle | Fichiers |
|--------|------|----------|
| **Agents** | Logique métier QA, appels LLM | `scripts/agents/*-agent.js` |
| **Modules partagés** | Infrastructure transversale | `scripts/agents/shared/` + `llm.js` |
| **Tests BDD** | Scénarios Gherkin + Steps TypeScript | `src/features/` + `src/steps/` |
| **POM** | Page Object Model | `src/pages/` |
| **Observabilité** | Traces, métriques, cache | `logs/` + `memory/` + `prompts/` |

---

## 10 Agents IA

### codegen-agent — Génération de code

Génère automatiquement les `.feature`, les step definitions TypeScript et les Page Objects depuis les User Stories Jira.

```bash
npm run agent:codegen:spec        # US Jira → fichiers .feature
npm run agent:codegen:steps       # .feature → steps TypeScript
npm run agent:codegen:pages       # .feature → Page Object Model
node scripts/agents/codegen-agent.js gherkin SCRUM-42   # US unique
```

**Technique LLM :** `chatCot` (raisonnement → extraction) + `chatStructured` (JSON garanti)  
**Guard :** `CODEGEN_BATCH=N` limite le nombre d'US par run

---

### runner-agent — Exécution des tests

Lance les tests CucumberJS, détecte les tests flaky par runs répétés, maintient une baseline de régression.

```bash
npm run agent:runner              # Tous les tests
npm run agent:runner:smoke        # @smoke uniquement
npm run agent:runner:critical     # @critical uniquement
npm run agent:runner:flaky        # Détection flaky (3 runs par défaut)
npm run agent:runner:regression   # Comparaison vs baseline
node scripts/agents/runner-agent.js baseline   # Créer la baseline
```

**Technique LLM :** `chat` pour le narratif de résumé (1 appel/run)  
**Flaky threshold :** ≥ 1/3 échecs sur N runs = flaky

---

### quality-agent — Qualité & Analyse

Triage des échecs avec score de confiance, Root Cause Analysis par groupe d'erreur, vérification de cohérence features/steps/allure.

```bash
npm run agent:quality:triage      # Triage IA avec score confiance
npm run agent:quality:rca         # Root Cause Analysis groupée
npm run agent:quality:verify      # Vérification cohérence globale
npm run agent:quality:full        # Triage + RCA + Vérification
```

**Techniques LLM :** `chatConfident` → déclenchement `chatAdversarial` si confiance < seuil · `chatCot` pour RCA  
**Guard :** `CONFIDENCE_THRESHOLD=0.70` — adversarial déclenché seulement si nécessaire (~50% tokens économisés)

---

### ci-agent — CI/CD & Git

Pilote GitHub Actions et Git via les CLI `gh` et `git`. LLM uniquement pour générer les messages de commit, descriptions de PR et release notes.

```bash
npm run agent:ci:status           # État des workflows GitHub Actions
npm run agent:ci:pr               # Créer une Pull Request
npm run agent:ci:git              # Statut git du dépôt
node scripts/agents/ci-agent.js ci run         # Déclencher un workflow
node scripts/agents/ci-agent.js ci watch       # Surveiller l'exécution
node scripts/agents/ci-agent.js release create # Créer une release
node scripts/agents/ci-agent.js git commit     # Commit avec message IA
```

**Technique LLM :** `chat` pour commit/PR/release (1 appel chacun)

---

### planning-agent — Gestion projet

Lit les User Stories et Test Cases Jira, gère les sprints via l'API Agile, analyse la couverture des `.feature`.

```bash
npm run agent:planning:stories    # Lister les US Jira
npm run agent:planning:coverage   # Analyser la couverture .feature
npm run agent:planning:gaps       # Identifier les types manquants
npm run agent:planning:sprint     # Lister les sprints
node scripts/agents/planning-agent.js sprint create "Sprint 4"
node scripts/agents/planning-agent.js sprint start <id>
node scripts/agents/planning-agent.js coverage suggest    # Suggestions LLM
```

**Types de couverture suivis :** `positif · negatif · auth · limite · securite · performance`  
**Technique LLM :** `chat` pour `coverage suggest` uniquement

---

### reporting-agent — Dashboards & Notifications

Génère un dashboard KPI HTML avec Chart.js, envoie des notifications Slack/Teams, synchronise les résultats vers Jira.

```bash
npm run agent:reporting:dashboard # Dashboard KPI HTML (docs/kpi-dashboard.html)
npm run agent:reporting:notify    # Notification Slack Block Kit
npm run agent:reporting:sync      # Poster les résultats dans les tickets Jira
node scripts/agents/reporting-agent.js notify teams   # Notification Teams
```

**Quality Gate :** pass_rate ≥ 90% · fail_rate ≤ 5% · flaky_rate ≤ 20% · coverage ≥ 80%  
**Coût LLM :** nul pour dashboard/sync — 1 appel pour les notifications narratives

---

### advisor-agent — Décision & Prédiction

Vote GO/NO-GO par N LLMs indépendants (self-consistency), prédit les risques par test case, calcule un score qualité global.

```bash
npm run agent:advisor:advise      # Recommandation GO/NO-GO (vote N=3)
npm run agent:advisor:predict     # Prédiction risque par TC
npm run agent:advisor:gate        # Score qualité 0–100
node scripts/agents/advisor-agent.js advise 5    # 5 votes
node scripts/agents/advisor-agent.js history TC-01
node scripts/agents/advisor-agent.js memory recurring
```

**Technique LLM :** `chatSelfConsistent` (N votes, majorité gagne) · `chatStructured` (JSON garanti)  
**Verdict :** `GO | NO-GO` avec blockers, warnings, niveau de risque

---

### observability-agent — Métriques & Coûts

100% déterministe — zéro appel LLM. Lit les traces JSONL et calcule métriques, anomalies, coûts et gère le circuit breaker.

```bash
npm run agent:observability:metrics  # Appels/agent, durée avg, P95, error rate
npm run agent:observability:cost     # Estimation tokens + coût USD par agent
npm run agent:observability:cb       # État circuit breaker
node scripts/agents/observability-agent.js anomalies   # Appels lents, bursts d'erreurs
node scripts/agents/observability-agent.js prompts list
node scripts/agents/observability-agent.js prompts rollback <name>
node scripts/agents/observability-agent.js report  # docs/observability-report.html
```

**Coût LLM : $0.00** — entièrement déterministe

---

### bug-agent — Analyse & Réparation

Boucle agentique avec outils `read_file` / `apply_fix` / `report_analysis`. Lit les fichiers TypeScript, identifie la cause racine, applique des correctifs ciblés.

```bash
npm run agent:bug:analyze         # Boucle agentique (lecture + analyse + fix)
npm run agent:bug:repair          # Réparation automatique (max 5 bugs/session)
npm run agent:bug:report          # Analyse complète + docs/bug-report.html
node scripts/agents/bug-agent.js analyze --max-iter=3   # Limiter les itérations
node scripts/agents/bug-agent.js repair --dry-run       # Simulation
```

**Technique LLM :** `chatCot` + tool use  
**Guard :** `AGENT_MAX_ITER=5` (hard cap 20) — borne la boucle agentique

---

### pipeline-agent — Orchestrateur maître

Invoque les agents dans l'ordre optimal, génère un rapport HTML de pipeline, sauvegarde le résumé dans `logs/pipeline-summary.json`.

```bash
npm run agent:pipeline:full       # Tout : planning → codegen → run → quality → bug → report → advisor → ci
npm run agent:pipeline:quick      # Essentiel : run → triage → dashboard → gate
npm run agent:pipeline:report     # Sans exécution : quality + bug + dashboard + observability
npm run agent:pipeline:status     # Vérifie la présence de tous les agents et artefacts
node scripts/agents/pipeline-agent.js full --dry-run    # Simulation
node scripts/agents/pipeline-agent.js quick --verbose   # Sortie complète
node scripts/agents/pipeline-agent.js full --no-tests   # Saute le runner
```

---

## 4 Modules partagés

### llm.js — Client LLM universel

Détecte automatiquement **Groq** (cloud, gratuit) ou **Ollama** (local, privé).  
Expose 5 patterns avancés en plus du `chat` de base :

| Fonction | Pattern | Usage |
|----------|---------|-------|
| `chat(messages)` | Standard | Appel simple |
| `chatStream(messages)` | Streaming | Affichage temps réel |
| `chatCot(messages)` | Chain of Thought | Raisonnement → extraction (2 appels) |
| `chatStructured(messages, schema)` | JSON forcé | Sortie JSON garantie avec retry (max 3) |
| `chatConfident(messages, threshold)` | Confiance | Score 0–1, trigger adversarial si < seuil |
| `chatAdversarial(messages)` | Adversarial | 3 phases : proposant → critique → arbitre |
| `chatSelfConsistent(messages, schema, N)` | Votes | N LLMs indépendants, majorité gagne |

> **Guard adversarial :** `chatAdversarial` ne se déclenche que si `confidence < CONFIDENCE_THRESHOLD` (~50% tokens économisés sur les cas simples)

### shared/tracer.js — Traces LLM

Enregistre chaque appel LLM dans `logs/traces.jsonl` :

```jsonl
{"ts":"2026-06-14T10:23:11Z","fn":"bugAnalyze","model":"llama-3.3-70b-versatile","durationMs":1842,"promptLen":1240,"responseLen":380,"success":true,"confidence":0.87}
```

API : `record(opts)` · `class Span { begin(), end(success) }` · `loadTraces()` · `clearTraces()`

### shared/circuit-breaker.js — Résilience

Protège tous les appels LLM contre les pannes et la surcharge :

```
CLOSED ──(3 échecs)──► OPEN ──(30s cooldown)──► HALF_OPEN ──(2 succès)──► CLOSED
                          │
                          └──► Cache SHA256 servi (TTL 3600s, max 200 entrées)
```

Fichiers d'état : `logs/circuit_breaker_state.json` · `logs/llm_cache.json`

### shared/memory-store.js — Mémoire épisodique

Persiste l'historique des exécutions dans `memory/episodes.jsonl` :

- `recordEpisode(agent, results, summary)` → id
- `getTcHistory(tcId, lastN=10)` → historique par test case
- `getRecurringFailures(minOccurrences=3)` → failures répétitives
- `getContextFor(tcId)` → string formaté pour injection dans le prompt (trend: ↑↓→)

### shared/prompt-store.js — Versioning des prompts

Versionne les prompts en semver (`1.0.0` → patch/minor/major) dans `prompts/<name>.json` :

- `create(name, content, meta)` · `saveVersion(name, content, note, bump)`
- `get(name, version=null)` · `promote(name, version)` · `rollback(name)`
- `recordUsage(name, confidence)` → confiance moyenne accumulée en production

**8 templates câblés dans les agents** (modifiables sans toucher au code) :

| Template | Agent | Pattern LLM | Variables clés |
|----------|-------|-------------|----------------|
| `triage_classify` | quality-agent | `chatConfident` | test_name, status, error_message, stack_trace, context |
| `rca_analyze` | quality-agent | `chatCot` | count, fail_list |
| `repair_patch` | bug-agent | `chatCot` + tool use | test_name, error_message, stack_trace |
| `release_vote` | advisor-agent | `chatSelfConsistent` | pass_rate, passed, total, failures_count, fail_detail |
| `predict_gate` | advisor-agent | `chatStructured` | test_name, context, count, dominant_category |
| `tc_generate_ui` | codegen-agent | `chatStructured` | us_id, us_title, acceptance_criteria |
| `qa_notify` | reporting-agent | `chat` | run_summary, pass_rate, failed_count |
| `flaky_analyze` | quality-agent | `chat` | flaky_list |

---

## Patterns LLM avancés

### Chain of Thought (chatCot)
Deux appels en séquence : raisonnement libre → extraction structurée. Utilisé pour la RCA et l'analyse de bugs.

### Structured JSON (chatStructured)
Extrait le premier bloc `{...}` de la réponse, valide contre un schéma, retry jusqu'à 3 fois. Utilisé pour la génération de code et les prédictions.

### Confident (chatConfident)
Retourne `{ result, confidence, reasoning, above_threshold }`. Si `confidence < threshold`, l'appelant décide de déclencher `chatAdversarial` (économie ~50% tokens).

### Adversarial (chatAdversarial)
Trois phases avec rôles différents : 1) proposant génère une solution, 2) critique l'évalue, 3) arbitre produit la version finale. Utilisé pour la vérification et le triage critique.

### Self-Consistent (chatSelfConsistent)
N appels indépendants au même LLM, vote majoritaire sur le champ clé (`verdict`, `risk`...). Utilisé pour le GO/NO-GO du release advisor.

---

## Suite de tests

9 domaines fonctionnels couverts · 12 fichiers `.feature` · **35 scénarios** · 100% pass rate

| ID | Feature | Tags | Positif | Négatif |
|----|---------|------|---------|---------|
| Id01 | Inscription (Signup) | `@smoke @critical @regression` | ✅ | ✅ |
| Id02 | Connexion (Login) | `@smoke @critical @regression` | ✅ | ✅ |
| Id03 | Gestion Todo | `@smoke @regression` | ✅ | ✅ |
| Id04 | Suppression Todo | `@regression` | ✅ | ✅ |
| Id05 | Connexion invalide | `@negative @regression` | — | ✅ |
| Id06 | Mise à jour mot de passe | `@profile @security` | ✅ | ✅ |
| Id07 | Mise à jour email | `@profile @contact` | ✅ | ✅ |
| Id08 | Suppression de compte | `@profile @security` | ✅ | ✅ |
| **Id09** ✨ | **API Setup — Pattern Senior** | `@api-setup @smoke @critical @negative @regression` | ✅ | ✅ |

### Répartition par tag

| Tag | Scénarios | Périmètre |
|-----|-----------|-----------|
| `@smoke` | 10 | Flux critiques — signup, login, todo, api-setup |
| `@critical` | 8 | Signup + Login + API Setup |
| `@regression` | 29 | Toutes les features stables (hors @profile) |
| `@negative` | 23 | Cas d'erreur et validations |
| `@api-setup` | 3 | Pattern Senior — préconditions via REST API |
| `@profile` | 6 | Password update · Email update · Account deletion |

**Page Object Model :** `BasePage` · `SignupPage` · `LoginPage` · `TodoPage` · `ProfilePage`  
**Navigateurs :** Chromium · Firefox · multi-browser en parallèle

### Exécution parallèle (`test:headless`)

Le profil `headless` (`@regression and not @wip`) tourne avec `parallel: 2` + `retry: 1` dans `cucumber.js`.  
Chaque scénario a son propre `Browser`/`World` (`src/core/world.ts`) et crée son utilisateur via l'API (`QACartApiClient.register`) plutôt qu'un fichier de fixture partagé — aucune donnée mutable n'est partagée entre workers.

| Paramètre | Valeur | Raison |
|-----------|--------|--------|
| `parallel` | 2 | Calé sur les cœurs physiques disponibles — au-delà, crashs intermittents observés |
| `retry` | 1 | Absorbe les timeouts réseau ponctuels de l'app de démo publique (`qacart-todo.herokuapp.com`) |

### Rapport Allure

![Allure Report](docs/screenshots/allure-report.png)

---

## Analyse des coûts LLM

> Modèle : **llama-3.3-70b-versatile** via Groq  
> Tarif : **$0.59 / M tokens input** · **$0.79 / M tokens output**

### Par commande agent

| Agent | Commande | Tokens estimés | Coût USD | Technique |
|-------|----------|---------------|----------|-----------|
| codegen | `spec` (1 US) | ~2 000 | $0.0017 | chatCot |
| codegen | `steps` (5 features) | ~8 000 | $0.0059 | chatStructured |
| codegen | `pages` (5 features) | ~10 000 | $0.0074 | chatStructured |
| runner | `run` | ~800 | $0.0006 | chat |
| runner | `flaky` (3 runs) | ~2 400 | $0.0018 | chat |
| quality | `triage` (10 TCs) | ~6 000 | $0.0044 | chatConfident |
| quality | `triage` + adversarial | ~12 000 | $0.0088 | chatAdversarial |
| quality | `rca` (5 groupes) | ~10 000 | $0.0074 | chatCot |
| quality | `verify` | ~8 000 | $0.0059 | chatAdversarial |
| ci | `pr create` | ~1 500 | $0.0011 | chat |
| ci | `git commit` | ~500 | $0.0004 | chat |
| planning | `coverage suggest` | ~3 000 | $0.0022 | chat |
| reporting | `notify slack` | ~1 200 | $0.0009 | chat |
| reporting | `dashboard` / `sync` | 0 | **$0.00** | aucun |
| advisor | `advise` (N=3) | ~12 000 | $0.0088 | chatSelfConsistent |
| advisor | `predict` (10 TCs) | ~8 000 | $0.0059 | chatStructured |
| advisor | `gate` | ~2 000 | $0.0017 | chatStructured |
| observability | toutes | 0 | **$0.00** | aucun |
| bug | `analyze` (1 bug, 5 iter) | ~15 000 | $0.0110 | chatCot + tool use |
| bug | `repair` (1 bug) | ~10 000 | $0.0074 | tool use |

### Par pipeline

| Pipeline | Agents | Tokens totaux | Coût total |
|----------|--------|--------------|------------|
| `pipeline:quick` | runner + quality:triage + reporting:dashboard + advisor:gate | ~12 000 | **~$0.009** |
| `pipeline:report` | quality:full + bug:report + reporting:dashboard + observability:report | ~20 000 | **~$0.015** |
| `pipeline:full` | tous les agents | ~35 000 | **~$0.025** |

> **Limite gratuite Groq :** 14 400 req/jour · 500 000 tokens/min → pipelines illimités en pratique.

---

## Gardes de coût

Trois gardes intégrés dans le code — configurables via variables d'environnement :

| Guard | Variable env | Défaut | Effet |
|-------|-------------|--------|-------|
| **Boucle agentique** | `AGENT_MAX_ITER=N` | 5 | Borne max des itérations bug-agent (hard cap: 20) |
| **Adversarial conditionnel** | `CONFIDENCE_THRESHOLD=0.XX` | 0.70 | Déclenche chatAdversarial uniquement si confiance < seuil |
| **Batch génération** | `CODEGEN_BATCH=N` | 0 (illimité) | Limite le nombre d'US traitées par run codegen |

**Option `--dry-run`** disponible sur tous les agents : simule sans écrire ni appeler le LLM.

---

## Circuit Breaker & Cache

Le module `shared/circuit-breaker.js` est branché sur tous les agents :

| Paramètre | Valeur |
|-----------|--------|
| Seuil d'ouverture | 3 échecs consécutifs |
| Seuil de fermeture | 2 succès en HALF_OPEN |
| Cooldown | 30 secondes |
| TTL cache | 3 600 secondes (1h) |
| Max entrées cache | 200 |
| Clé cache | SHA256 du tableau `messages` |

```bash
npm run agent:observability:cb        # Voir l'état
node scripts/agents/observability-agent.js cb reset    # Réinitialiser
node scripts/agents/observability-agent.js cb cache    # Vider le cache
```

---

## Configuration

```bash
cp .env.example .env
```

```env
# LLM (obligatoire — choisir l'un ou l'autre)
GROQ_API_KEY=gsk_...               # Gratuit sur console.groq.com
OLLAMA_BASE_URL=http://localhost:11434   # Ollama local (fallback auto)

# Jira (pour planning, codegen, reporting)
JIRA_BASE_URL=https://monsite.atlassian.net
JIRA_EMAIL=user@company.com
JIRA_TOKEN=ATATT...                # id.atlassian.com → Security → API tokens
JIRA_PROJECT=SCRUM

# GitHub (pour ci-agent)
GITHUB_TOKEN=ghp_...
GITHUB_OWNER=mon-org
GITHUB_REPO=mon-repo

# Application sous test
BASE_URL=http://localhost:3000
TEST_BROWSER=chromium              # chromium | firefox
TEST_HEADLESS=true

# Gardes de coût
AGENT_MAX_ITER=5
CONFIDENCE_THRESHOLD=0.70
CODEGEN_BATCH=0                    # 0 = toutes les US
```

---

## Installation

```bash
# Prérequis : Node.js >= 18
npm install
npx playwright install chromium firefox

# Vérifier la configuration LLM
node scripts/agents/llm.js         # Doit afficher le modèle détecté

# Vérifier tous les agents
npm run agent:pipeline:status
```

---

## Commandes tests

### Tests BDD

```bash
npm test                           # Tous les tests (format progress)
npm run test:retry                 # Avec retry automatique (--retry 1)
npm run test:allure                # Tests + rapport Allure
npm run test:allure:retry          # Tests + retry + rapport Allure

# Par tag
npx cucumber-js --tags "@regression and not @wip"   # Suite principale CI
npx cucumber-js --tags "@smoke"                     # Smoke rapide
npx cucumber-js --tags "@api-setup"                 # Pattern Senior uniquement
npx cucumber-js --tags "@profile"                   # Profil (Id06/07/08)
npx cucumber-js --tags "@critical"                  # Critiques uniquement
```

### Multi-navigateur

```bash
npm run test:allure:chrome         # Chromium headless
npm run test:allure:firefox        # Firefox headless
npm run test:headed:chrome         # Chromium avec fenêtre
npm run test:headed:firefox        # Firefox avec fenêtre
npm run test:multibrowser          # Chrome + Firefox en parallèle
npm run test:parallel              # Chrome + Firefox en parallel workers
```

### Par environnement

```bash
npm run test:local                 # ENV=local
npm run test:staging               # ENV=staging
npm run test:prod                  # ENV=prod
npm run test:staging:firefox       # ENV=staging + Firefox
```

### Rapports Allure

```bash
npm run allure:generate            # Générer le rapport
npm run allure:open                # Ouvrir dans le navigateur
npm run allure:report              # generate + open
npm run allure:merge               # Fusionner multi-browser results
npm run dashboard:browser          # Dashboard HTML interactif
npm run dashboard:flaky            # Dashboard tests flaky
```

### Nettoyage

```bash
npm run clean                      # Tout nettoyer
npm run clean:results              # Résultats Allure uniquement
npm run clean:report               # Rapport Allure uniquement
```

---

## Commandes agents

### Génération de code

```bash
npm run agent:codegen:spec         # US Jira → .feature
npm run agent:codegen:steps        # .feature → steps TypeScript
npm run agent:codegen:pages        # .feature → Page Object Model
```

### Exécution & détection

```bash
npm run agent:runner               # Tous les tests
npm run agent:runner:smoke         # Tag @smoke
npm run agent:runner:critical      # Tag @critical
npm run agent:runner:flaky         # Détection tests instables
npm run agent:runner:regression    # Régression vs baseline
```

### Qualité & Analyse

```bash
npm run agent:quality:triage       # Triage IA des échecs
npm run agent:quality:rca          # Root Cause Analysis
npm run agent:quality:verify       # Cohérence features/steps/allure
npm run agent:quality:full         # Triage + RCA + Vérification
```

### Bugs & Réparation

```bash
npm run agent:bug:analyze          # Boucle agentique (lit, analyse, corrige)
npm run agent:bug:repair           # Réparation automatique des fichiers .ts
npm run agent:bug:report           # Rapport HTML des bugs
```

### CI/CD & Git

```bash
npm run agent:ci:status            # Workflows GitHub Actions
npm run agent:ci:pr                # Créer une Pull Request
npm run agent:ci:git               # Statut git
```

### Planning & Jira

```bash
npm run agent:planning:stories     # User Stories du projet
npm run agent:planning:coverage    # Couverture des .feature
npm run agent:planning:gaps        # Types de test manquants
npm run agent:planning:sprint      # Liste des sprints
```

### Reporting & Notifications

```bash
npm run agent:reporting:dashboard  # Dashboard KPI HTML
npm run agent:reporting:notify     # Notification Slack
npm run agent:reporting:sync       # Résultats → commentaires Jira
```

### Décision & Prédiction

```bash
npm run agent:advisor:advise       # Vote GO/NO-GO (N=3 LLMs)
npm run agent:advisor:predict      # Prédiction risque par TC
npm run agent:advisor:gate         # Score qualité 0–100
```

### Observabilité

```bash
npm run agent:observability:metrics   # Métriques par agent
npm run agent:observability:cost      # Estimation coût LLM
npm run agent:observability:cb        # État circuit breaker
```

### Pipeline complet

```bash
npm run agent:pipeline:full        # Planning → Codegen → Run → Quality → Bug → Report → Advisor → CI
npm run agent:pipeline:quick       # Run → Triage → Dashboard → Gate
npm run agent:pipeline:report      # Analyse + Dashboards (sans exécution)
npm run agent:pipeline:status      # État de santé de tous les agents
```

---

## Structure du projet

```
ui_playwright_bdd/
│
├── scripts/
│   └── agents/                      Couche IA
│       ├── llm.js                   Client LLM (Groq/Ollama) + 7 patterns
│       ├── jira-fetcher.js          Client Jira REST v3
│       ├── shared/
│       │   ├── tracer.js            Traces JSONL de tous les appels LLM
│       │   ├── circuit-breaker.js   Résilience + cache SHA256
│       │   ├── memory-store.js      Mémoire épisodique JSONL
│       │   └── prompt-store.js      Versioning sémantique des prompts
│       ├── codegen-agent.js         Génération specs / steps / POM
│       ├── runner-agent.js          Exécution + détection flaky
│       ├── quality-agent.js         Triage + RCA + Vérification
│       ├── ci-agent.js              GitHub Actions + Git
│       ├── planning-agent.js        Stories + Sprints + Couverture
│       ├── reporting-agent.js       Dashboard + Notifications + Jira sync
│       ├── advisor-agent.js         GO/NO-GO + Prédiction risques
│       ├── observability-agent.js   Métriques + Coûts + CB + Prompts
│       ├── bug-agent.js             Analyse + Réparation automatique
│       └── pipeline-agent.js        Orchestrateur maître
│
├── src/
│   ├── api/                         Client HTTP pour les préconditions (API Setup pattern)
│   │   └── QACartApiClient.ts       POST register/login — Playwright request, ignoreHTTPSErrors
│   ├── features/                    Scénarios Gherkin (Id01–Id09) · 12 fichiers · 35 scénarios
│   │   ├── Id01_SignupTest.feature
│   │   ├── Id01_SignupNegativeTest.feature
│   │   ├── Id02_LoginTest.feature
│   │   ├── Id03_TodoTest.feature
│   │   ├── Id03_TodoNegativeTest.feature
│   │   ├── Id04_DeleteTodoTest.feature
│   │   ├── Id04_DeleteTodoNegativeTest.feature
│   │   ├── Id05_LoginNegativeTest.feature
│   │   ├── Id06_PasswordUpdate.feature
│   │   ├── Id07_EmailUpdate.feature
│   │   ├── Id08_AccountDeletion.feature
│   │   └── Id09_ApiSetupTest.feature  ← Pattern Senior @api-setup @regression
│   ├── steps/                       Step definitions TypeScript (1 fichier / feature)
│   ├── pages/                       Page Object Model
│   │   ├── BasePage.ts
│   │   ├── Id01_SignupPage.ts
│   │   ├── Id02_LoginPage.ts
│   │   ├── Id03_TodoPage.ts
│   │   └── ProfilePage.ts           ← Password · Email · Account deletion
│   ├── core/
│   │   ├── world.ts                 CucumberJS World (Playwright context)
│   │   └── driver.ts               Gestionnaire navigateur
│   ├── hooks/
│   │   └── hooks.ts                Before/After Allure + screenshots
│   ├── config/
│   │   ├── env.ts                  Variables d'environnement
│   │   └── playwright.config.ts
│   ├── fixtures/
│   │   └── user.json               Données de test
│   ├── support/
│   │   ├── selectors.ts            Sélecteurs CSS centralisés
│   │   └── testData.ts             Données de test TypeScript (randomUser)
│   └── utils/
│       ├── allure-executor.ts
│       ├── execution-metrics.ts
│       ├── retry-manager.ts
│       └── smart-retry.ts
│
├── logs/
│   ├── traces.jsonl                 Traces LLM (durée, tokens, confiance)
│   ├── circuit_breaker_state.json  État CB (CLOSED/OPEN/HALF_OPEN)
│   └── llm_cache.json              Cache SHA256 des réponses LLM
│
├── memory/
│   └── episodes.jsonl              Historique épisodique par agent/TC
│
├── prompts/                         8 prompt templates versionnés (semver)
│   ├── triage_classify.json         Triage Playwright (4 catégories + confiance)
│   ├── rca_analyze.json             Root Cause Analysis groupée
│   ├── repair_patch.json            Patch correctif automatique TypeScript
│   ├── release_vote.json            Décision GO/NO-GO release
│   ├── predict_gate.json            Prédiction risque futur par test
│   ├── tc_generate_ui.json          Génération scénarios BDD UI
│   ├── qa_notify.json               Notifications QA narratives
│   └── flaky_analyze.json           Analyse flakiness UI
├── docs/                            Rapports HTML générés
├── allure-results/                  Résultats bruts Allure
├── allure-report/                   Rapport Allure généré
├── specs/                           Spécifications métier source
├── RAG/                             Base de connaissances QA
├── cucumber.js                      Configuration CucumberJS
├── tsconfig.json                    Configuration TypeScript
└── .env.example                     Template de configuration
```

---

## API Setup Pattern (Senior)

> Les préconditions de test ne passent **jamais** par l'UI signup.

```typescript
// Id09_ApiSetupSteps.ts
Given('I have a user created via API', async function (this: CustomWorld) {
  const user = randomUser();
  const token = await new QACartApiClient().register(user); // POST /api/v1/users/register
  this.user  = user;
  this.apiToken = token;
  // Utilisateur scopé au World (pas de fichier partagé) → parallel-safe
  // Token visible dans les logs CI → preuve de l'appel REST
});
```

`QACartApiClient` utilise **`playwright/test request.newContext()`** (built-in, zéro dépendance ajoutée)  
avec `ignoreHTTPSErrors: true` → bypass proxy corporate SSL.

| | Sans API Setup | Avec API Setup |
|---|---|---|
| Création user | UI Signup (3-5s, fragile) | `POST /api/v1/users/register` (300ms) |
| Dépendance | Tests Login dépendent de Signup | Isolation totale |
| Si Signup cassé | Login + Todo échouent | Login + Todo passent quand même |

---

## CI/CD — GitHub Actions

Workflow `.github/workflows/ci-playwright.yml` déclenché sur :
- Push sur `main` (path : `ui_playwright_bdd/**`)
- Pull Request vers `main`
- Dispatch manuel
- Planification hebdomadaire (dimanche 08h00 UTC)

**Étapes :**
1. Checkout + Node.js 20
2. `npm ci` + `npx playwright install --with-deps chromium`
3. `cucumber-js --tags "@regression and not @wip"` (Chrome headless, 20min timeout)
4. Génération rapport Allure
5. Upload artefacts (rapport + traces + screenshots)
6. Job Summary avec pass rate calculé

```bash
# Variable secrète GitHub à configurer :
# Settings → Secrets → Actions → GROQ_API_KEY
```

---

## Stack technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Tests BDD | CucumberJS | ^11.3 |
| Browser | Playwright | ^1.59 |
| Langage tests | TypeScript | ^6.0 |
| LLM cloud | Groq (llama-3.3-70b-versatile) | gratuit 14 400 req/j |
| LLM local | Ollama | fallback auto |
| SDK LLM | groq-sdk + @anthropic-ai/sdk | dernière |
| Reporting | Allure + Chart.js | ^2.38 |
| Gestion projet | Jira REST API v3 + Agile API | Cloud |
| CI/CD | GitHub Actions CLI (gh) | — |
| Runtime | Node.js | >= 18 |

---

*Framework QA développé avec Playwright, CucumberJS, Groq AI et des patterns LLM avancés.*
