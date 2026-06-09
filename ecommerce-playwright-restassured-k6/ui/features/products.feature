@products @regression
Feature: Catalogue Produits — Navigation & Recherche
  En tant que visiteur ou client
  Je veux parcourir et rechercher des produits
  Afin de trouver ce qui m'intéresse et l'ajouter au panier

  @smoke @TC-UI-006
  Scenario: TC-UI-006 — Affichage de la liste des produits
    Given je suis sur la page des produits
    Then la liste des produits est affichée
    And le nombre de produits est supérieur à 0

  @TC-UI-007
  Scenario: TC-UI-007 — Voir le détail d'un produit
    Given je suis sur la page des produits
    When je clique sur "View Product" du premier produit
    Then je suis sur la page de détail du produit
    And le nom du produit est affiché
    And le prix du produit est affiché

  @smoke @critical @TC-UI-008
  Scenario: TC-UI-008 — Recherche d'un produit existant
    Given je suis sur la page des produits
    When je recherche le produit "Top"
    Then les résultats de recherche sont affichés
    And le titre "Searched Products" est visible
    And au moins 1 produit est trouvé

  @TC-UI-009
  Scenario: TC-UI-009 — Recherche d'un produit inexistant
    Given je suis sur la page des produits
    When je recherche le produit "XYZNOTEXIST999"
    Then aucun produit n'est trouvé dans les résultats

  @TC-UI-010
  Scenario: TC-UI-010 — Ajout d'un produit au panier depuis la liste
    Given je suis sur la page des produits
    When j'ajoute le premier produit au panier
    Then la modale de confirmation apparaît
    When je clique sur "Continue Shopping"
    Then je reste sur la page des produits

  @TC-UI-011
  Scenario: TC-UI-011 — Ajout au panier depuis la page détail avec quantité personnalisée
    Given je suis sur la page des produits
    When je clique sur "View Product" du premier produit
    And je change la quantité à 3
    And j'ajoute au panier depuis la page détail
    Then la modale de confirmation apparaît
