# CI et revue humaine : fonctionnement réel

## Automatisation CI

Le workflow `.github/workflows/ci-playwright.yml` exécute les tests de régression via
`scripts/ci-ai.js test`, puis conserve les résultats Allure et le manifeste
d'exécution (identifiant du run, commit, empreinte des sources, fin d'exécution).

Sur `main`, un second job lance `quality triage` puis `bug analyze`, y compris
après un échec des tests. Il utilise uniquement les artefacts de cette exécution.
Les pull requests exécutent les tests sans recevoir la clé du fournisseur IA.
Le secret GitHub `GROQ_API_KEY` doit être configuré pour l'analyse.

Le bilan IA est `ADVISORY`, `FAILED`, `UNAVAILABLE` ou `BLOCKED`. Une clé absente,
des preuves incomplètes ou un mauvais identifiant ne deviennent jamais un succès
d'analyse. Le job de tests conserve son échec même si l'analyse réussit.
Les journaux et le bilan sont téléchargeables dans l'artefact `ai-analysis-*`.
`ADVISORY` signifie que les commandes ont terminé : leurs hypothèses restent
consultatives, y compris lorsque leur vérification indique `UNVERIFIED`.

La CI n'appelle pas la génération, la réparation, Jira, les notifications ou le
déploiement. Ces actions ne sont pas nécessaires à l'analyse d'un run et ne sont
pas autorisées implicitement par la réussite des tests.

## Propositions de code

`codegen` et `bug repair`, même appelés directement, enregistrent leurs candidats
dans `logs/change-proposals/<id>.json`. Les fichiers sources restent inchangés.
Le candidat contient le chemin cible, le contenu, son empreinte SHA-256 et celle
du code au moment de la proposition.

Après avoir relu le contenu et comparé le fichier actuel, le relecteur peut appliquer
exactement le candidat examiné :

```text
node scripts/agents/review-change-agent.js apply <id> <relecteur> <digest-du-candidat-relu>
```

La commande refuse une empreinte différente, une source modifiée depuis la
proposition, un chemin hors des features/steps/pages ou un candidat syntaxiquement
invalide. Après application, il faut compiler et réexécuter les tests : une revue
de code ne prouve pas à elle seule que la modification fonctionne.

## Validation finale locale

L'affichage distingue les **tests BDD** des **étapes du pipeline**. Tous les tests
peuvent réussir alors que l'Advisor affiche **EN ATTENTE D’APPROBATION**.
Cette attente compte séparément des échecs et des rejets, dans le terminal et le
tableau de bord HTML. Le résumé JSON utilise `PENDING_APPROVAL` et
`pendingApproval`. Le code de sortie reste non nul (`2`) : attendre une revue
n'autorise aucune release. Un rejet explicite est affiché **REJETÉ** ; les erreurs
techniques restent des **ÉCHECS**. Les anciens journaux ne sont pas réécrits.

Après exécution et production des analyses, créer un dossier de revue et valider
les éléments dans cet ordre, après leur lecture effective :

```text
node scripts/agents/qa-workflow-agent.js create QA-123
node scripts/agents/qa-workflow-agent.js approve QA-123 gherkin prenom.nom
node scripts/agents/qa-workflow-agent.js approve QA-123 script prenom.nom
node scripts/agents/qa-workflow-agent.js approve QA-123 execution prenom.nom
node scripts/agents/qa-workflow-agent.js approve QA-123 analysis prenom.nom
node scripts/agents/qa-workflow-agent.js approve QA-123 decision prenom.nom
node scripts/agents/qa-workflow-agent.js gate QA-123
```

Les validations portent sur le même code et le même ensemble de résultats et
rapports JSON Allure. Une modification invalide l'accord précédent. Un rejet ou
une nouvelle revue d'une étape annule les validations suivantes. Les étapes
execution/analysis/decision exigent une exécution complète et tous les tests passés.
Les anciens runs sans empreinte des sources doivent être réexécutés.

Pour `advisor gate` ou `advisor advise`, définir `QA_WORKFLOW_ID=QA-123` et, si
nécessaire, `ALLURE_RESULTS_DIR` vers le run relu. Ces points d'entrée vérifient
eux-mêmes la revue : lancer l'agent directement ne contourne pas cette règle.
La revue humaine est nécessaire mais pas suffisante : les contrôles techniques et
de vérification IA existants restent bloquants. Le pipeline automatique ne peut
donc pas fabriquer son propre accord humain après un nouveau run.

## Limite d'autorité et configuration GitHub restante

Un nom de relecteur et un registre JSON local assurent une traçabilité de travail,
pas une authentification. Une personne ayant accès en écriture au dépôt peut
modifier le programme ou le registre. Ces règles encadrent les points d'entrée
modifiés ci-dessus, pas toute commande système ni tous les autres agents.

Pour une autorisation de merge ou de déploiement opposable, configurer les règles
de branche GitHub (PR et approbations obligatoires, checks requis, révocation des
approbations après modification). Un futur job de déploiement doit utiliser un
environnement protégé avec des relecteurs requis, idéalement sans auto-approbation.
Ces réglages distants ne sont pas activés par la présence de ce fichier et n'ont
pas été modifiés dans cette intervention. Aucun déploiement n'est ajouté.

Référence : [environnements et relecteurs GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

## Vérification locale sans fournisseur IA

```text
node --test scripts/agents/tests/human-review.test.js scripts/agents/tests/agent-reliability.test.js scripts/agents/tests/pipeline-runtime.test.js
```

Ces tests utilisent des dossiers temporaires et des réponses simulées. Un cas
d'intégration lance réellement Cucumber sur un scénario local volontairement en
échec pour vérifier les artefacts. Ils ne valident pas la disponibilité de QACart,
de Groq ou du service GitHub Actions.
