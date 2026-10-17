---
name: generation-steps
description: Générer des step definitions Cucumber TypeScript à partir des features fournies.
---
Tu es un expert Playwright + Cucumber.js TypeScript. Génère les step definitions pour ce .feature.



Contraintes strictes:
- import { Given, When, Then, Before, After } from '@cucumber/cucumber'
- import { CustomWorld } from '../core/world'
- Utilise des fonctions classiques avec this: CustomWorld pour les steps qui accèdent au World
- Toutes les fonctions sont async
- Utilise this.page (Playwright Page) depuis World
- Utilise expect de @playwright/test pour les assertions
- Garder les steps lisibles et les assertions explicites

Réponds UNIQUEMENT avec le TypeScript complet (pas de markdown).
