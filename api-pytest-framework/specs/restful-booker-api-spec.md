# DOCUMENT DE SPÉCIFICATION API
## Restful-Booker — Hotel Booking API
### https://restful-booker.herokuapp.com

| Attribut  | Valeur |
|-----------|--------|
| Version   | 1.0 |
| Date      | 08 Juin 2026 |
| Auteur    | Faicel GHANEM — Senior QA Automation Engineer |
| Framework | Python Requests + Pytest + Agents IA |
| Statut    | APPROUVÉ |

---

## 1. Présentation de l'API

Restful-Booker est une API REST publique développée par Mark Winteringham, dédiée à la formation en test API. Elle simule un système de réservation hôtelière avec authentification, opérations CRUD complètes et des bugs intentionnels pour pratiquer l'exploration.

### 1.1 Informations générales

| Attribut | Valeur |
|----------|--------|
| Base URL | https://restful-booker.herokuapp.com |
| Documentation | https://restful-booker.herokuapp.com/apidoc/index.html |
| Format | JSON / XML |
| Authentification | Basic Auth + Token Bearer |
| Reset données | Toutes les 10 minutes automatiquement |
| Données initiales | 10 réservations pré-chargées |
| Bugs intentionnels | Oui — pour pratiquer l'exploration QA |

### 1.2 Credentials de test

| Paramètre  | Valeur       | Usage |
|------------|--------------|-------|
| username   | admin        | Authentification token |
| password   | password123  | Authentification token |
| Basic Auth | admin:password123 | PUT / PATCH / DELETE |

### 1.3 Endpoints disponibles

| Méthode | Endpoint | Description | Auth requise |
|---------|----------|-------------|--------------|
| POST    | /auth | Générer un token d'authentification | Non |
| GET     | /booking | Lister toutes les réservations (IDs) | Non |
| GET     | /booking/{id} | Récupérer une réservation par ID | Non |
| POST    | /booking | Créer une nouvelle réservation | Non |
| PUT     | /booking/{id} | Mettre à jour une réservation complète | Oui |
| PATCH   | /booking/{id} | Mettre à jour partiellement une réservation | Oui |
| DELETE  | /booking/{id} | Supprimer une réservation | Oui |
| GET     | /ping | Vérifier la santé de l'API (Health Check) | Non |

---

## 2. Modèle de Données

### 2.1 Objet Booking

```json
{
  "firstname"      : "string",   // Prénom du client          — REQUIS
  "lastname"       : "string",   // Nom du client             — REQUIS
  "totalprice"     : "integer",  // Prix total (entier)        — REQUIS
  "depositpaid"    : "boolean",  // Acompte payé               — REQUIS
  "bookingdates"   : {
    "checkin"      : "date",     // Date arrivée (YYYY-MM-DD)  — REQUIS
    "checkout"     : "date"      // Date départ (YYYY-MM-DD)   — REQUIS
  },
  "additionalneeds": "string"    // Besoins supplémentaires    — OPTIONNEL
}
```

### 2.2 Codes HTTP attendus

| Code HTTP | Statut | Contexte |
|-----------|--------|----------|
| 200 | OK | GET réussi, PUT/PATCH réussi |
| 201 | Created | POST /booking réussi — réservation créée |
| 400 | Bad Request | Corps malformé, données manquantes ou invalides |
| 401 | Unauthorized | Token manquant ou expiré sur PUT/PATCH/DELETE |
| 403 | Forbidden | Token invalide sur PUT/PATCH/DELETE |
| 404 | Not Found | ID de réservation inexistant |
| 405 | Method Not Allowed | Méthode HTTP non supportée sur l'endpoint |
| 500 | Internal Server Error | Erreur serveur inattendue |

---

## 3. User Stories & Critères d'acceptation

### US-API-001 — Authentification (POST /auth)

> En tant que client API, je veux générer un token d'authentification afin d'effectuer des opérations sécurisées sur les réservations.

