

## User Stories Jira (2026-06-07T18:18:21.224Z)

**SCRUM-8** [À faire] — Delete Todo — En tant qu'utilisateur, je veux supprimer une tâche terminée
  En tant qu'utilisateur connecté, je veux supprimer des tâches afin de garder ma liste propre.

Critères d'acceptation:
- L'utilisateur peut supprimer une tâche existante
- La tâche disparaît de la liste après suppression
- La suppression est confirmée visuellement

Feature file: Id04_DeleteTodoTest.feature

**SCRUM-7** [À faire] — Todo — En tant qu'utilisateur, je veux créer et gérer mes tâches
  En tant qu'utilisateur connecté, je veux créer des tâches afin de les organiser.

Critères d'acceptation:
- L'utilisateur peut créer une nouvelle tâche
- La tâche apparaît dans la liste après création
- La création avec un champ vide est rejetée

Feature file: Id03_TodoTest.feature

**SCRUM-6** [À faire] — Login — En tant qu'utilisateur inscrit, je veux me connecter à mon compte
  En tant qu'utilisateur inscrit, je veux me connecter afin d'accéder à ma liste de tâches.

Critères d'acceptation:
- La page Login est accessible
- Email et mot de passe valides donnent accès au dashboard
- Les identifiants incorrects affichent un message d'erreur

Feature file: Id02_LoginTest.feature

**SCRUM-5** [À faire] — Signup — En tant que nouvel utilisateur, je veux créer un compte
  En tant que nouvel visiteur, je veux créer un compte afin de pouvoir gérer ma liste de tâches.

Critères d'acceptation:
- La page Signup est accessible
- L'utilisateur peut remplir prénom, nom, email, mot de passe
- Les identifiants valides sont acceptés
- L'utilisateur est redirigé vers le dashboard après inscription

Feature file: Id01_SignupTest.feature

**SCRUM-2** [En cours] — Tâche 2
  (pas de description)

## Traçabilité

### Analyse des User Stories et des Feature Files

#### SCRUM-8 : Suppression d'une tâche
- **Couverture par un test existant :** Oui, `Id04_DeleteTodoTest.feature` contient un scénario qui correspond à la suppression d'une tâche existante.
- **Recommandation :** Aucune, car le test existe déjà.

#### SCRUM-7 : Création et gestion de tâches
- **Couverture par un test existant :** Oui, `Id03_TodoTest.feature` contient un scénario qui correspond à la création d'une nouvelle tâche.
- **Recommandation :** Aucune, car le test existe déjà.

#### SCRUM-6 : Connexion
- **Couverture par un test existant :** Oui, `Id02_LoginTest.feature` contient un scénario qui correspond à la connexion avec des identifiants valides.
- **Recommandation :** Aucune, car le test existe déjà.

#### SCRUM-5 : Inscription
- **Couverture par un test existant :** Oui, `Id01_SignupTest.feature` contient un scénario qui correspond à l'inscription avec des informations valides.
- **Recommandation :** Aucune, car le test existe déjà.

#### SCRUM-2 : Tâche 2
- **Description :** Pas de description fournie.
- **Recommandation :** Compléter la description pour pouvoir analyser la couverture par les tests existants.

### Matrice de Traçabilité

| ID | Description | Feature File | Couverture |
|----|-------------|--------------|------------|
| SCRUM-8 | Suppression d'une tâche | Id04_DeleteTodoTest.feature | Oui |
| SCRUM-7 | Création et gestion de tâches | Id03_TodoTest.feature | Oui |
| SCRUM-6 | Connexion | Id02_LoginTest.feature | Oui |
| SCRUM-5 | Inscription | Id01_SignupTest.feature | Oui |
| SCRUM-2 | Tâche 2 | - | Non (description manquante) |

### Recommandations Générales
- Pour **SCRUM-2**, il est recommandé de compléter la description pour permettre une analyse appropriée de la couverture par les tests existants.
- Pour les autres user stories, les tests existants couvrent les fonctionnalités principales, mais il est toujours important de vérifier si les critères d'acceptation spécifiques sont bien pris en compte dans les scénarios de test.
- Il est également recommandé de régulièrement revoir et de mettre à jour les tests pour s'assurer qu'ils restent pertinents et complets par rapport aux exigences du projet.

