# Audit des sources et des résultats

Depuis la racine `ui_playwright_bdd` :

```powershell
npm run agent:quality:verify
```

L'audit commence par deux contrôles locaux : compilation TypeScript avec
`noUnusedLocals` et `noUnusedParameters`, puis dry-run Cucumber de tous les
scénarios sans filtre de tags. Le dry-run détecte notamment les steps manquants
ou ambigus ; il n'exécute pas les tests UI et ne produit pas de résultats Allure.
La compilation n'inclut pas une règle ESLint `no-floating-promises`.

Le LLM reçoit tous les fichiers `.feature` et `.ts` de `src/`, avec les hooks,
le World, les Page Objects et les helpers. Les fichiers sont complets et regroupés
en lots ; le contexte `src/hooks/` et `src/core/` est répété dans chaque lot.
Le manifeste indique les fichiers présents dans les autres lots. Une dépendance
non visible dans le lot courant ne permet pas de conclure à son absence.
Les fichiers `.env`, les données JSON des fixtures et `node_modules` ne font pas
partie des sources transmises.

Chaque lot de sources utilise un appel LLM structuré, au lieu de quatre appels
pour analyser puis extraire le verdict. Chaque constat doit citer un chemin,
une ligne et un extrait exact vérifiés localement. Cette vérification prouve
que l'extrait existe ; elle ne garantit pas la justesse du raisonnement du LLM.
Les conseils de style sont conservés séparément dans `suggestions`.
Un numéro de ligne erroné est recalé uniquement si la citation complète possède
une occurrence unique dans le fichier ; `reportedLine` conserve la valeur donnée
par le LLM. Une citation introuvable ou ambiguë reste à examiner. Les appels directs
sans argument dont TypeScript confirme un retour `void` sont transmis comme faits
locaux : leur valeur de retour ne demande pas d'`await`.

Le rapport `docs/verify-report.json` contient :

- `schemaVersion: 3` et le mode `full` ou `local-only` ;
- les trois catégories, y compris celles qui n'ont pas pu être évaluées ;
- les résultats locaux, le nombre de scénarios et de steps ;
- les chemins et empreintes SHA-256 des sources lues ;
- les lots terminés, les fichiers non analysés et les limites rencontrées ;
- les constats cités, les suggestions et les références rejetées.

La couverture (`reviewedFiles`) compte les sources des lots dont le LLM a terminé
l'analyse. Une citation rejetée ne retire pas tout le lot de ce compteur.
Le constat reste dans `unresolvedFindings`, et seule la catégorie concernée passe
à `NEEDS_REVIEW`. Les catégories ont aussi leur propre `coverage` : un problème
d'analyse d'une page TypeScript ne rend pas automatiquement les features non évaluées.
Les remarques sur un fichier vide sans usage défaillant cité ou sur un BOM UTF-8
accepté par le compilateur sont conservées comme conseils dans `dismissedFindings`.

| Verdict | Signification |
| --- | --- |
| `VALID` | Aucun défaut signalé dans le périmètre évalué ; pour les sources, tous les lots et contrôles locaux ont abouti. |
| `WARNING` | Le LLM signale un défaut avec une référence source vérifiable. |
| `INVALID` | Un contrôle local échoue, ou le LLM signale un défaut grave avec une référence vérifiable. |
| `NOT_EVALUATED` | Audit incomplet, service indisponible, données absentes ou mode local seul. |

`analysisStatus` précise si l'analyse est `COMPLETE`, `INCOMPLETE`,
`NEEDS_REVIEW`, `UNAVAILABLE` ou `SKIPPED`. Un échec local reste `INVALID` même si le LLM est
indisponible. Les constats d'un audit partiel restent consultables mais ne donnent
pas un certificat de validité à l'ensemble du code.

Pour Allure, le verdict est entièrement local (`method: deterministic`), sans appel
LLM. Tous les JSON complets et leurs étapes imbriquées sont contrôlés : UUID racine
non vide et unique, types des champs connus, enums, cohérence start/stop, labels,
liens, paramètres, pièces jointes et `titlePath` (tableau de chaînes).
Les champs optionnels, descriptions vides, tableaux vides et `statusDetails` sur un
test réussi sont acceptés. `historyId` reste une chaîne opaque ; le SDK utilise
normalement le hash de paramètres vides pour un test sans paramètres.
Un test `broken` n'est pas, en soi, un fichier Allure invalide.

Ce contrôle s'appuie sur le modèle installé `allure-js-commons/dist/types/model.d.ts`
et sur la [documentation du format Allure](https://allurereport.org/docs/how-it-works-test-result-file/).
Il ne vérifie pas le rendu HTML, l'existence des fichiers de pièces jointes ni les
extensions inconnues. `VALID` porte sur ce périmètre structurel, pas sur la qualité
métier ou la réussite des tests.

## Contrôle sans LLM

```powershell
npm run agent:quality:verify -- --local-only
```

Cette commande enregistre les contrôles locaux et laisse l'audit LLM des sources
à `SKIPPED`. Gherkin et Steps peuvent donc être `NOT_EVALUATED` malgré des contrôles
locaux `PASS`. Allure reçoit son verdict local habituel, même sans fournisseur LLM.
Pour préserver le rapport existant, ajouter `--dry-run` :

```powershell
npm run agent:quality:verify -- --local-only --dry-run
```

## Taille des lots

`VERIFY_MAX_PROMPT_CHARS` limite le prompt source à 24 000 caractères par défaut.
C'est une limite en caractères, pas une garantie sur le nombre de tokens ni sur
les quotas du fournisseur. Un fichier qui ne tient pas avec son contexte n'est
jamais tronqué : il est explicitement déclaré non analysé.
En cas d'indisponibilité LLM, le même lot est retenté une seule fois après 45 secondes.
Si le service reste indisponible, les lots suivants sont arrêtés et le rapport reste
explicite sur la couverture partielle.

```powershell
$env:VERIFY_MAX_PROMPT_CHARS = '32000'
npm run agent:quality:verify
```

L'audit ne modifie pas les sources et n'applique pas de corrections automatiques.
Le bilan porte sur la qualité des catégories, pas sur le taux de réussite des tests.
