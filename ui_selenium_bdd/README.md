# ui_selenium_bdd

**Selenium 4 · Cucumber 7 · TestNG 7.9 · Java 17 · Maven**  
Application sous test : [QACart Todo](https://qacart-todo.herokuapp.com) — 8 features · 26 scénarios  
Agents IA : 10 agents Python · 6 patterns LLM · 8 prompts versionnés

> Guide complet des agents → [agents.md](agents.md)

---

## Stack technique

| Couche | Technologie | Version |
|---|---|---|
| Langage | Java | 17 |
| Automation | Selenium | 4.12.1 |
| BDD | Cucumber | 7.14.0 |
| Runner | TestNG | 7.9.0 |
| Build | Maven | 3.x |
| Rapport | Allure | 2.24.0 |
| Driver management | WebDriverManager | 5.8.0 |
| Agents IA | Python + Groq LLM | 3.11+ |

---

## Structure du projet

```
ui_selenium_bdd/
├── src/test/
│   ├── java/com/qacart/todo/
│   │   ├── context/          → TestContext (ThreadLocal)
│   │   ├── data/             → User.java, FixtureStore.java
│   │   ├── factory/          → DriverManager, DriverFactory, BrowserOptionsFactory
│   │   ├── hooks/            → Cucumber Hooks (screenshot, quarantaine, cleanup)
│   │   ├── pages/            → Page Objects (LoginPage, SignupPage, TodoPage)
│   │   ├── steps/
│   │   │   ├── AuthSteps.java
│   │   │   ├── TodoSteps.java
│   │   │   ├── CommonSteps.java
│   │   │   ├── ProfileSteps.java
│   │   │   ├── runners/      → RunnerTest, ChromeRunnerTest, FirefoxRunnerTest, ParallelRunnerTest
│   │   │   └── utils/        → ElementActions, Waiter, EnvUtils, TestDataFactory
│   │   └── utilss/           → RunConfig
│   └── resources/
│       ├── features/         → 8 fichiers .feature Gherkin (Id01–Id08)
│       ├── properties/       → local.properties, staging.properties, production.properties
│       └── data/             → Fixtures JSON
├── agents/                   → 10 agents Python IA
├── prompts/                  → 8 templates LLM versionnés
├── docs/                     → Dashboards HTML générés
├── logs/                     → Traces JSONL, circuit breaker, cache LLM
├── pom.xml
├── testng.xml                → Config parallèle Chrome + Firefox
├── agents.md                 → Architecture complète des agents
└── .env.example
```

---

## Prérequis

- Java 17+
- Maven 3.x
- Python 3.11+
- Firefox + GeckoDriver **ou** Chrome + ChromeDriver (géré automatiquement par WebDriverManager)
- Clé API Groq (pour les agents IA)

---

## Installation

```bash
# Dépendances Java
mvn dependency:resolve

# Dépendances Python (agents IA)
pip install groq requests python-dotenv

# Configuration
cp .env.example .env
# Remplir GROQ_API_KEY dans .env
```

---

## Exécution des tests

> **PowerShell** : encadrer le paramètre `-D` entre guillemets doubles

```powershell
# Tous les tests
mvn test

# Par tag
mvn test "-Dcucumber.filter.tags=@smoke"
mvn test "-Dcucumber.filter.tags=@regression"
mvn test "-Dcucumber.filter.tags=@negative"

# Par navigateur
mvn test -Dbrowser=firefox
mvn test -Dbrowser=chrome

# Par environnement
mvn test -Denv=staging
mvn test -Denv=production

# Smoke + rapport Allure en une commande
mvn test "-Dcucumber.filter.tags=@smoke" ; python agents/reporting-agent.py generate ; python agents/reporting-agent.py serve
```

---

## Features & Tags

| Feature | Tags | Scénarios |
|---|---|---|
| Id01 — Signup | `@smoke @regression @critical` | Inscription valide |
| Id01 — Signup Negative | `@negative @regression` | Mots de passe non correspondants, champs manquants, format invalide |
| Id02 — Login | `@smoke @regression @critical` | Connexion valide |
| Id03 — Todo | `@smoke @regression` | Ajout d'un todo |
| Id03 — Todo Negative | `@negative @regression` | Todo vide, whitespace, trop long, après déconnexion |
| Id04 — Delete Todo | `@regression` | Suppression d'un todo |
| Id04 — Delete Negative | `@negative @regression` | Suppression inexistante, doublon, après déconnexion |
| Id05 — Login Negative | `@negative @regression` | Email invalide, email vide, mot de passe vide |
| Id06 — Password Update | `@wip @security` | *(en cours)* |
| Id07 — Email Update | `@wip @contact` | *(en cours)* |
| Id08 — Account Deletion | `@wip @security` | *(en cours)* |

**Résumé tags :**

| Tag | Périmètre |
|---|---|
| `@smoke` | Flux critiques (signup, login, todo) |
| `@regression` | Toutes les features stables (Id01–Id05) |
| `@negative` | Cas d'erreur et validations |
| `@critical` | Signup + Login |
| `@wip` | Features en développement (Id06–Id08) |

---

## Rapport Allure

```powershell
# Générer le rapport HTML
python agents/reporting-agent.py generate

# Ouvrir dans le navigateur
python agents/reporting-agent.py serve

# Générer + dashboard KPI + notifier Slack
python agents/reporting-agent.py publish

# Dashboard KPI seul
python agents/reporting-agent.py dashboard
```

---

## 10 agents IA

| Agent | Rôle | Commandes clés |
|---|---|---|
| `pipeline-agent.py` | Orchestrateur maître | `full` `quick` `smoke` `nightly` `gate` `status` |
| `runner-agent.py` | Exécution Maven + détection flaky | `run` `smoke` `critical` `regression` `flaky` `baseline` |
| `codegen-agent.py` | Génération Java/Gherkin par LLM | `feature` `steps` `page` `full` `tc` |
| `bug-agent.py` | Triage + RCA + auto-repair | `triage` `rca` `repair` `loop` `report` |
| `quality-agent.py` | KPI + gate + analyse flaky | `analyze` `kpi` `flaky` `gate` `verify` |
| `advisor-agent.py` | Vote GO/NO-GO release | `release` `predict` `recommend` `report` |
| `reporting-agent.py` | Allure + dashboards + notifications | `generate` `serve` `notify` `dashboard` `publish` |
| `planning-agent.py` | Coverage TCs + sync Jira | `tc` `coverage` `gaps` `stories` `sync` |
| `ci-agent.py` | Git + GitHub Actions + changelog | `commit` `push` `pr` `release` `changelog` |
| `observability-agent.py` | Traces + coûts LLM + circuit breaker | `traces` `metrics` `cost` `circuit` `prompts list` |

### Démarrage rapide agents

```powershell
# Statut général
python agents/pipeline-agent.py status

# Pipeline smoke (rapide)
python agents/pipeline-agent.py smoke

# Pipeline complet
python agents/pipeline-agent.py full

# Triage automatique des échecs
python agents/bug-agent.py triage

# Analyse Root Cause
python agents/bug-agent.py rca

# Vote release GO/NO-GO
python agents/advisor-agent.py release

# Voir les TCs et couverture
python agents/planning-agent.py tc
python agents/planning-agent.py gaps
```

---

## 6 patterns LLM

| Pattern | Usage |
|---|---|
| `chat` | Réponse directe (génération feature, notification) |
| `chat_cot` | Chain-of-Thought (RCA, analyse root cause) |
| `chat_structured` | JSON typé (triage échecs, vote release) |
| `chat_confident` | Avec score de confiance (prédiction quality gate) |
| `chat_self_consistent` | Consensus 3 appels (analyse flaky) |
| `chat_adversarial` | Critique croisée (vérification cohérence) |

---

## 8 prompts versionnés

| Template | Agent | Pattern |
|---|---|---|
| `triage_classify.json` | bug-agent | structured |
| `rca_analyze.json` | bug-agent | cot |
| `repair_patch.json` | bug-agent | structured |
| `tc_generate.json` | codegen-agent | chat |
| `release_vote.json` | advisor-agent | structured |
| `predict_gate.json` | advisor-agent | confident |
| `flaky_analyze.json` | quality-agent | self_consistent |
| `qa_notify.json` | reporting-agent | chat |

```powershell
# Gestion des versions de prompts
python agents/observability-agent.py prompts list
python agents/observability-agent.py prompts versions rca_analyze
python agents/observability-agent.py prompts rollback triage_classify
```

---

## Quality Gate

| Métrique | Seuil |
|---|---|
| Pass rate | ≥ 90% |
| Fail rate | ≤ 5% |
| Confiance LLM | ≥ 0.70 |

---

## Variables d'environnement

```bash
# Obligatoire pour les agents IA
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# Notifications (optionnel)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
TEAMS_WEBHOOK_URL=https://outlook.office.com/...

# Jira (optionnel)
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=user@example.com
JIRA_TOKEN=...
```

> `.env` ne doit **jamais** être commité. `ci-agent.py` bloque automatiquement le staging de fichiers sensibles.

---

## CI/CD — GitHub Actions

Le workflow `.github/workflows/main.yml` se déclenche sur :
- Push sur `main`
- Pull Request
- Dispatch manuel
- Planification hebdomadaire (dimanche 08h00 UTC)

**Étapes :**
1. Checkout + JDK 17
2. Attente Selenium Grid (port 4444)
3. `mvn clean test` (mode headless)
4. Génération rapport Allure
5. Upload artefacts
6. Notification email (Gmail SMTP)
