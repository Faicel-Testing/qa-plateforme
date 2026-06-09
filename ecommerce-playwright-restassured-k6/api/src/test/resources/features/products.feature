@products @regression
Feature: API Produits — GET /api/productsList & POST /api/searchProduct
  En tant que client
  Je veux récupérer la liste des produits et effectuer des recherches via l'API
  Afin d'intégrer le catalogue dans mon application

  @smoke @critical @TC-API-001
  Scenario: TC-API-001 — GET /api/productsList retourne 200 avec la liste des produits
    When je fais un GET sur "/api/productsList"
    Then le status code est 200
    And le body contient "responseCode" égal à 200
    And le body contient une liste "products" non vide

  @TC-API-002
  Scenario: TC-API-002 — POST /api/productsList retourne 405 Method Not Allowed
    When je fais un POST sur "/api/productsList" sans body
    Then le status code est 200
    And le body contient "responseCode" égal à 405
    And le body contient "message" avec "This request method is not supported"

  @smoke @TC-API-003
  Scenario: TC-API-003 — GET /api/brandsList retourne la liste des marques
    When je fais un GET sur "/api/brandsList"
    Then le status code est 200
    And le body contient "responseCode" égal à 200
    And le body contient une liste "brands" non vide

  @TC-API-004
  Scenario: TC-API-004 — PUT /api/brandsList retourne 405
    When je fais un PUT sur "/api/brandsList" sans body
    Then le status code est 200
    And le body contient "responseCode" égal à 405

  @critical @TC-API-005
  Scenario: TC-API-005 — POST /api/searchProduct retourne les produits correspondants
    When je recherche le produit "top" via l'API
    Then le status code est 200
    And le body contient "responseCode" égal à 200
    And les produits retournés contiennent le terme "top"

  @TC-API-006
  Scenario: TC-API-006 — POST /api/searchProduct sans paramètre retourne 400
    When je fais un POST sur "/api/searchProduct" sans body
    Then le status code est 200
    And le body contient "responseCode" égal à 400
    And le body contient "message" avec "Bad request"
