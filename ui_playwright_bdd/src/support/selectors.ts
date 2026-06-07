import { Page, Locator } from 'playwright';

export function byTestIdOr(page: Page, testId: string, fallback: () => Locator): Locator {
  // getByTestId utilise data-testid par défaut :contentReference[oaicite:1]{index=1}
  const testIdLocator = page.getByTestId(testId);
  // On ne peut pas "try/catch" sur Locator directement, donc on retourne le locator
  // et on gère l'attente au moment de l'action via helper "safeFill/safeClick" dans BasePage.
  return testIdLocator.or(fallback());
}