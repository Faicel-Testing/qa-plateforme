# Plane et les agents Playwright BDD

Projet : [Application_Test](https://app.plane.so/ai-qa-automation/projects/a1cd9e82-915a-4dc9-9fd9-69441c41ebdb/issues/).

Le client `scripts/agents/plane-fetcher.js` utilise l'API REST v1 officielle sur `api.plane.so`, avec `X-API-Key`, TLS obligatoire, délai de 30 secondes et pagination. Il ne suit pas les redirections et ne journalise ni clé ni corps d'erreur. Le token reste dans `.env`, ignoré par Git. Aucun appel LLM n'est nécessaire pour importer, lire ou sélectionner les tests.

Plane est l'unique fournisseur de Planning et Codegen. Le connecteur Jira et le repli conditionné par `STORY_PROVIDER` ont été supprimés. Les références SCRUM des documents historiques restent conservées pour le mapping. La génération crée des propositions à relire ; elle ne remplace pas les features validées et n'ajoute pas immédiatement ses propositions à l'exécution Runner.

Planning vérifie le projet distant et affiche `Planning connecté à Plane : Application_Test (APPLICATIO)` avant de lire les stories, cas de test ou cycles. Un refus d'accès produit un échec, sans repli. Les analyses de couverture locales restent indépendantes de cette connexion.

```powershell
npm.cmd run agent:planning:check
npm.cmd run agent:planning:stories
npm.cmd run agent:planning:testcases
npm.cmd run agent:planning:cycles
```

`sprint list` reste un alias de consultation des cycles Plane. Les anciennes mutations `sprint create/start/close` sont refusées : leurs règles et dates ne sont pas transposées automatiquement. Gérer les cycles dans Plane. Reporting `sync` utilise désormais le synchroniseur de résultats Plane ; le pipeline peut le déclencher explicitement avec `--sync-plane` (l'ancienne option `--sync-jira` n'active rien). La synchronisation déjà activée dans Runner continue de fonctionner.

## Organisation de l'import

Neuf stories historiques provenant de `docs/JIRA_TRACEABILITY.md` et `docs/SPEC_REPORT.md`, organisées en quatre modules : Authentification, Gestion des tâches, Évolutions du compte et À clarifier. Les références SCRUM sont conservées dans les titres et identifiants externes. Le projet n'active pas les types de work items : le label « User story » identifie ces éléments. État initial Backlog ; priorités proposées ; responsables et échéances non inventés.

Les critères issus des scénarios existants représentent la couverture de tests, pas une validation métier ni la preuve que l'application les respecte. SCRUM-9 recouvre SCRUM-6 ; les deux références sont conservées avec une note de consolidation. SCRUM-2 et les évolutions de compte ne disposent pas de tests exécutables associés.

L'import est séquentiel, protégé par un verrou local, et retrouve les éléments avec `(external_source, external_id)`. Une relance conserve les titres, descriptions, états et priorités déjà présents dans Plane. Un échec partiel laisse un journal local et peut être repris. Ne pas lancer le même import depuis plusieurs postes simultanément. Après une panne réseau ambiguë, vérifier Plane avant de relancer. Les modules sont rattachés si nécessaire, les autres champs ne sont pas écrasés.

## Commandes

```powershell
npm.cmd run plane:check
npm.cmd run plane:import:preview
npm.cmd run plane:import
npm.cmd run plane:stories
npm.cmd run plane:source -- APPLICATIO-5
node scripts/agents/codegen-agent.js gherkin APPLICATIO-5 --dry-run
npm.cmd run plane:run -- APPLICATIO-5 --dry-run
npm.cmd run plane:run -- APPLICATIO-5
```

`plane:source` vérifie la lecture complète d'une story sans appeler le LLM. Codegen gherkin, même en dry-run, appelle le LLM et peut consommer des tokens. Runner dry-run ne lance pas le navigateur ; en exécution réelle il utilise les résultats Allure et le manifeste habituels. Il ne marque pas automatiquement la story Done dans Plane. Les scénarios API Setup sont partagés entre les stories Todo et Delete ; la sélection se fait au niveau fichier.

Le mapping Runner est déterministe, à partir des identifiants historiques et des features locales. Une story sans mapping est refusée au lieu de lancer toute la suite. Pour ajouter une nouvelle story exécutable, compléter le mapping après revue des tests.

Le manifeste Allure d'un lancement `story` conserve la référence Plane et les fichiers sélectionnés. Les nouvelles stories créées directement dans Plane sont lues par Planning/Codegen lorsqu'elles portent le label « User story » ou « Story » ; elles ne disposent pas automatiquement d'un mapping Runner.

## Cas de test enfants des user stories

```powershell
npm.cmd run plane:testcases:preview
npm.cmd run plane:testcases:import
```

L'import compile les features avec le parseur Gherkin du framework. Chaque scénario est copié dans un work item enfant de sa story, avec le label `Test case`, le fichier et la ligne source, les tags et les étapes, y compris les préconditions du Background. L'état initial est Backlog : cet import n'exécute pas les tests et n'affirme pas leur réussite.

Le mapping actuel produit 38 rattachements pour 29 scénarios distincts : 8 sous APPLICATIO-1, 7 sous APPLICATIO-2, 7 sous APPLICATIO-3, 8 sous APPLICATIO-4 et 8 sous APPLICATIO-5. Les deux stories Login historiques partagent huit scénarios. Le scénario API sans authentification est partagé entre les stories Todo et Delete ; les actions API add/delete sont affectées à leur domaine respectif. Les quatre stories sans feature ne reçoivent aucun scénario inventé.

Les identifiants externes des cas de test utilisent une source distincte (`ui_playwright_bdd_testcase`) pour ne pas être confondus avec les stories par Planning/Codegen. Une relance conserve les cas existants et les modifications manuelles ; elle ne synchronise pas automatiquement les étapes modifiées. Le journal local est `logs/plane/testcases-import.json`. Un conflit de parent ou des identifiants externes ambigus bloque l'import. Les rattachements sont relus depuis Plane après création.

## Lire les résultats dans Plane

Ouvrir une user story puis son cas de test enfant. Le début de la description affiche le résultat du dernier run synchronisé, sa date (Europe/Paris), son identifiant et son périmètre. Dans la liste des work items, afficher les labels et filtrer sur `Test case`, puis sur le résultat souhaité :

| Label | Signification |
| --- | --- |
| 01 · QA FAILED | Au moins une tentative en échec |
| 02 · QA ERROR | Résultat technique broken, inconnu ou non reconnu |
| 03 · QA SKIPPED | Test ignoré, sans échec ni erreur recensé |
| 04 · QA NON EXÉCUTÉ | Scénario absent du run synchronisé |
| 05 · QA PASS | Toutes les tentatives recensées sont réussies |

Les numéros donnent un ordre de lecture, des échecs aux réussites ; ils ne changent pas le tri personnel de l'interface Plane. Les états Backlog/In Progress/Done restent indépendants du résultat des tests. Les autres labels et le contenu manuel des descriptions sont conservés.

`PLANE_SYNC_RESULTS=true` dans `.env` active la publication après chaque exécution par `runner-agent` (y compris les pipelines qui l'utilisent). Un échec de publication est signalé et rend le Runner non réussi. Une commande Cucumber directe ne déclenche pas ce branchement. Pour publier explicitement le dernier run local :

```powershell
npm.cmd run plane:results:preview
npm.cmd run plane:results:sync
```

La publication exige un manifeste terminé avec des résultats cohérents et refuse de remplacer une date plus récente par une ancienne. Un smoke marque les scénarios hors périmètre NON EXÉCUTÉ : le résultat décrit ce run, pas une régression complète. Le bloc contient la référence du rapport local ; il ne publie pas le rapport Allure sur Internet. Aucun appel LLM n'est effectué et les traces brutes ne sont pas envoyées dans Plane.

## Configuration des certificats

Sur ce poste, `PLANE_CA_FILE=logs/plane/windows-ca.pem` complète les autorités Node avec les certificats publics du magasin Windows. `scripts/export-plane-ca.ps1` régénère ce bundle ; il ne contient aucune clé privée. Ce réglage reste local et doit correspondre aux autorités approuvées de chaque poste. Ne jamais désactiver TLS pour contourner une erreur.

Le contenu récupéré depuis Plane est une donnée non fiable : il passe par le gateway lors d'un appel LLM et ne peut pas définir les chemins exécutés par Runner. Les commandes d'import sont explicites, sans LLM. Les secrets ne figurent pas dans les descriptions importées.

Référence API : https://developers.plane.so/api-reference/issue/add-issue
