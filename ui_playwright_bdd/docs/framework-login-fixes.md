# Corrections du framework et reproduction ciblée

Run de vérification : `framework-fix-b3280d5753784731bc2a39978b063b02`.

## Corrections

- Le client API accepte le champ réel `access_token` et conserve la compatibilité
  avec `token`. Une réponse sans jeton valide échoue explicitement.
- `BasePage.goto` utilise la limite de navigation définie dans le World (30 s),
  au lieu d’une limite de 180 s supérieure aux 60 s autorisées par Cucumber.
- Login attend le formulaire ou le dashboard avec une assertion de visibilité.
  Il n’utilise plus une course de promesses dont une branche peut échouer sans
  que l’autre ait terminé.
- Après le clic de connexion, les assertions existantes vérifient le résultat
  attendu ; plus d’attente `networkidle` de 10 s suivie d’un timeout masqué.
- Les paramètres API, durées, statuts et codes réseau sont joints à Allure sans
  corps HTTP, mot de passe ou token.

## Vérification

Le test de régression local maintient une vraie requête réseau de fond ouverte
après l’affichage du dashboard. Login doit terminer sans attendre `networkidle`.
Les tests de diagnostic API, le lint et la compilation TypeScript passent.

Sur la cible QACart, deux scénarios ont été rejoués :

- Login : PASS.
- Todo / longueur : FAIL sur l’assertion de validation, après réussite de la
  création du compte et de la connexion.

La trace réseau montre `POST /api/v1/tasks`, `item` de longueur 201, réponse 201.
La capture affiche la tâche créée. Ce comportement diffère de l’attente du test,
mais la règle cible de 200 caractères reste à confirmer par le métier :
`docs/todo-validation.md` la présente comme une règle proposée.
L’assertion n’a pas été affaiblie et le test n’a pas été ignoré.

L’ancien timeout Login était enregistré sur `And I open the login page` (60 s),
après une création de compte réussie. L’ancien ECONNRESET n’a pas été reproduit ;
sa cause réseau précise n’est pas établie. Aucun retry automatique d’inscription
n’a été ajouté, car une requête interrompue peut déjà avoir créé le compte.
