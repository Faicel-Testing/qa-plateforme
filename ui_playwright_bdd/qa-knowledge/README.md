# Base de connaissances QA — notes manuelles

Ce dossier contient des notes d'analyse QA accumulées manuellement au fil du temps (exports de sessions d'analyse, matrices de traçabilité User Story ↔ .feature). Ce n'était **pas** un système RAG (Retrieval-Augmented Generation) fonctionnel — le dossier s'appelait `RAG/`, mais aucun agent ne le lisait, aucun embedding ni retriever n'existait. Renommé `qa-knowledge/` le 2026-08-25 pour refléter honnêtement son contenu réel.

Fichiers :
- `qa-knowledge.md` — notes d'analyse de couverture (User Stories Jira ↔ fichiers `.feature`), accumulées manuellement.
- `QA_ANALYSIS.md` — copie de `../docs/QA_ANALYSIS.md`.

**Statut actuel** : ces notes sont consultées par le RAG hybride partagé (`scripts/agents/shared/hybrid-rag.js`). Elles restent des références non approuvées, pas des preuves automatiques.

Le RAG combine BM25 et embeddings Ollama, puis fusionne les classements avec RRF. Il recherche dans les notes, les spécifications, les scénarios et les champs sélectionnés de `memory/episodes.jsonl`. Voir [les commandes et limites](../docs/rag.md).
