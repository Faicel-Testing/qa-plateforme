# Changelog

## Changements depuis 1.7.1 — 2026-10-26

- CucumberJS comme moteur BDD unique ; suppression de la configuration et de la dépendance `playwright-bdd`.
- Sélecteurs des formulaires stabilisés, assertion de connexion dédupliquée et contrôle conjoint du message de validation et de l'absence d'insertion des tâches invalides.
- Métriques de retry isolées par pickle et fondées sur les tentatives démarrées ; classification SmartRetry conservée comme diagnostic.
- Résultats multibrowser isolés par run, manifestes et fusion des exécutions terminées ; diagnostics des erreurs de données et de fournisseur IA.
- Embeddings E5 locaux, worker dédié et stockage RAG PostgreSQL/pgvector optionnel.
- Instrumentation Python/Node OpenTelemetry et stack Langfuse locale optionnelle.
- README global, README Playwright et instructions des agents harmonisés.

Validation ciblée : TypeScript et lint réussis ; 56 tests Node ciblés, 70 contrôles de revue/orchestration et 62 tests Python réussis ; résolution des 29 scénarios Gherkin ; inscription et connexion réussies dans Chromium en mode de données mémoire. La régression UI complète et le mode PostgreSQL ne sont pas validés par ces contrôles.

## 1.7.1 — 2026-10-18

- README global et README Playwright BDD actualisés : architecture, agents Python LangChain / LangGraph, harness LLM, agent Data PostgreSQL et pgAdmin.
- Commandes d'installation, de pipeline, d'analyse, d'Allure et de DeepEval alignées sur les scripts du projet ; intégrations Plane et Confluence documentées.
- Documentation des contrôles CI, de la revue humaine et des limites connues ; versions npm et liens de release synchronisés.

Validation documentaire : 39 liens locaux et 33 commandes npm vérifiés. Aucun changement du comportement des tests ; les limites connues de la version 1.7.0 restent applicables.

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
