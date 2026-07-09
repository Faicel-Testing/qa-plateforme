# agents.md — UI Playwright BDD Framework

Ce fichier décrit comment les agents IA interagissent avec ce framework.
Convention inspirée de `CLAUDE.md` (Anthropic) — lisible par tout agent LLM.

---

## Ce que fait ce framework

Tests UI BDD (Playwright + Cucumber + TypeScript) pour l'application **QACart Todo**
(qacart-todo.herokuapp.com) — 29 scénarios Gherkin couvrant Signup, Login, Todo, Delete Todo, API Setup.

---

## Commandes disponibles

### Exécuter des tests

```bash
node scripts/agents/runner-agent.js smoke         # Tests @smoke (rapide)
node scripts/agents/runner-agent.js critical      # Tests @critical
node scripts/agents/runner-agent.js regression    # Suite complète
node scripts/agents/runner-agent.js gono-go       # Smoke + Critical + analyse LLM
node scripts/agents/runner-agent.js baseline      # Enregistre le baseline actuel
```

Ou via npm :
```bash
npm run test:smoke
npm run test:regression
npm run test:critical
```

### Analyser la qualité

```bash
node scripts/agents/quality-agent.js gate         # Quality gate → exit 0/1
node scripts/agents/quality-agent.js kpi          # KPI dashboard HTML
node scripts/agents/quality-agent.js flaky --runs=3
node scripts/agents/quality-agent.js verify
```

### Bugs et RCA

```bash
node scripts/agents/bug-agent.js triage           # Classifie les échecs UI
node scripts/agents/bug-agent.js rca              # Root cause analysis
node scripts/agents/bug-agent.js loop             # Boucle agentique
```

### Génération de code

```bash
node scripts/agents/codegen-agent.js spec         # Génère la spec UI
node scripts/agents/codegen-agent.js tc US-001    # Génère les TCs Gherkin pour une US
node scripts/agents/codegen-agent.js coverage     # Couverture des features
```

### Rapports

```bash
node scripts/agents/reporting-agent.js generate   # Rapport Allure HTML
node scripts/agents/reporting-agent.js publish    # Rapport + notification
node scripts/agents/reporting-agent.js notify     # Notification Slack/Teams seule
```

### Pipeline

```bash
node scripts/agents/pipeline-agent.js quick       # Smoke → gate → notify
node scripts/agents/pipeline-agent.js full        # Pipeline complet
node scripts/agents/pipeline-agent.js nightly     # Regression complète nocturne
node scripts/agents/pipeline-agent.js gate        # Gate CI/CD (exit 0 ou 1)
node scripts/agents/pipeline-agent.js status      # État du pipeline
```

### CI/CD et Jira

```bash
node scripts/agents/ci-agent.js commit            # Commit (ne stage jamais .env)
node scripts/agents/ci-agent.js push              # Push avec SSL bypass
node scripts/agents/ci-agent.js pr create         # Crée une PR GitHub
node scripts/agents/planning-agent.js stories     # Crée les US dans Jira
node scripts/agents/planning-agent.js tickets     # Crée les bugs Jira depuis Allure
```

---

## Structure des fichiers clés

```
scripts/agents/              ← 10 agents JS (point d'entrée)
  llm.js                     ← 5 patterns LLM — require() directement
  shared/
    circuit-breaker.js       ← résilience LLM
    memory-store.js          ← mémoire épisodique JSONL
    prompt-store.js          ← versioning des prompts
    tracer.js                ← traçabilité des appels LLM
  jira-fetcher.js            ← client Jira
src/
  features/                  ← fichiers .feature Gherkin (source de vérité)
  steps/                     ← step definitions Cucumber
  pages/                     ← Page Object Model (TypeScript)
  fixtures/                  ← fixtures Playwright (NE PAS COMMITTER user.json)
prompts/                     ← templates de prompts versionnés (JSON)
logs/                        ← traces LLM (NE PAS COMMITTER)
memory/                      ← épisodes agentiques (NE PAS COMMITTER)
allure-results/              ← résultats de test (NE PAS COMMITTER)
RAG/                         ← base de connaissances QA
docs/                        ← rapports HTML, specs, traceability matrix
```

---

## Règles de sécurité — OBLIGATOIRES

- **Ne jamais committer `.env`** — contient `GROQ_API_KEY`
- **Ne jamais committer `src/fixtures/user.json`** — credentials de test
- **Ne jamais committer `logs/`** ou `memory/`
- **Push toujours avec SSL bypass** : `git -c http.sslVerify=false push origin main`
- Le `ci-agent.js` gère ça automatiquement

---

## Variables d'environnement requises

```env
GROQ_API_KEY=...          # LLM Groq LLaMA 3.3 70B (obligatoire)
JIRA_URL=...              # URL Jira Cloud
JIRA_EMAIL=...            # Email compte Jira
JIRA_TOKEN=...            # Token API Jira
SLACK_WEBHOOK_URL=...     # Webhook Slack (optionnel)
TEAMS_WEBHOOK_URL=...     # Webhook Teams (optionnel)
AGENT_MAX_ITER=5          # Max itérations boucle agentique (hard cap: 20)
```

---

## Quality Gates

| Seuil | Valeur |
|-------|--------|
| Pass rate minimum | 90% |
| Fail rate maximum | 5% |
| Confidence LLM minimum | 0.70 |
| Flaky threshold | 0.34 (1/3 runs en échec) |

---

## Modules LLM disponibles

```javascript
const llm = require('./llm');

await llm.chat(messages)                         // Texte libre
await llm.chatCoT(messages)                      // Chain of Thought
await llm.chatStructured(messages, schema)       // JSON structuré
await llm.chatConfident(messages, schema)        // Avec score de confiance
await llm.chatSelfConsistent(messages, schema,   // Vote majoritaire N fois
                              verdictKey, n=3)
```

---

## Application testée

- **App** : QACart Todo — qacart-todo.herokuapp.com
- **Utilisateurs de test** : créés dynamiquement via API Setup (POST register), pas de compte statique
- **Features** : Signup, Login, Todo, Delete Todo, API Setup (Id01, Id02, Id03, Id04, Id05, Id09)
- **Projet Jira** : SCRUM

---

## Ne pas modifier

- `scripts/agents/llm.js` — interface LLM stable
- `scripts/agents/shared/circuit-breaker.js` — logique CB testée
- `src/features/*.feature` — source de vérité Gherkin
- `prompts/*.json` — modifier via `promptStore.save()`, jamais manuellement
- `src/fixtures/user.json` — ne pas committer, contient des credentials
