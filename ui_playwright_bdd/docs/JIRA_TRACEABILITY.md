# Jira ↔ Playwright Traceability Matrix

_2026-06-07T19:23:48.647Z — Projet: SCRUM — groq / llama-3.3-70b-versatile_

## Stories analysées (6)

- [SCRUM-9](https://kaysganem.atlassian.net/browse/SCRUM-9) [À faire] — En tant qu'utilisateur je veux me connecter avec email et mot de passe
- [SCRUM-8](https://kaysganem.atlassian.net/browse/SCRUM-8) [À faire] — Delete Todo — En tant qu'utilisateur, je veux supprimer une tâche terminée
- [SCRUM-7](https://kaysganem.atlassian.net/browse/SCRUM-7) [À faire] — Todo — En tant qu'utilisateur, je veux créer et gérer mes tâches
- [SCRUM-6](https://kaysganem.atlassian.net/browse/SCRUM-6) [À faire] — Login — En tant qu'utilisateur inscrit, je veux me connecter à mon compte
- [SCRUM-5](https://kaysganem.atlassian.net/browse/SCRUM-5) [À faire] — Signup — En tant que nouvel utilisateur, je veux créer un compte
- [SCRUM-2](https://kaysganem.atlassian.net/browse/SCRUM-2) [En cours] — Tâche 2

## Analyse et traçabilité

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
