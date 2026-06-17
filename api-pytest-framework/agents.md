# agents.md — API pytest-bdd Framework

Ce fichier décrit comment les agents IA interagissent avec ce framework.
Convention inspirée de `CLAUDE.md` (Anthropic) — lisible par tout agent LLM.

---

## Ce que fait ce framework

Tests API BDD (pytest-bdd + Gherkin) pour l'application **Hotel Booking**
(restful-booker.herokuapp.com) — 51 scénarios couvrant 8 endpoints REST.

---

## Commandes disponibles

### Exécuter des tests

```bash
python agents/runner-agent.py smoke          # Tests @smoke (rapide, ~2 min)
python agents/runner-agent.py critical       # Tests @critical
python agents/runner-agent.py regression     # Suite complète
python agents/runner-agent.py gono-go        # Smoke + Critical + analyse LLM
python agents/runner-agent.py baseline       # Enregistre le baseline actuel
```

### Analyser la qualité

```bash
python agents/quality-agent.py gate          # Quality gate → exit 0 (pass) ou 1 (fail)
python agents/quality-agent.py kpi           # KPI dashboard HTML
python agents/quality-agent.py flaky --runs=3
python agents/quality-agent.py verify gherkin
```

### Bugs et RCA

```bash
python agents/bug-agent.py triage            # Classifie tous les échecs
python agents/bug-agent.py rca               # Root cause analysis
python agents/bug-agent.py repair            # Génère un patch (dry-run)
python agents/bug-agent.py repair --apply    # Applique le patch
python agents/bug-agent.py loop              # Boucle agentique (triage→rca→repair)
```

### Génération de code

```bash
python agents/codegen-agent.py spec          # Génère la spec API depuis les features
python agents/codegen-agent.py tc US-001     # Génère les TCs pour une US
python agents/codegen-agent.py coverage      # Analyse la couverture
python agents/codegen-agent.py full          # Spec + TC + coverage
```

### Rapports

```bash
python agents/reporting-agent.py generate    # Rapport Allure HTML
python agents/reporting-agent.py publish     # Rapport + notification Slack/Teams
python agents/reporting-agent.py notify      # Notification seule
```

### Pipeline

```bash
python agents/pipeline-agent.py quick        # Smoke → gate → notify
python agents/pipeline-agent.py full         # Pipeline complet
python agents/pipeline-agent.py nightly      # Regression complète nocturne
python agents/pipeline-agent.py gate         # Gate CI/CD (exit 0 ou 1)
python agents/pipeline-agent.py status       # État du pipeline
```

### CI/CD et Jira

```bash
python agents/ci-agent.py commit             # Commit (ne stage jamais .env)
python agents/ci-agent.py push               # Push avec SSL bypass
python agents/ci-agent.py pr create          # Crée une PR GitHub
python agents/planning-agent.py stories      # Crée les 8 US dans Jira
python agents/planning-agent.py tickets      # Crée des bugs Jira depuis Allure
python agents/planning-agent.py sync         # Synchronise Allure → Jira
```

---

## Structure des fichiers clés

```
agents/                  ← 10 agents IA (ne pas modifier les modules partagés)
  llm.py                 ← 5 patterns LLM — importer directement
  circuit_breaker.py     ← résilience LLM — ne pas instancier manuellement
  memory_store.py        ← mémoire épisodique JSONL
  prompt_store.py        ← versioning des prompts (charger via PromptStore().get())
  tracer.py              ← traçabilité des appels LLM
  jira_fetcher_agent.py  ← client Jira (JiraClient)
features/                ← fichiers .feature Gherkin (source de vérité)
steps/                   ← step definitions pytest-bdd
prompts/                 ← templates de prompts versionnés (JSON)
logs/                    ← traces LLM, circuit breaker state (NE PAS COMMITTER)
memory/                  ← épisodes agentiques JSONL (NE PAS COMMITTER)
allure-results/          ← résultats de test (NE PAS COMMITTER)
RAG/                     ← base de connaissances QA pour contexte LLM
```

---

## Règles de sécurité — OBLIGATOIRES

- **Ne jamais committer `.env`** — contient `GROQ_API_KEY`
- **Ne jamais committer `logs/`** — traces avec données potentiellement sensibles
- **Ne jamais committer `memory/`** — épisodes agentiques
- **Push toujours avec SSL bypass** : `git -c http.sslVerify=false push origin main`
- Le `ci-agent.py` gère ça automatiquement — ne pas utiliser `git push` nu

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

```python
import llm

llm.chat(messages)                              # Texte libre
llm.chat_cot(messages)                          # Chain of Thought
llm.chat_structured(messages, schema)           # JSON structuré
llm.chat_confident(messages, schema)            # Avec score de confiance
llm.chat_self_consistent(messages, schema,      # Vote majoritaire N fois
                         verdict_key, n=3)
```

---

## Projet Jira

- **Clé projet** : `HBAPI`
- **8 User Stories** : US-001 (POST /auth) à US-008 (GET /ping)
- **Marqueurs pytest** : `@smoke`, `@critical`, `@regression`, `@tc-NNN`, `@us-NNN`

---

## Ne pas modifier

- `agents/llm.py` — interface LLM stable, utilisée par tous les agents
- `agents/circuit_breaker.py` — logique CB testée
- `features/*.feature` — source de vérité Gherkin, ne modifier qu'avec `codegen-agent`
- `prompts/*.json` — modifier via `PromptStore().save()`, jamais manuellement