## User Stories Jira (2026-06-07T18:36:20.349Z)

**SCRUM-9** [À faire] — En tant qu'utilisateur je veux me connecter avec email et mot de passe
  En tant qu'utilisateur enregistré Je veux me connecter avec email et mot de passe Afin d'accéder à mon espace personnel Critères d'acceptation : GIVEN je suis sur la page login WHEN je saisis email valide et mot de passe correct THEN je suis redirigé vers le dashboard GIVEN je saisis un mot de passe incorrect WHEN je clique Se connecter THEN un message d'erreur s'affiche GIVEN je saisis un email invalide WHEN je clique Se connecter THEN un message Email invalide s'affiche

**SCRUM-8** [À faire] — Delete Todo — En tant qu'utilisateur, je veux supprimer une tâche terminée
  En tant qu'utilisateur connecté, je veux supprimer des tâches afin de garder ma liste propre.

Critères d'acceptation:
- L'utilisateur peut supprimer une tâche existante
- La tâche disparaît de la liste après suppression
- La suppression est confirmée visuellement

Feature file: Id04_DeleteTodoTest.feature

**SCRUM-7** [À faire] — Todo — En tant qu'utilisateur, je veux créer et gérer mes tâches
  En tant qu'utilisateur connecté, je veux créer des tâches afin de les organiser.

Critères d'acceptation:
- L'utilisateur peut créer une nouvelle tâche
- La tâche apparaît dans la liste après création
- La création avec un champ vide est rejetée

Feature file: Id03_TodoTest.feature

**SCRUM-6** [À faire] — Login — En tant qu'utilisateur inscrit, je veux me connecter à mon compte
  En tant qu'utilisateur inscrit, je veux me connecter afin d'accéder à ma liste de tâches.

Critères d'acceptation:
- La page Login est accessible
- Email et mot de passe valides donnent accès au dashboard
- Les identifiants incorrects affichent un message d'erreur

Feature file: Id02_LoginTest.feature

**SCRUM-5** [À faire] — Signup — En tant que nouvel utilisateur, je veux créer un compte
  En tant que nouvel visiteur, je veux créer un compte afin de pouvoir gérer ma liste de tâches.

Critères d'acceptation:
- La page Signup est accessible
- L'utilisateur peut remplir prénom, nom, email, mot de passe
- Les identifiants valides sont acceptés
- L'utilisateur est redirigé vers le dashboard après inscription

Feature file: Id01_SignupTest.feature

**SCRUM-2** [En cours] — Tâche 2
  (pas de description)

## Traçabilité

### Analyse des User Stories et des Feature Files existants

#### User Story SCRUM-9
- **Description** : En tant qu'utilisateur, je veux me connecter avec email et mot de passe afin d'accéder à mon espace personnel.
- **Couverture par un test existant** : Partiellement couvert par `Id02_LoginTest.feature`.
- **Scénario Gherkin à créer** :
  ```gherkin
  @ui @login @SCRUM-9 @negative @regression
  Feature: Login Validation

  Scenario: SCRUM-9_LoginNegative - invalid credentials show an error
    Given I open the login page
    When I login with invalid credentials
    Then I should see a login error message

  Scenario: SCRUM-9_LoginNegative - login with invalid email format should fail
    Given I open the login page
    When I login with invalid email format
    Then I should see an invalid email error

  Scenario: SCRUM-9_LoginNegative - login with wrong password should fail
    Given I open the login page
    When I login with correct email and wrong password
    Then I should see an authentication error message
  ```
#### User Story SCRUM-8
- **Description** : En tant qu'utilisateur, je veux supprimer une tâche terminée afin de garder ma liste propre.
- **Couverture par un test existant** : Couvert par `Id04_DeleteTodoTest.feature`.
- **Scénario Gherkin à créer** : Non nécessaire, déjà couvert.

