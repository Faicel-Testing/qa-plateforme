# Runs isolés et erreurs des agents

## Rapport avec moins de scénarios que prévu

Un rapport généré avant la fin du run ne contient que les résultats déjà écrits. Vérifier `completed` dans `results/run-manifest.json` et l'événement `testRunFinished` dans le journal Cucumber. Les retries ne sont pas des scénarios supplémentaires : 30 tentatives peuvent représenter 29 scénarios.

La commande `test:parallel` attend maintenant la fin des deux navigateurs, même si l'un termine en échec. L'option `concurrently -k`, qui arrêtait l'autre navigateur, a été retirée. Le code de sortie global reste en échec si l'un des navigateurs échoue. Allure signale les exécutions incomplètes à l'ouverture/génération et dans `Execution.Status`.

## Données PostgreSQL : run déjà clôturé

`Data run is already completed; use a new run ID` signifie qu'une réservation de données a reçu l'identifiant d'un run clôturé. Ce message ne démontre aucun défaut de l'application cible.

Les nouveaux lancements autonomes du runner et du multibrowser génèrent une identité indépendante des variables utilisées pour consulter un ancien rapport. L'identité et le dossier ne sont imposés par l'orchestrateur que pour une exécution gérée. Les commandes de consultation et d'analyse continuent de respecter un `ALLURE_RESULTS_DIR` explicite.

Les résultats multibrowser sont maintenant isolés par run, avec un manifeste. `allure:merge` lit les derniers pointeurs Chromium et Firefox et crée un nouveau dossier, sans reprendre les anciens échecs présents dans `allure-results`. Il refuse des runs incomplets ou issus de versions différentes des sources.

Dans le terminal utilisé pour consulter un ancien rapport, enlever les sélections avant de consulter le prochain run :

```powershell
Remove-Item Env:ALLURE_RESULTS_DIR, Env:QA_RUN_ID -ErrorAction SilentlyContinue
```

Ces deux paramètres sont des sélections transitoires et ne doivent pas être conservés dans `.env` pour les exécutions autonomes. Les anciens dossiers ne sont pas supprimés. Ne pas réouvrir artificiellement un run clôturé dans PostgreSQL.

## Groq : taille, débit et disponibilité

- **HTTP 413** : requête rejetée pour sa taille. La RCA déduplique les traces et messages identiques dans chaque groupe, tout en conservant les noms des tests affectés. Les lectures complètes restent disponibles dans les preuves originales.
- **HTTP 429** : fournisseur limitant les appels ou les tokens. L'analyse Bug interrompt les appels supplémentaires du lot et marque les autres cas non évalués. Le mode repair s'arrête également. Le circuit breaker reste actif.
- **Circuit ouvert** : protection consécutive à des erreurs, sans réponse IA de remplacement. Ne pas réinitialiser la protection en boucle pour forcer les appels.
- **Audit incomplet** : TypeScript et Cucumber peuvent être PASS alors que la revue IA des sources n'a pas abouti. Les deux résultats restent distincts.

Les analyses qui contiennent déjà les preuves et les sources nécessaires (investigation Bug, audit de sources et RCA) n'ajoutent plus de recherche/reranking RAG à ces appels. Cela évite les requêtes supplémentaires et les extraits non nécessaires dans ces parcours. Le RAG reste disponible pour les autres usages.

Ces ajustements ne suppriment pas les quotas externes. En cas de 429, attendre la disponibilité du compte puis relancer uniquement le périmètre utile. Une erreur de fournisseur reste une erreur technique, jamais une réparation réussie ou un verdict métier valide.

## Confluence

`account/token denied access` nécessite un compte disposant de l'accès au produit et aux pages configurées. Le contexte indisponible est exclu ; aucun correctif de test ne peut accorder ces droits. L'absence de contexte doit rester visible dans les analyses qui en dépendent.
