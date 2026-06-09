@cart @regression
Feature: Panier — Gestion des articles
  En tant que client
  Je veux gérer mon panier d'achats
  Afin de préparer ma commande

  @smoke @critical @TC-UI-012
  Scenario: TC-UI-012 — Vérifier qu'un produit ajouté apparaît dans le panier
    Given je suis sur la page des produits
    When j'ajoute le premier produit au panier
    And je clique sur "View Cart" dans la modale
    Then je suis sur la page du panier
    And le panier contient au moins 1 article

  @TC-UI-013
  Scenario: TC-UI-013 — Supprimer un article du panier
    Given j'ai un produit dans mon panier
    When je supprime le premier article du panier
    Then le panier est vide

  @TC-UI-014
  Scenario: TC-UI-014 — Accéder au checkout depuis le panier
    Given je suis connecté avec "testuser@example.com" et "Test@1234"
    And j'ai un produit dans mon panier
    When je clique sur "Proceed To Checkout"
    Then je suis sur la page de confirmation de commande

  @TC-UI-015
  Scenario: TC-UI-015 — Panier vide affiche un message approprié
    Given je suis sur la page du panier sans articles
    Then le message de panier vide est affiché
