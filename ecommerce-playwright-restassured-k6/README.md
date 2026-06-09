# E-commerce QA — Playwright BDD + REST Assured + K6

[![UI Tests](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci.yml/badge.svg?label=UI)](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci.yml)
[![API Tests](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci.yml/badge.svg?label=API)](https://github.com/Faicel-Testing/qa-plateforme/actions/workflows/ci.yml)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4-blue?logo=typescript)](https://www.typescriptlang.org/)
[![Java](https://img.shields.io/badge/Java-17-orange?logo=openjdk)](https://openjdk.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.44-green?logo=playwright)](https://playwright.dev/)
[![REST Assured](https://img.shields.io/badge/REST_Assured-5.4-brightgreen)](https://rest-assured.io/)
[![K6](https://img.shields.io/badge/K6-Performance-purple?logo=k6)](https://k6.io/)

> **Playwright BDD + REST Assured + K6** — Couverture complète d'une application e-commerce : UI fonctionnel, API backend et tests de performance dans un seul pipeline CI/CD.

---

## Vue d'ensemble

```
E-commerce (AutomationExercise)
         │
         ├── UI Layer        Playwright BDD TypeScript  → Tests navigateur
         ├── API Layer       REST Assured Java BDD      → Tests backend
         └── Perf Layer      K6 JavaScript              → Tests de charge
                   │
                   └── Allure Report unifié  →  GitHub Pages
```

**Site testé** : [automationexercise.com](https://automationexercise.com) — plateforme e-commerce avec catalogue produits, panier, checkout et gestion utilisateur.

---

## Architecture

```
ecommerce-playwright-restassured-k6/
│
├── ui/                              Playwright BDD — TypeScript
│   ├── features/
│   │   ├── auth.feature             Login, Register, Logout (5 TCs)
│   │   ├── products.feature         Catalogue, Recherche, Détail (6 TCs)
│   │   └── cart.feature             Panier, Checkout (4 TCs)
│   ├── pages/                       Page Object Model
│   │   ├── BasePage.ts
│   │   ├── LoginPage.ts
│   │   ├── HomePage.ts
│   │   ├── ProductsPage.ts
│   │   └── CartPage.ts
│   ├── steps/                       Step definitions Cucumber
│   │   ├── authSteps.ts
│   │   ├── productsSteps.ts
│   │   ├── cartSteps.ts
│   │   └── hooks.ts                 Screenshots auto sur échec
│   ├── support/
│   │   └── world.ts                 PlaywrightWorld (Browser/Context/Page)
│   ├── cucumber.json
│   ├── tsconfig.json
│   └── package.json
│
├── api/                             REST Assured BDD — Java 17
│   ├── src/test/resources/features/
│   │   ├── products.feature         GET /productsList, POST /searchProduct (6 TCs)
│   │   └── auth.feature             /verifyLogin, /createAccount, /getUserDetail (6 TCs)
│   ├── src/test/java/com/automationexercise/
│   │   ├── steps/
│   │   │   ├── ProductSteps.java
│   │   │   └── AuthSteps.java
│   │   ├── runners/
│   │   │   └── TestRunner.java
│   │   └── config/
│   │       └── Config.java
│   └── pom.xml
│
├── perf/                            K6 — JavaScript
│   ├── scripts/
│   │   ├── smoke.js                 1 VU × 5 itérations — sanity check
│   │   ├── load.js                  50 VUs × 2 min — charge nominale
│   │   └── stress.js                200 VUs — point de rupture
│   └── thresholds/
│       └── quality-gate.js          Seuils Performance Quality Gate
│
├── .github/workflows/
│   └── ci.yml                       Pipeline unifié — 4 jobs parallèles
└── README.md
```

---

## Couverture de tests

### UI — Playwright BDD (15 TCs)

| Feature | TCs | Tags |
|---------|-----|------|
| Authentification | 5 | `@auth` · `@smoke` · `@critical` |
| Catalogue Produits | 6 | `@products` · `@smoke` · `@critical` |
| Panier | 4 | `@cart` · `@smoke` · `@critical` |

### API — REST Assured (12 TCs)

| Endpoint | TCs | Tags |
|----------|-----|------|
| GET /api/productsList | 2 | `@products` · `@smoke` · `@critical` |
| GET /api/brandsList | 2 | `@products` · `@smoke` |
| POST /api/searchProduct | 2 | `@products` · `@critical` |
| POST /api/verifyLogin | 3 | `@auth` · `@smoke` · `@critical` |
| GET /api/getUserDetailByEmail | 1 | `@auth` · `@smoke` |
| POST /api/createAccount | 1 | `@auth` |
| DELETE /api/verifyLogin | 1 | `@auth` |

### Performance — K6

| Script | VUs | Durée | Objectif |
|--------|-----|-------|----------|
| `smoke.js` | 1 | ~30s | Vérification sanity des endpoints |
| `load.js` | 50 | 2 min | Charge nominale — p95 < 5s |
| `stress.js` | 200 | ~2 min | Point de rupture — p95 < 10s |

---

## Quality Gate Performance

| Critère | Seuil Smoke | Seuil Load | Seuil Stress |
|---------|-------------|------------|--------------|
| Error Rate | < 1% | < 5% | < 10% |
| P95 Response Time | < 3s | < 5s | < 10s |
| P99 Response Time | < 5s | < 8s | — |
| HTTP Failures | < 1% | < 5% | < 10% |

---

## Pipeline CI/CD

```
git push
    │
    ├── [ui-tests]       Node 20 → npm ci → playwright install → cucumber-js
    ├── [api-tests]      Java 17 → mvn test → allure-results
    ├── [perf-tests]     K6 install → smoke.js → JSON results
    │         (parallèles)
    └── [allure-report]  Merge ui + api results → allure generate → GitHub Pages
```

**Déclencheurs :**
- `push` sur `main` ou `feature/**`
- `pull_request` vers `main`
- `workflow_dispatch` (choix : all / ui / api / perf)
- `schedule` : lundi–vendredi 06h00 UTC

---

## Démarrage rapide

### UI — Playwright

```bash
cd ui
npm install
npx playwright install chromium

# Tous les tests
npm test

# Par tag
npm run test:smoke
npm run test:critical
npm run test:auth
npm run test:cart

# Rapport Allure
npm run allure:generate && npm run allure:serve
```

### API — REST Assured

```bash
cd api

# Tous les tests
mvn test

# Par tag Cucumber
mvn test -Dcucumber.filter.tags="@smoke"
mvn test -Dcucumber.filter.tags="@critical"

# Rapport Allure
mvn allure:serve
```

### Performance — K6

```bash
# Installation K6
# Linux: sudo apt-get install k6
# Mac:   brew install k6
# Win:   choco install k6

# Smoke test (rapide)
k6 run perf/scripts/smoke.js

# Load test
k6 run perf/scripts/load.js

# Stress test
k6 run perf/scripts/stress.js

# Avec output JSON
k6 run perf/scripts/load.js --out json=perf/results/load-results.json
```

---

## Stack technique

```
UI Testing        Playwright 1.44 + Cucumber.js 10 + TypeScript 5.4
API Testing       REST Assured 5.4 + Cucumber JVM 7.15 + Java 17
Performance       K6 (Grafana)
Reporting         Allure 2.29 (unifié UI + API)
CI/CD             GitHub Actions — 4 jobs parallèles
Pages             GitHub Pages — rapport live
```

---

*Framework développé sur [AutomationExercise](https://automationexercise.com) — Playwright BDD + REST Assured + K6.*
