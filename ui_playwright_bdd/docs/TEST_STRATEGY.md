# Stratégie de Test — UI Playwright BDD

> **Application sous test :** qacart-todo.herokuapp.com  
> **Framework :** Playwright + CucumberJS BDD (TypeScript) + 10 agents IA  
> **Version :** 1.0.0 — Juin 2026

---

## Table des matières

1. [Contexte et objectifs](#1-contexte-et-objectifs)
2. [Périmètre de test](#2-périmètre-de-test)
3. [Architecture du framework](#3-architecture-du-framework)
4. [Types de tests](#4-types-de-tests)
5. [Couverture fonctionnelle](#5-couverture-fonctionnelle)
6. [Stratégie de données de test](#6-stratégie-de-données-de-test)
7. [Environnements](#7-environnements)
8. [Critères de qualité (Quality Gate)](#8-critères-de-qualité-quality-gate)
9. [Gestion des risques](#9-gestion-des-risques)
10. [Bugs connus et limitations applicatives](#10-bugs-connus-et-limitations-applicatives)
11. [Pipeline CI/CD](#11-pipeline-cicd)
12. [Métriques et reporting](#12-métriques-et-reporting)
13. [Stratégie par agent IA](#13-stratégie-par-agent-ia)
14. [Conventions et bonnes pratiques](#14-conventions-et-bonnes-pratiques)

---

## 1. Contexte et objectifs

### Application sous test

**qacart-todo.herokuapp.com** est une application web Todo SPA (Single Page Application) React avec :
- Authentification utilisateur (inscription, connexion, déconnexion)
- Gestion de tâches (création, suppression)
- Gestion de profil (mise à jour email, mot de passe, suppression de compte)

### Objectifs de la stratégie de test

| Objectif | Mesure |
|----------|--------|
| Détecter les régressions avant mise en production | Pass rate ≥ 90% sur toute la suite |
| Couvrir tous les chemins critiques | 100% des scénarios `@critical` et `@smoke` verts |
| Identifier les tests instables | Flaky rate ≤ 20% |
| Réduire le temps de détection des bugs | Pipeline complet < 10 min |
| Automatiser l'analyse des échecs | RCA IA sur 100% des échecs |

### Hors périmètre

- Tests de charge / performance
- Tests de sécurité offensifs (pentest)
- Tests d'accessibilité (WCAG)
- Tests sur navigateurs mobiles

---

## 2. Périmètre de test

### Domaines fonctionnels couverts

| ID | Domaine | Positif | Négatif | Tags |
|----|---------|---------|---------|------|
| Id01 | Inscription (Signup) | ✅ | ✅ 7 scénarios | `@signup` `@smoke` `@critical` `@regression` |
| Id02 | Connexion (Login) | ✅ | — | `@login` `@smoke` `@critical` `@regression` |
| Id03 | Gestion Todo | ✅ | ✅ 4 scénarios | `@todo` `@smoke` `@regression` |
| Id04 | Suppression Todo | ✅ | ✅ 4 scénarios | `@todo` `@regression` |
| Id05 | Connexion invalide | — | ✅ 7 scénarios | `@login` `@negative` `@regression` |
| Id09 | API Setup — Pattern Senior | ✅ | ✅ | `@api-setup` `@smoke` `@critical` `@negative` `@regression` |

> Id06/07/08 (Password Update, Email Update, Account Deletion) retirés : `qacart-todo.herokuapp.com` n'expose aucune page `/profile` (SPA React sans cette route). User stories Jira spéculatives (SCRUM-18/19/20) jamais implémentées côté application.

### Bilan couverture

```
29 scénarios  |  9 fichiers .feature  |  4 Page Objects
```

---

## 3. Architecture du framework

```
ui_playwright_bdd/
├── src/
│   ├── features/        Scénarios Gherkin (source de vérité BDD)
│   ├── steps/           Step definitions TypeScript (1 fichier / feature)
│   ├── pages/           Page Object Model (abstraction UI)
│   ├── core/world.ts    Contexte CucumberJS (browser, user, lastTodo…)
│   ├── hooks/           Before/After : screenshots, Allure, cleanup
│   └── support/         Sélecteurs, données de test, fixtures
├── scripts/agents/      10 agents IA (génération, analyse, reporting…)
├── logs/                Traces LLM + état circuit breaker + cache
├── memory/              Mémoire épisodique (historique par test case)
└── docs/                Rapports HTML, RCA, baseline, stratégie
```

### Patron de conception : Page Object Model

Chaque page de l'application a sa propre classe :

```
BasePage          → navigation, logout, assertErrorMessage
 ├── SignupPage   → fillSignupForm, signup, assertSignupError
 ├── LoginPage    → login, assertLoginError, assertLoggedIn
 └── TodoPage     → addTodo, deleteTodo, attemptAddTodo, assertTodoValidationError
```

**Règle** : aucun sélecteur CSS dans les step definitions — toujours dans les pages.

### Gestion du contexte inter-étapes

La classe `CustomWorld` porte les données entre les étapes Gherkin :

```typescript
class CustomWorld {
  page       : Page          // instance Playwright
  user?      : TestUser      // utilisateur courant (fixture)
  lastTodo?  : string        // dernier todo créé/ciblé
  consoleLogs: string[]      // logs console capturés
  pageErrors : string[]      // erreurs JS capturées
}
```

**Règle** : toute valeur nécessaire dans un `Then` après un `When` **doit** être stockée dans `this.*` dans le `When`.

---

## 4. Types de tests

### 4.1 Tests de fumée (`@smoke`)

**But :** vérifier que l'application est opérationnelle en moins de 2 minutes.

**Scénarios inclus :**
- Inscription réussie (`Id01`)
- Connexion réussie (`Id02`)
- Ajout d'un todo (`Id03`)

```bash
npm run agent:runner:smoke
```

**Fréquence :** à chaque déploiement, avant la suite complète.  
**Critère de passage :** 100% des scénarios `@smoke` verts.

---

### 4.2 Tests critiques (`@critical`)

**But :** valider les chemins business absolument bloquants.

**Scénarios inclus :**
- Inscription + Connexion (Id01, Id02)

```bash
npm run agent:runner:critical
```

**Critère de passage :** 100% — tout échec bloque le déploiement.

---

### 4.3 Tests de régression (`@regression`)

**But :** détecter toute régression sur l'ensemble du périmètre.

**Scénarios inclus :** 32 scénarios dans tous les domaines.

```bash
npm run agent:runner:regression   # vs baseline sauvegardée
npm run test:allure               # exécution complète avec rapport
```

**Baseline :** `docs/baseline.json` — référence créée sur un run vert.  
**Fréquence :** à chaque Pull Request + run quotidien nocturne.

---

### 4.4 Tests négatifs (`@negative`)

**But :** vérifier que l'application rejette correctement les entrées invalides.

**Scénarios :** 16 scénarios couvrant :
- Champs obligatoires vides
- Formats invalides (email, mot de passe faible)
- Valeurs hors limites

**Stratégie d'assertion :**

```typescript
// 1. Attendre explicitement le message d'erreur (waitFor, pas isVisible)
const errorVisible = await errorLocator
  .waitFor({ state: 'visible', timeout: 8000 })
  .then(() => true).catch(() => false);

// 2. Fallback : vérifier l'absence de l'élément si pas de message
// 3. Bug applicatif connu → attach Allure sans bloquer
```

---

### 4.5 Tests de détection des tests instables (`flaky`)

**But :** identifier les tests dont le résultat est non-déterministe.

```bash
npm run agent:runner:flaky        # 3 runs par défaut
```

**Seuil flaky :** ≥ 33% d'échecs sur N runs = déclaré flaky.  
**Rapport :** `docs/flaky-report.json`

**Dernière détection (14/06/2026) :**

| Test | Flakiness | Cause identifiée |
|------|-----------|-----------------|
| Id03_TodoNegative - whitespace | 37.5% | Bug applicatif (app accepte whitespace) |
| Id05_LoginNegative - empty fields | 37.5% | waitForNavigation prématuré sur SPA React → **corrigé** |
| Id01_SignupNegative - missing email | 37.5% | waitForNavigation prématuré → **corrigé** |

---

## 5. Couverture fonctionnelle

### Matrice de couverture

| Fonctionnalité | Cas positifs | Cas négatifs | Edge cases | Couverture |
|----------------|-------------|-------------|------------|------------|
| Inscription | ✅ | ✅ 7 cas | Mot de passe faible, email invalide | Complète |
| Connexion | ✅ | ✅ 7 cas | Champs vides, mauvais mdp | Complète |
| Création todo | ✅ | ✅ 4 cas | Vide, whitespace, 250+ chars | Partielle* |
| Suppression todo | ✅ | ✅ 4 cas | Non-existant, déjà supprimé | Complète |

> \* Partielle : l'app ne valide pas whitespace ni limite de caractères (bugs connus)

### Types de couverture par domaine

| Domaine | Positif | Négatif | Auth | Limite | Sécurité | Performance |
|---------|---------|---------|------|--------|----------|-------------|
| Signup | ✅ | ✅ | — | ✅ | — | — |
| Login | ✅ | ✅ | ✅ | — | — | — |
| Todo | ✅ | ✅ | ✅ | ✅ | — | — |

---

## 6. Stratégie de données de test

### Isolation des données

Chaque scénario crée ses propres données pour garantir l'isolation :

```typescript
// Génération d'utilisateur unique à chaque run
const user = randomUser();  // email unique avec timestamp
// → { firstName, lastName, email: `qa_${Date.now()}@test.com`, password }
```

### Utilisateur créé via API (pattern inter-scénarios)

Pour les scénarios login (Id02, Id05) qui nécessitent un compte existant, l'utilisateur est créé via l'API (`QACartApiClient.register`) et scopé au `World` du scénario — aucun fichier partagé entre workers (parallel-safe) :

```typescript
const user = randomUser();
const token = await new QACartApiClient().register(user);
world.user = user;
```

### Données sensibles

- Les mots de passe de test sont dans `src/support/testData.ts` (données fictives)
- Les clés API (GROQ, Jira, GitHub) **ne sont jamais commitées** — `.env` dans `.gitignore`
- Les fixtures utilisateur sont régénérées si invalides

### Nettoyage

Les comptes créés pendant les tests ne sont pas supprimés automatiquement (l'app ne fournit ni API ni page de suppression de compte).

---

## 7. Environnements

### Configuration par environnement

| Variable | Local | Staging | Production |
|----------|-------|---------|------------|
| `BASE_URL` | `http://localhost:3000` | `https://staging.qacart-todo.com` | `https://qacart-todo.herokuapp.com` |
| `TEST_HEADLESS` | `false` | `true` | `true` |
| `AGENT_MAX_ITER` | `3` | `5` | `5` |

```bash
npm run test:local       # ENV=local
npm run test:staging     # ENV=staging
npm run test:prod        # ENV=prod (qacart-todo.herokuapp.com)
```

### Navigateurs

| Navigateur | Commande | Usage |
|------------|----------|-------|
| Chromium | `npm test` | Défaut — tous les runs |
| Firefox | `npm run test:allure:firefox` | Validation cross-browser |
| Multi-browser | `npm run test:multibrowser` | Run de validation pré-release |

### Contraintes Heroku

L'application sur Heroku peut présenter des cold starts (10-20s) après inactivité. Les timeouts d'assertion sont calibrés en conséquence :

- Navigation / goto : 30s
- Apparition d'éléments : 15s (négatifs), 10s (positifs)
- Network idle après submit : 10s

---

## 8. Critères de qualité (Quality Gate)

### Seuils de passage

| Métrique | Seuil minimum | Seuil idéal | Bloquant |
|----------|--------------|-------------|----------|
| Pass rate global | **≥ 90%** | ≥ 97% | Oui |
| Fail rate | **≤ 5%** | 0% | Oui |
| Flaky rate | **≤ 20%** | ≤ 5% | Non |
| Couverture features | **≥ 80%** | 100% | Non |
| Tests `@critical` | **100%** | 100% | Oui |
| Tests `@smoke` | **100%** | 100% | Oui |

### Vérification automatique

```bash
npm run agent:advisor:gate        # Score qualité 0–100 via LLM
npm run agent:advisor:advise      # Vote GO / NO-GO (3 LLMs)
npm run agent:reporting:dashboard # Dashboard KPI HTML
```

### Décision de déploiement (GO / NO-GO)

```
┌─────────────────────────────────────────────┐
│  @smoke 100% ET @critical 100%              │
│         ET pass_rate ≥ 90%                  │
│         ET fail_rate ≤ 5%                   │
│                  ↓                          │
│             → GO 🟢                         │
│                                             │
│  Sinon        → NO-GO 🔴                   │
└─────────────────────────────────────────────┘
```

---

## 9. Gestion des risques

### Risques techniques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Cold start Heroku | Élevée | Moyen | Timeouts étendus à 15-30s, `waitForLoadState('networkidle')` |
| Test flaky sur SPA React | Élevée | Moyen | `waitFor` au lieu de `isVisible`, networkidle après submit |
| LLM Groq indisponible | Faible | Moyen | Circuit breaker OPEN → cache SHA256 servi (TTL 1h) |
| Clé API expirée | Faible | Élevé | Alertes via `agent:observability:cb` |
| Données de fixture corrompues | Faible | Moyen | Régénération automatique si `loadUser()` retourne null |

### Risques applicatifs (bugs connus)

| Comportement | Sévérité | Statut |
|-------------|----------|--------|
| Todo whitespace-only accepté | Moyenne | **BUG CONNU** — warning Allure |
| Todo > 250 caractères accepté | Moyenne | **BUG CONNU** — warning Allure |
| `waitForNavigation` SPA React | Élevée | **CORRIGÉ** → `waitForLoadState('networkidle')` |

### Stratégie de retry

```bash
npm run test:allure:retry   # --retry 1 sur les tests flakey
```

Le retry est limité à **1 tentative** pour éviter les faux positifs. Un test qui passe en retry est marqué dans Allure.

---

## 10. Bugs connus et limitations applicatives

### Bug #1 — Absence de validation whitespace dans les todos

**Description :** L'application accepte la création de todos contenant uniquement des espaces.  
**Scénario :** `Id03_TodoNegative - adding todo with only whitespace should fail`  
**Comportement attendu :** message d'erreur ou rejet côté serveur.  
**Comportement actuel :** le todo est créé avec un contenu vide visible.  
**Impact test :** warning Allure attaché, test passe sans bloquer le pipeline.  
**Priorité fix :** Moyenne — UX dégradée mais non critique.

### Bug #2 — Absence de limite de caractères dans les todos

**Description :** L'application accepte des todos de plus de 250 caractères.  
**Scénario :** `Id03_TodoNegative - adding todo exceeding character limit should fail`  
**Comportement attendu :** rejet avec message "limite de caractères dépassée".  
**Comportement actuel :** le todo long est créé sans erreur.  
**Impact test :** warning Allure attaché, test passe sans bloquer le pipeline.  
**Priorité fix :** Faible — cas limite peu impactant.

### Limitation — Pas d'API de cleanup

L'application ne fournit pas d'endpoint d'administration pour supprimer les comptes de test en masse. Chaque run de test crée un nouvel utilisateur avec un email unique.

---

## 11. Pipeline CI/CD

### Flux de pipeline

```
Pull Request créée
       │
       ▼
  [Smoke tests]      @smoke — 3 scénarios — < 2 min
       │ ✅
       ▼
  [Critical tests]   @critical — 2 scénarios — < 1 min
       │ ✅
       ▼
  [Full regression]  32 scénarios — ~5 min
       │
       ▼
  [Quality Gate]     pass_rate ≥ 90% / fail_rate ≤ 5%
       │
       ├── ✅ GO     → merge autorisé
       └── ❌ NO-GO  → PR bloquée, notification Slack
```

### Commandes pipeline

```bash
# Pipeline rapide (post-merge)
npm run agent:pipeline:quick

# Pipeline complet (pre-release)
npm run agent:pipeline:full

# Statut CI GitHub Actions
npm run agent:ci:status
```

### Notifications

- **Slack :** `npm run agent:reporting:notify` — bloc KPI + verdict GO/NO-GO
- **Jira :** `npm run agent:reporting:sync` — commentaires sur les tickets liés aux échecs
- **GitHub PR :** description auto-générée par `ci-agent` avec résumé des résultats

---

## 12. Métriques et reporting

### Métriques collectées

| Métrique | Source | Outil |
|----------|--------|-------|
| Pass/Fail/Broken par run | `allure-results/` | `agent:reporting:dashboard` |
| Durée par scénario | Allure | Dashboard HTML |
| Taux de flakiness par TC | `docs/flaky-report.json` | `agent:runner:flaky` |
| Coût LLM par agent | `logs/traces.jsonl` | `agent:observability:cost` |
| Confiance RCA | `logs/traces.jsonl` | `agent:observability:metrics` |
| Historique trend | `memory/episodes.jsonl` | `agent:advisor:history` |

### Dashboards

```bash
npm run agent:reporting:dashboard   # docs/kpi-dashboard.html
npm run agent:observability:report  # docs/observability-report.html
npm run agent:pipeline:report       # docs/pipeline-dashboard.html
npm run agent:bug:report            # docs/bug-report.html
npm run dashboard:browser           # Dashboard Allure browser
```

### Rapport Allure

```bash
npm run test:allure           # Génère allure-results/
npm run allure:generate       # Compile allure-report/
npm run allure:open           # Ouvre dans le navigateur
```

---

## 13. Stratégie par agent IA

### Quand utiliser quel agent

| Situation | Agent recommandé | Commande |
|-----------|-----------------|----------|
| Nouvelle US Jira → générer les tests | codegen | `agent:codegen:spec` |
| Exécuter les tests | runner | `agent:runner` |
| Des tests échouent → comprendre pourquoi | quality | `agent:quality:triage` |
| Analyser la cause racine en profondeur | quality | `agent:quality:rca` |
| Corriger automatiquement les tests | bug | `agent:bug:repair` |
| Décider si on peut déployer | advisor | `agent:advisor:advise` |
| Voir le coût LLM et les métriques | observability | `agent:observability:cost` |
| Créer une PR avec description auto | ci | `agent:ci:pr` |
| Voir l'état du pipeline GitHub | ci | `agent:ci:status` |
| Tableau de bord pour le client | reporting | `agent:reporting:dashboard` |
| Tout faire en une commande | pipeline | `agent:pipeline:full` |

### Coût LLM par situation

| Situation | Pipeline | Coût estimé |
|-----------|---------|------------|
| Vérification rapide post-merge | `pipeline:quick` | ~$0.009 |
| Analyse complète des échecs | `pipeline:report` | ~$0.015 |
| Cycle complet génération → déploiement | `pipeline:full` | ~$0.025 |
| Toute la journée de travail (10 runs) | — | ~$0.25 |

---

## 14. Conventions et bonnes pratiques

### Nommage des scénarios

```gherkin
Scenario: <ID>_<Domaine> - <action> should <résultat>
# Exemple :
Scenario: Id01_SignupNegative - signup with missing email should fail
```

### Tags obligatoires

Tout scénario doit avoir **au minimum** :
- Un tag de domaine : `@signup` `@login` `@todo`
- Un tag d'ID : `@Id01` … `@Id05`, `@api-setup` pour Id09
- Un tag de type : `@smoke` ou `@regression` ou `@negative`
- `@ui` pour tous les tests E2E

### Règles de step definitions

1. **Un seul niveau d'abstraction par step** — le step appelle une méthode Page, pas de logique directe
2. **`this.lastTodo`** doit être assigné dans le `When` si le `Then` en a besoin
3. **Jamais de `isVisible()` sans attente** — toujours `waitFor({ state: 'visible', timeout })` ou `expect().toBeVisible({ timeout })`
4. **Bug applicatif** → `this.attach(message, 'text/plain')` puis `return` — ne pas `throw`

### Règles de Page Objects

1. **Tous les sélecteurs dans le constructeur** avec `.or()` pour la résilience
2. **Après un clic de submit** : `waitForLoadState('networkidle')` — jamais `waitForNavigation` seul sur SPA
3. **Timeouts** : 15s pour assertions sur négatifs, 10s pour positifs, 30s pour navigation

### Gestion des assertions

```typescript
// ✅ Correct — attend vraiment
await expect(locator).toBeVisible({ timeout: 15000 });
await locator.waitFor({ state: 'visible', timeout: 8000 });

// ❌ Incorrect — check instantané, ignore le timeout
await locator.isVisible({ timeout: 3000 });  // timeout ignoré !
```

### Revue de test

Avant chaque merge, vérifier :
- [ ] `npm run agent:runner:smoke` → 100% vert
- [ ] `npm run agent:quality:triage` → aucun new failure
- [ ] `npm run agent:advisor:gate` → score ≥ 80
- [ ] Aucun test flaky non documenté

---

*Document maintenu par l'équipe QA — mis à jour à chaque évolution du framework.*  
*Généré le 14 juin 2026.*