#### User Story SCRUM-7
- **Description** : En tant qu'utilisateur, je veux créer et gérer mes tâches.
- **Couverture par un test existant** : Partiellement couvert par `Id03_TodoTest.feature`.
- **Scénario Gherkin à créer** :
  ```gherkin
  @ui @todo @SCRUM-7 @regression
  Feature: Todo Management

  Scenario: SCRUM-7_TodoTest - user can view and manage their todos
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I add multiple new todo items
    Then I should see all the todo items in the list
    And I should be able to mark a todo as completed
    And I should see the todo item as completed in the list
  ```

#### User Story SCRUM-6
- **Description** : En tant qu'utilisateur inscrit, je veux me connecter à mon compte.
- **Couverture par un test existant** : Couvert par `Id02_LoginTest.feature`.
- **Scénario Gherkin à créer** : Non nécessaire, déjà couvert.

#### User Story SCRUM-5
- **Description** : En tant que nouvel utilisateur, je veux créer un compte.
- **Couverture par un test existant** : Partiellement couvert par `Id01_SignupTest.feature`.
- **Scénario Gherkin à créer** :
  ```gherkin
  @ui @signup @SCRUM-5 @regression
  Feature: Signup

  Scenario: SCRUM-5_SignupTest - user can signup and access their account
    Given I open the signup page
    When I signup with a new random user
    Then I should be logged in after signup
    And I should see my account details correctly
  ```

#### User Story SCRUM-2
- **Description** : Non disponible.
- **Couverture par un test existant** : Non applicable.
- **Scénario Gherkin à créer** : Non applicable, description manquante.

### Matrice de Traçabilité

| ID User Story | Description | Couverture | Fichier de Test associé |
| --- | --- | --- | --- |
| SCRUM-9 | Connexion avec email et mot de passe | Partiellement couvert | `Id02_LoginTest.feature` |
| SCRUM-8 | Suppression d'une tâche | Couvert | `Id04_DeleteTodoTest.feature` |
| SCRUM-7 | Création et gestion de tâches | Partiellement couvert | `Id03_TodoTest.feature` |
| SCRUM-6 | Connexion au compte | Couvert | `Id02_LoginTest.feature` |
| SCRUM-5 | Création d'un compte | Partiellement couvert | `Id01_SignupTest.feature` |
| SCRUM-2 | Non disponible | Non applicable | - |

### Recommandations
- Réviser les scénarios de test existants pour s'assurer qu'ils couvrent entièrement les critères d'acceptation de chaque user story.
- Ajouter les nouveaux scénarios Gherkin proposés pour les user stories qui ne sont pas entièrement couvertes.
- Mettre à jour les fichiers de test existants pour refléter les changements ou ajouts effectués.
- Utiliser les matrice de traçabilité pour suivre l'évolution des tests et garantir que chaque exigence soit bien testée.

## User Stories Jira (2026-06-07T19:23:48.647Z)

**SCRUM-9** [À faire] — En tant qu'utilisateur je veux me connecter avec email et mot de passe
  En tant qu'utilisateur enregistré Je veux me connecter avec email et mot de passe Afin d'accéder à mon espace personnel Critères d'acceptation : GIVEN je suis sur la page login WHEN je saisis email valide et mot de passe correct THEN je suis redirigé vers le dashboard GIVEN je saisis un mot de passe incorrect WHEN je clique Se connecter THEN un message d'erreur s'affiche GIVEN je saisis un email invalide WHEN je clique Se connecter THEN un message Email invalide s'affiche

**SCRUM-8** [À faire] — Delete Todo — En tant qu'utilisateur, je veux supprimer une tâche terminée
  En tant qu'utilisateur connecté, je veux supprimer des tâches afin de garder ma liste propre.

Critères d'acceptation:
- L'utilisateur peut supprimer une tâche existante
- La tâche disparaît de la liste après suppression
- La suppression est confirmée visuellement

Feature file: Id04_DeleteTodoTest.feature

**SCRUM-7** [À faire] — Todo — En tant qu'utilisateur, je veux créer et gérer mes tâches
  En tant qu'utilisateur connecté, je veux créer des tâches afin de les organiser.

Critères d'acceptation:
- L'utilisateur peut créer une nouvelle tâche
- La tâche apparaît dans la liste après création
- La création avec un champ vide est rejetée

