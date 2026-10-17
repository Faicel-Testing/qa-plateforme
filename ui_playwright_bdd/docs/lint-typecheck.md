# ESLint et TypeScript

Le framework utilise ESLint 10, la configuration recommandée JavaScript et
`typescript-eslint/recommendedTypeChecked` pour TypeScript. La configuration est
dans `eslint.config.cjs`. Les versions exactes sont verrouillées dans `package-lock.json`.

## Installation et commandes

Utiliser Node **24**, également déclaré dans `.nvmrc` et utilisé dans GitHub Actions.
La version globale Node 23 de ce poste n'est pas prise en charge par ESLint 10.
Elle n'a pas été remplacée ; les vérifications de cette intégration utilisent
une copie temporaire isolée de Node 24.

```bash
npm ci
npm run lint
npm run typecheck
npm run test:review
```

`npm run lint:fix` applique localement les corrections automatiques disponibles.
Relire le diff avant de valider : cette commande n'est pas exécutée dans la CI.

## Périmètre

- JavaScript : `scripts/`, `cucumber.js`, `eslint.config.cjs`.
- TypeScript : `src/**/*.ts`, avec les informations de types de `tsconfig.json`.
- Les rapports, résultats Allure, logs, dépendances et fichiers compilés sont exclus.
- Les features Gherkin restent contrôlées par Cucumber.

Le lint détecte notamment les variables non définies ou inutilisées, les `any`
explicites, les usages non sûrs des types et les promesses sans traitement.
`tsc --noEmit` vérifie séparément la compilation TypeScript, sans générer de code.

Deux conventions sont explicites : un paramètre intentionnellement inutilisé
peut commencer par `_`, et une propriété retirée par déstructuration avec reste
est autorisée. Les captures d'erreur volontairement ignorées sont acceptées.
Ces réglages ne désactivent pas les contrôles de promesses ou de types.
Une exception locale documentée conserve le masquage des erreurs du fournisseur
d'embeddings : leur cause brute pourrait exposer des identifiants dans les logs.

## Blocage CI

Après `npm ci`, la CI exécute, dans cet ordre :

1. `npm run lint`, avec zéro avertissement autorisé ;
2. `npm run typecheck` ;
3. les tests des contrôles de revue et de lint ;
4. les tests BDD.

Les erreurs arrêtent les étapes suivantes : aucun `continue-on-error` ni
correction automatique. L'analyse IA exige la réussite des contrôles statiques,
mais reste disponible après un échec des tests BDD.

Le workflow s'exécute aussi lorsqu'une PR modifie son fichier YAML. Pour imposer
sa réussite avant toute fusion, le statut du job doit être exigé dans les règles
de branche GitHub ; ces réglages distants n'ont pas été modifiés.

Références : [compatibilité ESLint 10](https://eslint.org/docs/latest/use/migrate-to-10.0.0),
[configurations TypeScript](https://typescript-eslint.io/users/configs/).