```gherkin
Feature: Authentification API

  Scenario: Générer un token avec credentials valides
    Given l'API est disponible sur https://restful-booker.herokuapp.com
    When j'envoie une requête POST sur /auth
    And le body contient username "admin" et password "password123"
    Then le status code est 200
    And la réponse contient un champ "token" non vide
    And le token a une longueur > 10 caractères

  Scenario: Tentative avec credentials invalides
    When j'envoie POST /auth avec username "wrong" et password "wrong"
    Then le status code est 200
    And la réponse contient "reason": "Bad credentials"

  Scenario: Body vide
    When j'envoie POST /auth avec un body vide
    Then le status code est 400 ou 200 avec message d'erreur

  Scenario: Champ username manquant
    When j'envoie POST /auth sans le champ username
    Then la réponse indique une erreur d'authentification

  Scenario: Champ password manquant
    When j'envoie POST /auth sans le champ password
    Then la réponse indique une erreur d'authentification
```

---

### US-API-002 — Lister les réservations (GET /booking)

> En tant que client API, je veux récupérer la liste de toutes les réservations afin de consulter les IDs disponibles.

```gherkin
Feature: Lister les réservations

  Scenario: Récupérer toutes les réservations
    When j'envoie GET /booking
    Then le status code est 200
    And la réponse est une liste d'objets contenant "bookingid"
    And la liste contient au moins 1 réservation

  Scenario: Filtrer par prénom
    When j'envoie GET /booking?firstname=John
    Then le status code est 200
    And la réponse filtre les réservations avec firstname John

  Scenario: Filtrer par nom
    When j'envoie GET /booking?lastname=Doe
    Then le status code est 200

  Scenario: Filtrer par date checkin
    When j'envoie GET /booking?checkin=2024-01-01
    Then le status code est 200
    And les réservations retournées ont checkin >= 2024-01-01

  Scenario: Filtrer par date checkout
    When j'envoie GET /booking?checkout=2024-12-31
    Then le status code est 200

  Scenario: Filtre combiné firstname + lastname
    When j'envoie GET /booking?firstname=John&lastname=Doe
    Then le status code est 200

  Scenario: Filtre avec valeur inexistante
    When j'envoie GET /booking?firstname=XYZ_INEXISTANT
    Then le status code est 200
    And la liste retournée est vide
```

---

### US-API-003 — Récupérer une réservation (GET /booking/{id})

> En tant que client API, je veux récupérer le détail d'une réservation par son ID afin de consulter ses informations complètes.

```gherkin
Feature: Récupérer une réservation par ID

  Scenario: Récupérer une réservation existante
    Given il existe une réservation avec l'ID 1
    When j'envoie GET /booking/1
    Then le status code est 200
    And la réponse contient firstname, lastname, totalprice, depositpaid, bookingdates
    And bookingdates contient checkin et checkout

  Scenario: Récupérer une réservation avec ID inexistant
    When j'envoie GET /booking/999999
    Then le status code est 404

  Scenario: ID négatif
    When j'envoie GET /booking/-1
    Then le status code est 404

  Scenario: ID non numérique
    When j'envoie GET /booking/abc
    Then le status code est 404

  Scenario: Accept header JSON
    When j'envoie GET /booking/1 avec header Accept: application/json
    Then le status code est 200
    And Content-Type de la réponse est application/json

  Scenario: Accept header XML
    When j'envoie GET /booking/1 avec header Accept: application/xml
    Then le status code est 200
    And la réponse est au format XML
```

---

### US-API-004 — Créer une réservation (POST /booking)

> En tant que client API, je veux créer une nouvelle réservation afin d'enregistrer un séjour hôtelier.

```gherkin
Feature: Créer une réservation

  Scenario: Créer une réservation avec données valides
    When j'envoie POST /booking avec body:
      | firstname       | John       |
      | lastname        | Doe        |
      | totalprice      | 150        |
      | depositpaid     | true       |
      | checkin         | 2026-07-01 |
      | checkout        | 2026-07-10 |
      | additionalneeds | Breakfast  |
    Then le status code est 200 ou 201
    And la réponse contient un "bookingid" entier > 0
    And la réponse contient l'objet booking créé

  Scenario: Créer sans additionalneeds (optionnel)
    When j'envoie POST /booking sans le champ additionalneeds
    Then le status code est 200 ou 201
    And la réservation est créée avec succès

  Scenario: Créer sans firstname — champ requis manquant
    When j'envoie POST /booking sans le champ firstname
    Then le status code est 400 ou 500

  Scenario: Créer sans lastname
    When j'envoie POST /booking sans le champ lastname
    Then le status code est 400 ou 500

  Scenario: Créer sans totalprice
    When j'envoie POST /booking sans le champ totalprice
    Then le status code est 400 ou 500

  Scenario: Créer sans bookingdates
    When j'envoie POST /booking sans le champ bookingdates
    Then le status code est 400 ou 500

  Scenario: totalprice négatif
    When j'envoie POST /booking avec totalprice = -100
    Then le status code est 400 ou 500

  Scenario: checkin > checkout (dates incohérentes)
    When checkin est "2026-12-31" et checkout est "2026-01-01"
    Then le status code est 400 ou 500

  Scenario: Format date invalide
    When checkin est "31-07-2026" (format invalide)
    Then le status code est 400 ou 500

  Scenario: Body vide
    When j'envoie POST /booking avec body vide {}
    Then le status code est 400 ou 500

  Scenario: totalprice = 0
    When j'envoie POST /booking avec totalprice = 0
    Then le status code est 200 ou 201

  Scenario: Champs avec caractères spéciaux
    When firstname contient "<script>alert('xss')</script>"
    Then le status code est 400 ou la valeur est sanitisée
```