Feature file: Id03_TodoTest.feature

**SCRUM-6** [À faire] — Login — En tant qu'utilisateur inscrit, je veux me connecter à mon compte
  En tant qu'utilisateur inscrit, je veux me connecter afin d'accéder à ma liste de tâches.

Critères d'acceptation:
- La page Login est accessible
- Email et mot de passe valides donnent accès au dashboard
- Les identifiants incorrects affichent un message d'erreur

Feature file: Id02_LoginTest.feature

**SCRUM-5** [À faire] — Signup — En tant que nouvel utilisateur, je veux créer un compte
  En tant que nouvel visiteur, je veux créer un compte afin de pouvoir gérer ma liste de tâches.

Critères d'acceptation:
- La page Signup est accessible
- L'utilisateur peut remplir prénom, nom, email, mot de passe
- Les identifiants valides sont acceptés
- L'utilisateur est redirigé vers le dashboard après inscription

Feature file: Id01_SignupTest.feature

**SCRUM-2** [En cours] — Tâche 2
  (pas de description)

## Traçabilité

## Analyse des User Stories Jira et Feature Files Playwright

### 1. SCRUM-9 - Connexion avec email et mot de passe

* La story est couverte par le fichier `Id02_LoginTest.feature` et `Id05_LoginNegativeTest.feature`
* Le scénario `Id02_LoginTest` vérifie que l'utilisateur peut se connecter avec succès, tandis que les scénarios `Id05_LoginNegativeTest` vérifient les cas où les informations de connexion sont invalides.

### 2. SCRUM-8 - Suppression d'une tâche

* La story est couverte par le fichier `Id04_DeleteTodoTest.feature`
* Le scénario `Id04_DeleteTodoTest` vérifie que l'utilisateur peut supprimer une tâche avec succès.

### 3. SCRUM-7 - Création et gestion de tâches

* La story est couverte par le fichier `Id03_TodoTest.feature`
* Le scénario `Id03_TodoTest` vérifie que l'utilisateur peut créer une nouvelle tâche avec succès.

### 4. SCRUM-6 - Connexion

* La story est couverte par le fichier `Id02_LoginTest.feature`
* Le scénario `Id02_LoginTest` vérifie que l'utilisateur peut se connecter avec succès.

### 5. SCRUM-5 - Inscription

* La story est couverte par le fichier `Id01_SignupTest.feature`
* Le scénario `Id01_SignupTest` vérifie que l'utilisateur peut s'inscrire avec succès.

### 6. SCRUM-2 - Tâche 2

* La story n'est pas couverte par aucun fichier de test existant.
* Il est recommandé de créer un nouveau fichier de test pour cette story.

## Matrice de Traçabilité

| User Story | Fichier de Test | Scénario |
| --- | --- | --- |
| SCRUM-9 | Id02_LoginTest.feature | Id02_LoginTest |
| SCRUM-9 | Id05_LoginNegativeTest.feature | Id05_LoginNegativeTest |
| SCRUM-8 | Id04_DeleteTodoTest.feature | Id04_DeleteTodoTest |
| SCRUM-7 | Id03_TodoTest.feature | Id03_TodoTest |
| SCRUM-6 | Id02_LoginTest.feature | Id02_LoginTest |
| SCRUM-5 | Id01_SignupTest.feature | Id01_SignupTest |
| SCRUM-2 |  |  |

## Recommandations

* Créer un nouveau fichier de test pour la story SCRUM-2.
* Ajouter des scénarios pour les cas où les informations de connexion sont invalides dans le fichier `Id02_LoginTest.feature`.
* Vérifier que les scénarios existants couvrent tous les cas de figure pour les stories SCRUM-7 et SCRUM-8.

## Scénario Gherkin pour la story SCRUM-2

```gherkin
@ui @todo @SCRUM-2 @regression
Feature: Tâche 2

  Scenario: SCRUM-2 - utilisateur peut créer une nouvelle tâche
    Given I have a user in fixture
    And I open the login page
    When I login using fixture user
    And I create a new task
    Then I should see the new task in the list
```