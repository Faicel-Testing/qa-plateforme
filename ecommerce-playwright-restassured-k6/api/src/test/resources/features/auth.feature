@auth @regression
Feature: API Authentification — POST /api/verifyLogin & User Management
  En tant que système
  Je veux vérifier les identifiants et gérer les comptes utilisateurs via l'API
  Afin de sécuriser l'accès à la plateforme

  @smoke @critical @TC-API-007
  Scenario: TC-API-007 — POST /api/verifyLogin avec identifiants valides retourne 200
    When je vérifie la connexion avec l'email "test@example.com" et le mot de passe "Test@1234"
    Then le status code est 200
    And le body contient "responseCode" égal à 200
    And le body contient "message" avec "User exists!"

  @critical @TC-API-008
  Scenario: TC-API-008 — POST /api/verifyLogin avec identifiants invalides retourne 404
    When je vérifie la connexion avec l'email "wrong@email.com" et le mot de passe "wrong"
    Then le status code est 200
    And le body contient "responseCode" égal à 404
    And le body contient "message" avec "User not found!"

  @TC-API-009
  Scenario: TC-API-009 — POST /api/verifyLogin sans email retourne 400
    When je vérifie la connexion sans email avec le mot de passe "Test@1234"
    Then le status code est 200
    And le body contient "responseCode" égal à 400

  @TC-API-010
  Scenario: TC-API-010 — DELETE /api/verifyLogin retourne 405
    When je fais un DELETE sur "/api/verifyLogin"
    Then le status code est 200
    And le body contient "responseCode" égal à 405

  @smoke @critical @TC-API-011
  Scenario: TC-API-011 — GET /api/getUserDetailByEmail retourne le détail utilisateur
    When je récupère les détails de l'utilisateur "test@example.com"
    Then le status code est 200
    And le body contient "responseCode" égal à 200
    And le body contient l'objet "user" avec un email

  @TC-API-012
  Scenario: TC-API-012 — POST /api/createAccount crée un nouveau compte
    When je crée un compte avec les données suivantes:
      | name     | email                     | password  | title | birth_date | birth_month | birth_year | firstname | lastname | company  | address1    | country | zipcode | state  | city  | mobile_number |
      | NewUser  | newuser_test@example.com  | Pass@1234 | Mr    | 1          | January     | 1990       | New       | User     | TestCorp | 123 Test St | India   | 12345   | TestSt | Delhi | 9876543210    |
    Then le status code est 200
    And le body contient "responseCode" égal à 201
    And le body contient "message" avec "User created!"