---

### US-API-005 — Mise à jour complète (PUT /booking/{id})

> En tant que client API authentifié, je veux mettre à jour entièrement une réservation afin de modifier toutes ses informations.

```gherkin
Feature: Mise à jour complète d'une réservation

  Scenario: Mise à jour complète avec token valide
    Given je possède un token valide
    And il existe une réservation avec l'ID 1
    When j'envoie PUT /booking/1 avec toutes les données valides
    And le header Cookie contient token=<mon_token>
    Then le status code est 200
    And la réponse contient les données mises à jour

  Scenario: Mise à jour avec Basic Auth
    When j'envoie PUT /booking/1 avec Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=
    Then le status code est 200

  Scenario: PUT sans authentification
    When j'envoie PUT /booking/1 sans header d'authentification
    Then le status code est 403

  Scenario: PUT avec token invalide
    When j'envoie PUT /booking/1 avec token "INVALID_TOKEN"
    Then le status code est 403

  Scenario: PUT sur ID inexistant
    Given je possède un token valide
    When j'envoie PUT /booking/999999
    Then le status code est 404 ou 405

  Scenario: PUT avec champ requis manquant
    Given je possède un token valide
    When j'envoie PUT /booking/1 sans le champ firstname
    Then le status code est 400
```

---

### US-API-006 — Mise à jour partielle (PATCH /booking/{id})

> En tant que client API authentifié, je veux mettre à jour partiellement une réservation afin de modifier uniquement certains champs.

```gherkin
Feature: Mise à jour partielle d'une réservation

  Scenario: PATCH firstname uniquement
    Given je possède un token valide
    When j'envoie PATCH /booking/1 avec {"firstname": "UpdatedName"}
    Then le status code est 200
    And la réponse contient firstname = "UpdatedName"
    And les autres champs sont inchangés

  Scenario: PATCH totalprice uniquement
    When j'envoie PATCH /booking/1 avec {"totalprice": 999}
    Then le status code est 200
    And totalprice = 999 dans la réponse

  Scenario: PATCH sans authentification
    When j'envoie PATCH /booking/1 sans authentification
    Then le status code est 403

  Scenario: PATCH avec token invalide
    When j'envoie PATCH /booking/1 avec token invalide
    Then le status code est 403

  Scenario: PATCH sur ID inexistant
    When j'envoie PATCH /booking/999999 avec token valide
    Then le status code est 404 ou 405

  Scenario: PATCH avec body vide
    When j'envoie PATCH /booking/1 avec body {} et token valide
    Then le status code est 200
    And la réservation est inchangée
```

---

### US-API-007 — Supprimer une réservation (DELETE /booking/{id})

> En tant que client API authentifié, je veux supprimer une réservation afin de l'effacer du système.

```gherkin
Feature: Suppression d'une réservation

  Scenario: Supprimer une réservation existante avec token
    Given je possède un token valide
    And j'ai créé une réservation et récupéré son ID
    When j'envoie DELETE /booking/{id} avec le token
    Then le status code est 201
    And GET /booking/{id} retourne 404 après suppression

  Scenario: Supprimer avec Basic Auth
    When j'envoie DELETE /booking/{id} avec Basic Auth
    Then le status code est 201

  Scenario: DELETE sans authentification
    When j'envoie DELETE /booking/1 sans authentification
    Then le status code est 403

  Scenario: DELETE avec token invalide
    When j'envoie DELETE /booking/1 avec token "FAKE"
    Then le status code est 403

  Scenario: DELETE sur ID inexistant
    Given je possède un token valide
    When j'envoie DELETE /booking/999999
    Then le status code est 404 ou 405

  Scenario: Double DELETE — supprimer une réservation déjà supprimée
    Given j'ai supprimé la réservation {id}
    When j'envoie DELETE /booking/{id} à nouveau
    Then le status code est 404 ou 405
```

