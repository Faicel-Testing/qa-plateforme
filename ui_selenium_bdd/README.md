# ui_selenium_bdd

**Selenium 4 · Cucumber 7 · TestNG 7.9 · Java 17 · Maven**  
Application sous test : [automationexercise.com](https://automationexercise.com) — 26 cas de test  
Agents IA : 10 agents Python · 6 patterns LLM · 8 prompts versionnés

🤖 [Guide agents IA →](agents.md)

---

## Stack technique

| Couche | Technologie |
|---|---|
| Langage | Java 17 |
| Automation | Selenium 4.12.1 |
| BDD | Cucumber 7.14.0 |
| Runner | TestNG 7.9.0 |
| Build | Maven |
| Rapport | Allure 2.24 |
| Agents IA | Python 3.11+ · Groq LLM |

---

## Structure du projet

```
ui_selenium_bdd/
├── src/
│   └── test/
│       ├── java/com/qacart/todo/
│       │   ├── factory/      → DriverFactory, BrowserFactory
│       │   ├── hooks/        → Cucumber Hooks (screenshot, cleanup)
│       │   ├── pages/        → Page Objects (générés par codegen-agent)
│       │   ├── runners/      → TestNG runners (@smoke, @critical, @regression)
│       │   ├── steps/        → Step Definitions (générés par codegen-agent)
│       │   └── utils/        → ElementActions, Waiter, ScenarioContext
│       └── resources/
│           ├── features/     → Fichiers .feature Gherkin
│           ├── properties/   → local / staging / production
│           └── quarantine/   → Tests mis en quarantaine
├── agents/                   → 10 agents Python IA
├── prompts/                  → 8 templates LLM versionnés
├── docs/                     → Dashboards HTML générés
├── logs/                     → Traces, circuit breaker, cache LLM
├── memory/                   → Mémoire épisodique agents
├── pom.xml
├── testng.xml
├── agents.md                 → Guide complet agents IA
└── .env.example
```

---

## Installation

```bash
# Dépendances Java/Maven
mvn dependency:resolve

# Dépendances Python (agents IA)
pip install groq requests python-dotenv

# Configuration
cp .env.example .env
# → Remplir GROQ_API_KEY dans .env
```

---

## Exécution des tests

```bash
# Tous les tests
mvn clean test

# Par tag
mvn clean test -Dcucumber.filter.tags="@smoke"
mvn clean test -Dcucumber.filter.tags="@critical"
mvn clean test -Dcucumber.filter.tags="@regression"

# Par navigateur
mvn clean test -Dbrowser=firefox
mvn clean test -Dbrowser=chrome

# Par environnement
mvn clean test -Denv=staging
mvn clean test -Denv=production

# Rapport Allure
mvn allure:serve
```

---

## Agents IA — Démarrage rapide

```bash
# Vue d'ensemble du framework
python agents/pipeline-agent.py status

# Pipeline smoke (le plus rapide)
python agents/pipeline-agent.py smoke

# Pipeline complet
python agents/pipeline-agent.py full

# Générer feature + steps + page pour un TC
python agents/codegen-agent.py full --tc 1

# Voir les 26 TCs et leur statut
python agents/planning-agent.py tc

# Triage automatique des échecs
python agents/bug-agent.py triage

# Vote GO/NO-GO release
python agents/advisor-agent.py release
```

---

## 10 agents Python

| Agent | Rôle | Commandes clés |
|---|---|---|
| `pipeline-agent.py` | Orchestrateur maître | `full`, `quick`, `smoke`, `nightly` |
| `runner-agent.py` | Exécution Maven | `run`, `smoke`, `critical`, `flaky` |
| `codegen-agent.py` | Génération Java IA | `feature`, `steps`, `page`, `full` |
| `bug-agent.py` | Triage + RCA + patch | `triage`, `rca`, `repair`, `loop` |
| `quality-agent.py` | KPI + gate + flaky | `analyze`, `kpi`, `gate`, `verify` |
| `advisor-agent.py` | Vote GO/NO-GO | `release`, `predict`, `recommend` |
| `reporting-agent.py` | Allure + Slack/Teams | `generate`, `publish`, `notify` |
| `planning-agent.py` | Coverage 26 TCs + Jira | `tc`, `coverage`, `gaps`, `sync` |
| `ci-agent.py` | Git + GitHub Actions | `commit`, `push`, `pr`, `release` |
| `observability-agent.py` | Traces + coûts + prompts | `traces`, `metrics`, `cost`, `circuit` |

---

## 6 patterns LLM

| Pattern | Usage |
|---|---|
| `chat` | Réponse directe (génération feature, notification) |
| `chat_cot` | Chain-of-Thought (RCA, analyse root cause) |
| `chat_structured` | JSON typé (triage, vote release) |
| `chat_confident` | Avec score de confiance (prédiction gate) |
| `chat_self_consistent` | Consensus 3 appels (analyse flaky) |
| `chat_adversarial` | Critique croisée (vérification cohérence) |

---

## Prompts versionnés — `prompts/`

| Template | Agent | Pattern LLM |
|---|---|---|
| `triage_classify.json` | bug-agent | structured |
| `rca_analyze.json` | bug-agent | cot |
| `repair_patch.json` | bug-agent | structured |
| `tc_generate.json` | codegen-agent | chat |
| `release_vote.json` | advisor-agent | structured |
| `predict_gate.json` | advisor-agent | confident |
| `flaky_analyze.json` | quality-agent | self_consistent |
| `qa_notify.json` | reporting-agent | chat |

```bash
# Gestion des prompts
python agents/observability-agent.py prompts list
python agents/observability-agent.py prompts rollback triage_classify
python agents/observability-agent.py prompts versions rca_analyze
```

---

## 26 cas de test — automationexercise.com

| Tag | TCs | Description |
|---|---|---|
| `@smoke` | TC1, TC2, TC8, TC9 | Flux critiques de base |
| `@critical` | TC12, TC14, TC15, TC16 | Panier + commandes |
| `@auth` | TC1–TC5 | Inscription, login, logout |
| `@order` | TC14–TC16, TC23, TC24 | Parcours d'achat complet |
| `@cart` | TC11–TC13, TC17, TC20, TC22 | Gestion du panier |
| `@negative` | TC3, TC5 | Cas d'erreur |

```bash
# Générer des TCs manquants
python agents/planning-agent.py gaps
python agents/codegen-agent.py full --tc 3 4 5
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
GROQ_API_KEY=gsk_...          # Obligatoire pour les agents IA
SLACK_WEBHOOK_URL=https://... # Notifications Slack
TEAMS_WEBHOOK_URL=https://... # Notifications Teams
JIRA_URL=https://...          # Intégration Jira
JIRA_EMAIL=...
JIRA_TOKEN=...
```

> `.env` ne doit **jamais** être commité. `ci-agent.py` bloque automatiquement tout stage de fichiers sensibles.
