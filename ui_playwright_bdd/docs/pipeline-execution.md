# Exécuter le pipeline et consulter les échecs

Depuis `ui_playwright_bdd`, dans PowerShell :

```powershell
npm.cmd run agent:pipeline:quick
npm.cmd run allure:open
```

`quick` exécute les scénarios `@smoke`. Pour toutes les features :

```powershell
npm.cmd run agent:pipeline:full
npm.cmd run allure:open
```

Le pipeline full conserve planning, génération de spécifications, analyse des échecs,
tableaux de bord, recommandation de release, observabilité et consultation CI.
Il ajoute la génération Allure immédiatement après le Runner et un quality gate final.
La synchronisation Jira est optionnelle (`-- --sync-jira`).

## Résultats et rapports

Chaque exécution de tests utilise un nouveau dossier `allure-runs/<runId>/results`.
Les anciens résultats restent conservés. Tous les agents du pipeline reçoivent le
même dossier via `ALLURE_RESULTS_DIR`. Le rapport HTML est dans
`allure-runs/<runId>/report`; `npm.cmd run allure:open` ouvre celui de la dernière
exécution. Dans Allure, ouvrir **Suites**, puis un test Failed/Broken, pour voir
les erreurs et les pièces jointes produites par les hooks.

`npm.cmd run allure:generate` permet de régénérer ce rapport sans rejouer les tests.
Si le HTML manque, `allure:open` le génère avant de l'ouvrir. Si les JSON Allure
manquent mais qu'un journal `cucumber-messages.ndjson` complet est disponible,
les événements enregistrés sont rejoués uniquement dans le reporter Allure :
les tests et leurs hooks ne sont pas exécutés. Le code d'échec initial est conservé.
Le Runner donne à Allure une sortie distincte de `progress`, car Cucumber ne
conserve qu'un formatteur par destination de sortie.
Pour les commandes npm de tests traditionnelles, de nouveaux fichiers dans
`allure-results` prennent la priorité sur un ancien run d'agent. Un dossier peut
aussi être choisi explicitement avec `$env:ALLURE_RESULTS_DIR = 'chemin'`.

Le rapport est tenté même si les tests échouent ou dépassent leur délai : il peut
donc être **partiel**. S'il n'y a aucun résultat, la génération échoue explicitement.
Un rapport disponible ne signifie pas que l'exécution est complète.

## Conditions de validation

Le Runner lance directement le Cucumber installé, sans `npx`, sans shell intermédiaire
et sans attendre le service LLM. Son résumé IA est optionnel (`--ai-summary`).

Le manifeste `run-manifest.json` conserve le code de sortie, les dates, le nombre
de résultats et la réception de l'événement Cucumber `testRunFinished`.
La validation exige une exécution complète, un code de sortie zéro, des résultats
non vides appartenant au run et tous les tests passés. Un test Failed, Broken,
Skipped ou de statut inconnu bloque donc la validation dans cette politique stricte.
Les anciens résultats sans manifeste ne peuvent pas autoriser une release.

Le verdict du gate doit ensuite être PASS, sans blocage de gouvernance.
FAIL, NO-GO, réponse IA invalide, absence de décision et exception renvoient un code
non nul. Une étape obligatoire en échec bloque les décisions suivantes.
`report`, `--no-tests` et `--dry-run` ne valident jamais une nouvelle exécution.
Les étapes ignorées sont comptées séparément des étapes réussies.
Les décisions non exécutées sont affichées **BLOQUÉ**, séparément des **KO**
(commandes exécutées en échec). Les deux empêchent la validation globale.

Codegen renvoie un code non nul si Jira n'est pas configuré/accessible, s'il n'y a
pas de données à générer ou si une génération échoue, y compris partiellement.
Les sorties vides, les messages d'indisponibilité et les erreurs de syntaxe
Gherkin/TypeScript sont rejetés avant écriture. Cette validation syntaxique ne
remplace pas la revue métier, la compilation complète et les tests du code généré.

Bug `analyze` utilise des décisions JSON validées localement, sans appels d'outils
natifs du fournisseur. Chaque contexte est limité à 12 000 caractères ; un échec
ou JSON invalide entraîne une seule nouvelle tentative à 6 000 caractères.
Les extraits coupés sont marqués explicitement et les lectures identiques sont
réutilisées. Le dernier tour exige une conclusion ; une absence de conclusion
reste **NOT_EVALUATED**, avec code d'échec. Ces règles ne modifient pas le mode `repair`.

Quality retente une fois les lots incomplets et conserve les lots complets dans
`logs/verify-cache` pendant 24 heures. La clé couvre le modèle, les sources et le
contexte des contrôles locaux ; les réponses sont revalidées avant réutilisation.
Les lots invalides, indisponibles ou avec des références non vérifiables ne sont
pas réutilisés. Les fichiers sources de cet audit restent transmis complets.
Une relance de `npm.cmd run agent:quality:verify` reprend ainsi les lots restants
lorsque les sources n'ont pas changé. Le cache n'est pas écrit en dry-run.

## Délais et diagnostic

Le délai des tests est désormais de 30 minutes par défaut (au lieu d'un arrêt
global du Runner à 5 minutes). Il ne modifie pas les timeouts propres à chaque step.

```powershell
$env:RUNNER_TIMEOUT_MS = '2400000' # 40 minutes pour Cucumber
$env:AGENT_TIMEOUT_MS = '600000'  # 10 minutes par autre agent
npm.cmd run agent:pipeline:full -- --verbose
```

Le Runner arrête l'arbre des processus à expiration. Le pipeline lui accorde
30 secondes supplémentaires pour enregistrer son état avant son propre arrêt forcé.
Augmenter ce délai ne corrige pas un défaut applicatif ou un step bloqué.

Les sorties des agents sont conservées dans `logs/pipeline/<runId>/*.log`.
Quality full dispose de 15 minutes par défaut (`QUALITY_TIMEOUT_MS`) et Bug de
10 minutes (`BUG_TIMEOUT_MS`). `AGENT_TIMEOUT_MS`, s'il est explicitement défini,
reste le délai commun de repli ; les variables dédiées prennent la priorité.
Quality sauvegarde ses phases dans `results/quality-analysis.json` et
`docs/quality-full-report.json`. Bug sauvegarde chaque conclusion, ou absence
de conclusion, dans `results/bug-analysis.json` et `docs/bug-analysis.json`.
Le mode Bug `analyze` est en lecture seule et réserve le dernier appel à une
conclusion ; une indisponibilité du LLM reste signalée comme non évaluée.
`summary.json` dans ce dossier et `logs/pipeline-summary.json` indiquent les codes
de sortie, timeouts, raisons des blocages et la validation globale.
`docs/pipeline-dashboard.html` affiche ce bilan.

## Vérification locale du code

```powershell
node --test scripts/agents/tests/pipeline-runtime.test.js
```

Les tests couvrent les échecs, timeouts, données périmées, absence de résultats,
gates négatifs/indisponibles et le format Allure produit par un scénario Cucumber
local volontairement en échec. Ils ne lancent pas de navigateur ni de service externe.