---

### US-API-008 — Health Check (GET /ping)

> En tant que client API, je veux vérifier la disponibilité de l'API afin de m'assurer qu'elle est opérationnelle avant de lancer les tests.

```gherkin
Feature: Health Check API

  Scenario: API disponible
    When j'envoie GET /ping
    Then le status code est 201
    And le temps de réponse est inférieur à 3000ms

  Scenario: Vérification avant suite de tests
    Given l'API est disponible (GET /ping retourne 201)
    Then je peux lancer les tests API
```

---

## 4. Récapitulatif des cas de test

| US ID   | Endpoint          | Passants | Non-passants | Total |
|---------|-------------------|----------|--------------|-------|
| US-001  | POST /auth        | 1        | 4            | 5     |
| US-002  | GET /booking      | 5        | 2            | 7     |
| US-003  | GET /booking/{id} | 3        | 4            | 7     |
| US-004  | POST /booking     | 3        | 9            | 12    |
| US-005  | PUT /booking/{id} | 2        | 4            | 6     |
| US-006  | PATCH /booking/{id}| 3       | 4            | 7     |
| US-007  | DELETE /booking/{id}| 2      | 4            | 6     |
| US-008  | GET /ping         | 2        | 0            | 2     |
| **TOTAL** | **8 endpoints** | **21**   | **31**       | **52** |

> Note : Ce nombre peut être étendu à 100-120 cas de test en ajoutant les tests de performance, de charge, de sécurité (injection SQL, XSS) et les tests de contrat de schéma JSON.

---

## 5. Structure du Framework Python Requests

### 5.1 Architecture recommandée

```
api-pytest-framework/
├── agents/
│   ├── api-spec-agent.py      # Lit la spec et génère les tests
│   ├── api-generate-agent.py  # Génère les cas de test
│   ├── api-execute-agent.py   # Exécute les tests via pytest
│   └── api-reporter-agent.py  # Génère le rapport
├── features/
│   ├── auth.feature
│   ├── booking.feature
│   ├── health_check.feature
│   └── steps/
│       ├── auth_steps.py
│       ├── booking_steps.py
│       └── health_check_steps.py
├── tests/
│   ├── test_auth.py           # US-API-001
│   ├── test_get_bookings.py   # US-API-002
│   ├── test_get_booking.py    # US-API-003
│   ├── test_create_booking.py # US-API-004
│   ├── test_update_booking.py # US-API-005
│   ├── test_patch_booking.py  # US-API-006
│   ├── test_delete_booking.py # US-API-007
│   └── test_health_check.py   # US-API-008
├── pages/
│   ├── base_api.py
│   ├── auth_page.py
│   ├── booking_page.py
│   └── health_page.py
├── payloads/
│   └── booking_payloads.py
├── schemas/
│   └── booking_schema.py
├── conftest.py                # Fixtures pytest (token, base_url)
├── config.py                  # Configuration (BASE_URL, credentials)
└── requirements.txt           # requests, pytest, pytest-bdd, allure-pytest
```

### 5.2 Exemple de fixture pytest

```python
# conftest.py
import pytest
import requests

BASE_URL = "https://restful-booker.herokuapp.com"

@pytest.fixture(scope="session")
def auth_token():
    response = requests.post(f"{BASE_URL}/auth", json={
        "username": "admin",
        "password": "password123"
    })
    return response.json()["token"]

@pytest.fixture
def created_booking_id(auth_token):
    response = requests.post(f"{BASE_URL}/booking", json={
        "firstname": "Test", "lastname": "User",
        "totalprice": 100, "depositpaid": True,
        "bookingdates": {"checkin": "2026-07-01", "checkout": "2026-07-10"}
    })
    booking_id = response.json()["bookingid"]
    yield booking_id
    # Teardown — supprimer après le test
    requests.delete(f"{BASE_URL}/booking/{booking_id}",
        cookies={"token": auth_token})
```

---

*Document généré par Faicel GHANEM — Senior QA Automation Engineer | Freelance Paris*
