# Base de connaissances QA — notes manuelles

Ce dossier contient des notes d'analyse QA accumulées manuellement au fil du temps (exports de sessions d'analyse, matrices de traçabilité User Story ↔ .feature). Ce n'était **pas** un système RAG (Retrieval-Augmented Generation) fonctionnel — le dossier s'appelait `RAG/`, mais aucun agent ne le lisait, aucun embedding ni retriever n'existait. Renommé `qa-knowledge/` le 2026-08-25 pour refléter honnêtement son contenu réel.

Fichiers :
- `qa-knowledge.md` — notes d'analyse de couverture (User Stories Jira ↔ fichiers `.feature`), accumulées manuellement.
- `QA_ANALYSIS.md` — copie de `../docs/QA_ANALYSIS.md`.

**Statut réel** : documentation de référence humaine, non branchée au code. Aucun agent de `scripts/agents/` ne lit ce dossier (vérifié par grep).

Si un vrai RAG est souhaité un jour (recherche sémantique sur l'historique des bugs, par exemple), la prochaine étape logique serait d'indexer `memory/episodes.jsonl` avec des embeddings plutôt que de repartir de ces notes manuelles.
