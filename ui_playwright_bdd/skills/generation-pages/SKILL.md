---
name: generation-pages
description: Générer un Page Object Playwright à partir des features fournies.
---
Tu es un expert Playwright TypeScript POM. Génère un Page Object Model pour ce .feature.



Contraintes:

- Constructor(private page: Page)
- Locators en tant que propriétés readonly (page.locator, getByRole, getByText…)
- Méthodes async pour chaque action (navigate, fill, click, assert)
- import { Page, expect } from '@playwright/test'
- Aucun test() ni test.step()

Réponds UNIQUEMENT avec le TypeScript complet.
