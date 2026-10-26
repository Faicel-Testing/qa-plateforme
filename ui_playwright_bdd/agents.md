# Instructions pour les agents — UI Playwright BDD

Lire [README.md](README.md) pour l'installation et les parcours de référence.
CucumberJS est le moteur BDD unique (`cucumber.js`). Playwright fournit
l'automatisation et les assertions. Les features restent la source des scénarios.

## Commandes de référence

- `npm run test:headless` : régression Cucumber sans LLM.
- `npm run agents:pipeline -- quick --local-only` : smoke sans LLM.
- `npm run agents:pipeline -- full` : pipeline Python LangGraph recommandé.
- `npm run typecheck` et `npm run lint` : contrôles statiques.
- `node --test scripts/tests/step-definitions.test.js` : contrats des assertions,
  métriques et résolution Gherkin sans navigateur ni appels externes.

Les adaptateurs `scripts/agents/` historiques restent disponibles ; leurs
commandes ne sont pas équivalentes au graphe Python `qa_agents/`.
Les synchronisations externes et publications ont des commandes séparées.

## Responsabilités

- `src/core/world.ts` : contexte isolé et navigateur par scénario.
- `src/hooks/hooks.ts` : cycle de vie, preuves et tentatives.
- `src/pages/` : Page Objects et sélecteurs stables.
- `src/steps/` : liaison métier avec Cucumber.
- `src/api/` et `src/data/` : préconditions API et données de test.
- `qa_agents/` : orchestration et analyses Python.

## Règles de travail

Ne jamais committer `.env`, les credentials, `logs/`, `memory/` ni les résultats.
Conserver les modifications existantes de l'utilisateur.
Configurer le certificat du proxy plutôt que désactiver la vérification TLS de Git.
Ne pas publier ni envoyer de notifications sans instruction explicite.
Les tests seuls ne nécessitent pas de clé LLM.

Le verdict de tests est déterministe et distinct de l'autorisation de livraison.
Les analyses IA sont des hypothèses à vérifier ; les propositions de correctif
passent par la revue décrite dans `docs/ci-human-review.md`.
Ne pas assouplir les assertions pour masquer les défauts de l'application.
La règle cible des tâches est dans `docs/todo-validation.md`.

Cucumber décide des retries ; `SmartRetry` fournit uniquement un diagnostic.
Les compteurs sont isolés par pickle et locaux au worker ; les résultats du run
Cucumber/Allure servent à l'agrégation.
