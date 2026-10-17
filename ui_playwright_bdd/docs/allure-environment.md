# KPI dans Environment

## Indicateurs globaux

`allure:generate` ajoute les 18 champs demandés à `environment.properties` et
enregistre les valeurs dans `report-metrics.json`, dans le dossier du run sélectionné.
Les propriétés utilisateur et les métriques par navigateur sont conservées.

| Champ | Définition |
| --- | --- |
| Quality.Gate | Gate déterministe des tests : PASS / FAIL ; NOT_EVALUATED sans manifeste. Aucune autorisation de release. |
| Gate.Criteria.Passed | Nombre de critères satisfaits sur 7 : résultats lisibles non vides, run identifié, exécution complète, runner réussi, nombre de résultats cohérent, période valide, toutes les tentatives réussies. |
| Gate.Blockers | Contrôles non satisfaits et motifs du gate existant. |
| Pass.Rate / Fail.Rate / Broken.Rate | Statut final par test et navigateur, divisé par Total.TCs. |
| Anomaly.Rate | (Failed + Broken) / Total.TCs ; les skipped/unknown ne sont pas des succès et bloquent le gate. |
| Flaky.Tests | Groupes ayant au moins une tentative passed et une failed/broken dans ce run. Ce n'est pas une mesure historique. |
| Automation.Coverage | Cas automatisés / inventaire de référence explicite ; jamais déduit du taux de réussite. |
| Total.TCs / Passed / Failed | Comptages après regroupement des retries par historyId et navigateur (uuid à défaut). |
| Execution.Time | Intervalle entre première tentative et dernière fin ; inclut retries et parallélisme, exclut l'IA. |
| Avg.Test.Duration | Moyenne des durées des tentatives finales. NOT_EVALUATED si durées incomplètes. |
| Framework | Socle Playwright/Cucumber TypeScript et agents Python LangChain/LangGraph. |
| LLM.Engine | Valeur llmEngine enregistrée dans le manifeste ; NOT_RECORDED en son absence. La configuration actuelle n'est pas une preuve d'usage dans un ancien run. |
| API.Under.Test | Cible applicative enregistrée (baseUrl du manifeste ou pièce jointe Base URL). Pour ce framework UI, ce champ ne prouve pas une couverture de tous les endpoints API. Identifiants, query et fragment sont retirés. |
| Report.Generated | Date UTC de génération des métriques du rapport. |

Le gate examine toutes les tentatives : un run peut donc avoir un Pass.Rate final
de 100 % mais un gate FAIL si une première tentative a échoué.

Pour fournir la couverture, déposer un inventaire validé `automation-coverage.json`
dans le dossier de résultats, avec un runId correspondant au manifeste :

```json
{"schemaVersion":1,"runId":"ID_DU_RUN","scope":"Lot de référence validé","totalTestCases":20,"automatedTestCases":12}
```

Ces nombres sont un exemple de format, pas la couverture de ce projet.
Sans référence valide, la couverture reste NOT_EVALUATED. Les métriques globales
ne présentent pas de pourcentages calculés sur un corpus comportant des JSON illisibles.

## Indicateurs par navigateur

La génération `npm run allure:generate` calcule automatiquement les KPI du dossier de résultats sélectionné avant de produire le rapport, en local et dans la CI.

Pour chaque navigateur : `total`, `passed`, `failed`, `broken`, `skipped`, `unknown`, `retried`, taux de réussite, taux d'échec et taux de retry. Les tentatives partageant le même `historyId` et navigateur sont regroupées ; le dernier résultat détermine le statut final.

`chromium_execution_time` (et les équivalents pour les autres navigateurs) mesure le temps entre le début de la première tentative et la fin de la dernière. `tests_execution_time` mesure cet intervalle sur tous les navigateurs. Les durées sont exprimées en secondes, incluent les retries et ne cumulent pas les tests parallèles. Elles excluent les étapes IA et la génération du rapport. Une durée absente est indiquée `unavailable`.

Le navigateur est lu dans les résultats ou leurs pièces jointes ; sans cette information, il est classé `unknown`. Les autres propriétés d'environnement sont conservées. Dans Allure, cliquer sur **Show all** pour afficher tous les KPI.

### Affichage sans doublons

Dans le rapport final, tests_execution_time est remplace par Execution.Time. Pour un seul navigateur, les champs navigateur total, passed, failed, pass_rate, failure_rate et execution_time sont masques car leurs equivalents globaux sont deja affiches. Les compteurs complementaires restent visibles. Pour plusieurs navigateurs, le detail par navigateur est conserve. Les fichiers browser-dashboard.json et browser-dashboard.txt gardent toutes les mesures. Fail.Rate et Anomaly.Rate restent distincts : Anomaly.Rate inclut aussi les tests broken.
