# RAG Knowledge Base — API Framework

Ce dossier contient la base de connaissances QA utilisée par les agents IA du framework API.

## Fichiers

| Fichier | Rôle | Alimenté par |
|---------|------|--------------|
| `QA_ANALYSIS.md` | Analyse QA, user stories, critères d'acceptation, couverture | `api-spec-agent.py` |
| `qa-knowledge.md` | Connaissances accumulées : Jira stories, patterns, historique | `jira-agent.py`, `qa-agent.py` |

## Comment les agents utilisent ce dossier

```
api-spec-agent    → écrit dans QA_ANALYSIS.md   (user stories extraites)
jira-agent        → écrit dans qa-knowledge.md  (stories Jira mappées)
qa-agent          → lit QA_ANALYSIS.md          (analyse la couverture)
bug-analyzer      → lit qa-knowledge.md         (contexte des échecs)
api-generate-agent → lit QA_ANALYSIS.md         (génère les tests)
```
