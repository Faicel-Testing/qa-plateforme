# QA Analysis — API Framework

## Application testée
- **URL** : `https://restful-booker.herokuapp.com`
- **Type** : REST API — gestion de réservations (Booking API)

## Framework
- Python + pytest + requests
- Allure reporting
- Agents IA : Groq (llama-3.3-70b-versatile) / Ollama (fallback local)

## Couverture implémentée

| Fichier test | User Story | Endpoint | Statut |
|---|---|---|---|
| `test_auth.py` | US-API-001 | `POST /auth` | 🔲 À implémenter |
| `test_get_bookings.py` | US-API-002 | `GET /booking` | 🔲 À implémenter |
| `test_get_booking.py` | US-API-003 | `GET /booking/{id}` | 🔲 À implémenter |
| `test_create_booking.py` | US-API-004 | `POST /booking` | 🔲 À implémenter |
| `test_update_booking.py` | US-API-005 | `PUT /booking/{id}` | 🔲 À implémenter |
| `test_patch_booking.py` | US-API-006 | `PATCH /booking/{id}` | 🔲 À implémenter |
| `test_delete_booking.py` | US-API-007 | `DELETE /booking/{id}` | 🔲 À implémenter |
| `test_health_check.py` | US-API-008 | `GET /ping` | 🔲 À implémenter |

## User Stories

### US-API-001 — Authentification
- **En tant que** : client API
- **Je veux** : obtenir un token d'authentification
- **Afin de** : accéder aux endpoints protégés
- **Critères** :
  - `POST /auth` avec credentials valides → 200 + token
  - `POST /auth` avec credentials invalides → 200 + `"Bad credentials"`

### US-API-002 — Liste des réservations
- **En tant que** : client API
- **Je veux** : récupérer la liste de toutes les réservations
- **Afin de** : consulter les bookings existants
- **Critères** :
  - `GET /booking` → 200 + liste d'IDs
  - Filtrage par `firstname`, `lastname`, `checkin`, `checkout`

### US-API-003 — Détail d'une réservation
- **En tant que** : client API
- **Je veux** : récupérer une réservation par son ID
- **Afin de** : consulter ses détails complets
- **Critères** :
  - `GET /booking/{id}` valide → 200 + objet booking
  - `GET /booking/{id}` inexistant → 404

### US-API-004 — Créer une réservation
- **En tant que** : client API
- **Je veux** : créer une nouvelle réservation
- **Afin de** : enregistrer un séjour
- **Critères** :
  - `POST /booking` avec payload valide → 200 + bookingid + booking
  - Champs obligatoires : `firstname`, `lastname`, `totalprice`, `depositpaid`, `bookingdates`

### US-API-005 — Mettre à jour une réservation (PUT)
- **En tant que** : client API authentifié
- **Je veux** : remplacer entièrement une réservation
- **Afin de** : corriger toutes ses informations
- **Critères** :
  - `PUT /booking/{id}` avec token valide → 200 + booking mis à jour
  - Sans token → 403

### US-API-006 — Mettre à jour partiellement (PATCH)
- **En tant que** : client API authentifié
- **Je veux** : modifier certains champs d'une réservation
- **Afin de** : faire une mise à jour partielle
- **Critères** :
  - `PATCH /booking/{id}` avec token valide → 200 + champs mis à jour
  - Sans token → 403

### US-API-007 — Supprimer une réservation
- **En tant que** : client API authentifié
- **Je veux** : supprimer une réservation
- **Afin de** : nettoyer les données obsolètes
- **Critères** :
  - `DELETE /booking/{id}` avec token valide → 201
  - Sans token → 403
  - ID inexistant → 405

### US-API-008 — Health Check
- **En tant que** : client API
- **Je veux** : vérifier que l'API est disponible
- **Afin de** : valider l'environnement avant les tests
- **Critères** :
  - `GET /ping` → 201 `Created`
