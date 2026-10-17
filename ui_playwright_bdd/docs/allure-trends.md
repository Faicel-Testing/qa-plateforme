# Tendances Allure

`npm run allure:generate` et les pipelines `quick`/`full` reprennent désormais
le dossier `history` d'une exécution antérieure avant de générer le rapport.
Les widgets **Trend**, **Duration**, **Retries** et l'historique des tests utilisent
ces données. Le total des tests affiché reste celui de l'exécution courante.

Les historiques générés sont conservés dans `.allure-history/` (ignoré par Git).
Les anciens rapports de `allure-runs/` permettent aussi d'amorcer la série : le
rapport précédent compatible est repris, sans rejouer ses tests. Les anciens
rapports isolés ne sont pas tous reconstruits rétroactivement.

Une première exécution donne un point ; une comparaison apparaît à partir de
deux exécutions. Allure 2 conserve jusqu'à 20 rapports dans ses graphiques.
Régénérer le même rapport ne crée pas de point supplémentaire.

Les séries sont séparées par le filtre de tags du manifeste (`@smoke`, régression,
etc.). Pour séparer aussi plusieurs environnements ou navigateurs, définir
`ALLURE_HISTORY_KEY` avec une valeur stable, par exemple `smoke-chromium-staging`.
Pour les commandes sans manifeste, la série utilise le nom du dossier de résultats.
`ALLURE_HISTORY_DIR` permet de choisir un autre dossier de conservation.

Les runs dont le manifeste indique une exécution incomplète n'alimentent pas
l'historique. Les exécutions terminées avec des tests en échec y figurent bien.

Dans GitHub Actions, le cache conserve cet historique par référence Git et la
génération utilise le même agent qu'en local. Un cache absent ou supprimé démarre
une nouvelle série. Les rapports HTML restent téléchargeables comme artefacts.

```bash
npm run allure:generate
npm run allure:open
```

Utiliser ces commandes plutôt qu'un appel direct à `npx allure generate` pour
bénéficier de la reprise automatique de l'historique.

Référence : [historique Allure 2](https://allurereport.org/docs/history-and-retries/).
