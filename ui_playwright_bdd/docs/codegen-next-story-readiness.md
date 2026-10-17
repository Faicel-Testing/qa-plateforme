# Préparation de la prochaine génération — APPLICATIO-7

Analyse du 13 octobre 2026 : lecture des neuf stories Plane et comparaison avec
les neuf features actuellement présentes sous `src/features/`.

## Besoins sans scénario associé identifié

| Story | Besoin | Information disponible | Manque principal |
| --- | --- | --- | --- |
| APPLICATIO-6 | Tâche 2 | Titre historique uniquement | Besoin fonctionnel |
| APPLICATIO-7 | Mise à jour du mot de passe | Utilisateur connecté, modification avec succès ou échec | Parcours, règles et résultats attendus |
| APPLICATIO-8 | Mise à jour de l'email | Utilisateur connecté, modification avec succès ou échec | Parcours, validation de l'adresse et résultats attendus |
| APPLICATIO-9 | Suppression du compte | Utilisateur connecté, suppression avec succès ou échec | Confirmation, effets attendus et conditions de refus |

Les stories APPLICATIO-1 à APPLICATIO-5 sont associées à des tests existants.
Cela ne démontre pas une couverture exhaustive. APPLICATIO-1 recouvre historiquement
le besoin Login d'APPLICATIO-4.

## Cas retenu

[APPLICATIO-7](https://app.plane.so/ai-qa-automation/projects/a1cd9e82-915a-4dc9-9fd9-69441c41ebdb/issues/6f3c49eb-96c6-4608-9381-2524ee4fd07b),
priorité high dans Plane, origine SCRUM-18 / `docs/SPEC_REPORT.md`.

La story précise que les exigences historiques restent à confirmer. Aucun scénario
exécutable ni POM de modification du mot de passe n'a été identifié dans l'inventaire
consulté. Cette absence dans le dépôt ne démontre pas l'absence de la fonction dans
l'application déployée.

## Informations requises avant génération

1. Fonction disponible dans l'application cible et parcours ou URL d'accès.
2. Champs obligatoires : ancien mot de passe, nouveau, confirmation, selon le besoin réel.
3. Règles de validation et conditions de refus, avec résultats observables attendus.
4. Résultat d'une modification réussie : message, navigation, état de la session et
   comportement attendu lors d'une connexion ultérieure.

Ne pas déduire ces règles des habitudes d'autres applications. Les champs cités sont
des points à clarifier, pas des exigences validées.

## Suite prévue après clarification

- Générer une proposition Gherkin liée uniquement aux critères confirmés.
- Revoir le delta par rapport aux tests existants.
- Implémenter les steps/POM avec des locators observés sur le parcours réel.
- Vérifier compilation, résolution Cucumber et exécution sur un compte de test isolé.

Statut : exigences insuffisantes pour un nouveau test exécutable. Aucun scénario,
appel de génération IA ou changement de backlog n'a été effectué lors de cette analyse.

## Inspection de l'application déployée

Inspection du 13 octobre 2026 avec un compte de test créé par le client API existant,
puis connexion réelle via Playwright. Aucun changement de mot de passe effectué.

- Page authentifiée : `https://qacart-todo.herokuapp.com/todo`.
- Navigation observée : Home, Todo, Logout ; aucun accès profil ou paramètres.
- Routes extraites du bundle public `main.8d588c26.chunk.js` : `/login`, `/signup`,
  `/todo/new`, `/todo`, `/`.
- Aucun terme de route ou de fonction change/update/reset/forgot password, profile
  ou settings trouvé par la recherche ciblée dans ce bundle.
- Preuves locales : `logs/account-navigation.json` et `logs/account-routes.json`.

Conclusion limitée au périmètre inspecté : aucun parcours UI de modification du
mot de passe identifié dans cette version déployée. Cela ne démontre pas l'absence
d'une API backend ou d'une autre version de l'application. APPLICATIO-7 reste une
exigence historique à confirmer, et non une fonctionnalité UI prête à automatiser.
La prochaine génération doit porter sur un besoin confirmé et observable, ou attendre
l'implémentation de ce parcours ; aucun test simulant cette fonctionnalité n'est ajouté.
