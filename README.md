# QA Platform — Unified Quality Engineering

> **Architecture QA industrialisable** · UI · API · Mobile · CI/CD · Agents IA  
> Faicel Ghanem — QA Automation Architect · Freelance

---

## Pourquoi cette plateforme

Dans la majorité des projets, la qualité est fragmentée (UI d'un côté, API ailleurs), tardive (tests à la fin) et peu décisionnelle (rapports sans impact réel).

**QA Platform** apporte une réponse claire : une plateforme unique, automatisée, qui aide à décider si un produit peut être livré sans risque.

---

## Valeur apportée au client

- Réduction des incidents en production
- Accélération des mises en production
- Décisions **Go / No-Go** basées sur des tests objectifs
- Standardisation QA multi-équipes
- Intégration native dans le CI/CD existant

---

## Architecture globale

```
CI/CD Pipeline (GitHub Actions)
        │
        ├── UI Automation   →  Playwright BDD (TypeScript)  ·  Selenium BDD (Java)  ·  Cypress BDD (JavaScript)
        ├── API Tests        →  pytest-bdd (Python)  ·  RestAssured BDD (Java)
        └── Mobile Tests     →  Appium + TestNG (Java) — hors CI continue, exécution manuelle
                │
                ▼
        Quality Gates — Go / No-Go
        Smoke · Critical · Regression
```

---

## Frameworks

| Framework | Stack | Tests | Agents IA | Rapport |
|---|---|---|---|---|
| [ui_playwright_bdd](ui_playwright_bdd/) | Playwright · CucumberJS · TypeScript | 29 BDD | 10 agents | [Allure live](https://faicel-testing.github.io/qa-plateforme/ui_playwright_bdd/) |
| [api-pytest-framework](api-pytest-framework/) | pytest-bdd · Requests · Python | 51 BDD | 10 agents | [Allure live](https://faicel-testing.github.io/qa-plateforme/api-pytest-framework/) |
| [api-Java-Rest-Assured](api-Java-Rest-Assured/) | RestAssured · Cucumber · Java | 51 BDD | 10 agents | — |
| [ui_selenium_bdd](ui_selenium_bdd/) | Selenium · Cucumber · Java | 34 BDD | 10 agents | — |
| [ui_cypress_bdd](ui_cypress_bdd/) | Cypress · CucumberJS · JavaScript | 29 BDD | 10 agents | — |
| [mobile](mobile/) | Appium · TestNG · Java | 6 E2E | 11 agents | CI désactivée (manuel) |

---

## Quality Gates

| Gate | Déclencheur | Critère |
|---|---|---|
| **Smoke** | Pull Request | Parcours critiques — échec = No-Go immédiat |
| **Regression** | Merge vers main | Couverture fonctionnelle étendue |
| **Nightly** | Planifié 02h00 | Suite complète + analyse IA |

---

## CI/CD

```
Pull Request  →  Smoke Tests (bloquant)
Merge         →  Regression Suite
Nightly       →  Full Suite + Quality Gate
Manuel        →  Par tag ou périmètre ciblé
```

---

## Secteurs couverts

**E-commerce** · **Transport** · **Énergie** · **Secteur public** · **Tech / SaaS**  
Même architecture, périmètres adaptés au domaine métier.

---

## Auteur

**Faicel Ghanem** — QA Automation Architect · Freelance  
Spécialités : Architecture QA · UI / API / Mobile Automation · CI/CD · Quality Gates · Agents IA

📧 [faicel.ganem@gmail.com](mailto:faicel.ganem@gmail.com) · 💼 [LinkedIn](https://www.linkedin.com/in/ghanem-faicel-b40787a8/) · 🔗 [Malt](https://www.malt.fr/profile/faicelghanem)

> Ce dépôt est une vitrine d'architecture QA.  
> Les implémentations client réelles sont maintenues dans des repositories privés.
