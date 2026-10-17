# Changelog

## 1.7.0 — 2026-10-18

- Agents Python avec LangChain / LangGraph : pipeline, analyse, qualité, génération et agent Data.
- Groq comme fournisseur IA unique, gateway de contrôle, RAG BM25 et intégration DeepEval.
- Jeux de données PostgreSQL : migrations SQL, profils synthétiques, réservations concurrentes par scénario, libération et connexion pgAdmin locale.
- Rapports Allure : environnement, historique et tendances par exécution.
- Intégrations Plane et Confluence, diagnostics d'accès et exclusion du contexte indisponible.
- Diagnostics API sans secrets, prise en charge de `access_token`, navigation login et traces améliorées.
- Revue humaine des propositions, vérifications des agents, lint et contrôles CI.

### Validation et limites connues

Le scénario de connexion a été rejoué avec succès. Le scénario négatif sur la longueur d'une tâche reste en échec : l'application accepte 201 caractères avec HTTP 201 ; la limite métier proposée de 200 caractères doit être confirmée. Les assertions restent actives.

L'accès Confluence nécessite un compte autorisé. Les appels IA nécessitent une clé Groq et restent soumis aux quotas du fournisseur. Les configurations PostgreSQL et les secrets locaux ne sont pas inclus dans cette version.
