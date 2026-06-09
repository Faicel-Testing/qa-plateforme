@auth @regression
Feature: Authentication — Login & Register
  En tant qu'utilisateur de la plateforme e-commerce
  Je veux pouvoir m'authentifier et gérer mon compte
  Afin d'accéder aux fonctionnalités réservées aux membres

  Background:
    Given je suis sur la page de connexion

  @smoke @critical @TC-UI-001
  Scenario: TC-UI-001 — Connexion avec des identifiants valides
    When je saisis l'email "testuser@example.com" et le mot de passe "Test@1234"
    And je clique sur le bouton de connexion
    Then je suis redirigé vers la page d'accueil
    And je vois "Logged in as" dans la barre de navigation

  @smoke @critical @TC-UI-002
  Scenario: TC-UI-002 — Déconnexion réussie
    Given je suis connecté avec "testuser@example.com" et "Test@1234"
    When je clique sur le lien de déconnexion
    Then je suis redirigé vers la page de connexion

  @TC-UI-003
  Scenario: TC-UI-003 — Connexion avec un email invalide
    When je saisis l'email "wrong@email.com" et le mot de passe "WrongPass"
    And je clique sur le bouton de connexion
    Then je vois le message d'erreur "Your email or password is incorrect!"

  @TC-UI-004
  Scenario: TC-UI-004 — Connexion avec mot de passe vide
    When je saisis l'email "testuser@example.com" et le mot de passe ""
    And je clique sur le bouton de connexion
    Then le formulaire ne peut pas être soumis

  @TC-UI-005
  Scenario: TC-UI-005 — Inscription avec un email déjà utilisé
    When je saisis le nom "Test User" et l'email "testuser@example.com" pour l'inscription
    And je clique sur le bouton d'inscription
    Then je vois le message "Email Address already exist!"
