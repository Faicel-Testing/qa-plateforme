# Mobile — Appium + TestNG (Android)

> Framework de tests E2E mobile natif pour Android, avec agents IA pour le triage, l'analyse de flaky tests et la génération de rapports.

---

## Stack

- **Appium** (java-client) + Selenium BOM — pilotage natif Android
- **TestNG 7.9** — orchestration, retry, listeners
- **Java 17** + Maven
- **Allure 2** — reporting
- **Agents IA** : Python (Groq / Ollama fallback)

## Application testée

**Sauce Labs "My Demo App"** — app Android open-source de démo e-commerce (`com.saucelabs.mydemoapp.android`), APK embarqué dans `src/test/resources/apps/my-demo-app.apk`.

## Scope — 6 parcours E2E

| Test | Parcours |
|---|---|
| `Test01_Login` | Connexion utilisateur |
| `Test02_Catalog` | Navigation catalogue produits |
| `Test03_ProductDetail` | Fiche produit |
| `Test04_Cart` | Panier |
| `Test05_Checkout` | Tunnel de paiement (adresse → paiement → confirmation) |
| `Test06_Navigation` | Menu de navigation |

Parcours e-commerce complet du login jusqu'à la confirmation de commande.

## Exécution locale

Prérequis : Android SDK + émulateur (ou device réel) démarré, serveur Appium lancé.

```bash
appium --base-path /wd/hub --port 4723

mvn clean test -Denv=qa -Dudid=<device-id> -Dsurefire.suiteXmlFiles=testng.xml
```

Configuration par environnement : `src/test/resources/config/{qa,staging}.properties`, surchargeable via `-Dkey=value` ou variables d'environnement.

## Retry automatique

`RetryAnalyzer` / `RetryTransformer` / `RetryRules` — relance automatique des scénarios flaky (jusqu'à 2x) au niveau TestNG.

## Agents IA — `agents/`

| Agent | Rôle |
|---|---|
| `triage-agent.py` | Classification des échecs |
| `rca-agent.py` | Root cause analysis |
| `flaky-agent.py` | Détection des tests instables |
| `release-advisor-agent.py` | Recommandation GO/NO-GO |
| `kpi-agent.py` | Indicateurs qualité |
| `spec-generator-agent.py` | Génération de specs de test |
| `userstory-generator-agent.py` | Génération de user stories |
| `notification-agent.py` | Notifications Slack/Teams |
| `jira-ticket-agent.py` / `jira-project-agent.py` / `jira_fetcher_agent.py` | Intégration Jira |

Variables requises : voir `.env.example` (clé Groq, config Jira, webhooks Slack/Teams).

## CI/CD

`.github/workflows/ci-mobile.yml` :
- **À chaque push/PR** : compilation Maven (validation rapide, sans device).
- **Sur déclenchement manuel** (`workflow_dispatch`, `run_emulator=true`) : provisionne un émulateur Android (API 30, Pixel 5), démarre Appium, exécute la suite TestNG complète.

L'exécution complète sur émulateur est volontairement manuelle plutôt qu'automatique sur chaque PR — un run Appium + émulateur prend plusieurs minutes, ce qui n'est pas adapté à une gate bloquante de PR.

## Reporting

```bash
mvn allure:report
mvn allure:serve
```

---

Le reste de l'architecture (quality gates, secteurs couverts, positionnement) est décrit dans le [README racine](../../README.md).
