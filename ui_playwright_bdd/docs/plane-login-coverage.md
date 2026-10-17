# Couverture consolidée — APPLICATIO-4

Story : [APPLICATIO-4 — Login](https://app.plane.so/ai-qa-automation/projects/a1cd9e82-915a-4dc9-9fd9-69441c41ebdb/issues/28961fe5-14e3-4167-91ee-5ecef1086850).
Ancienne référence : SCRUM-6. Liaison locale via le tag `@applicatio-4` ; aucune
modification du backlog Plane n'est effectuée par cette consolidation.

| Cas | Feature de référence |
| --- | --- |
| Connexion avec un utilisateur créé par fixture | `Id02_LoginTest.feature` |
| Identifiants invalides | `Id05_LoginNegativeTest.feature` |
| Format email invalide | `Id05_LoginNegativeTest.feature` |
| Mot de passe incorrect | `Id05_LoginNegativeTest.feature` |
| Utilisateur inexistant | `Id05_LoginNegativeTest.feature` |
| Email vide | `Id05_LoginNegativeTest.feature` |
| Mot de passe vide | `Id05_LoginNegativeTest.feature` |
| Email et mot de passe vides | `Id05_LoginNegativeTest.feature` |

Les étapes, assertions et tags smoke/critical/regression existants sont conservés.
L'ancien fichier généré est archivé sous `docs/archived-proposals/` et ne participe
plus à la suite. La proposition IA n'apporte pas de couverture supplémentaire.

Sélection Cucumber : `--tags @applicatio-4` (huit scénarios attendus).
Les critères de la story restent à valider métier ; la traçabilité et la réussite
des tests ne constituent pas une acceptation métier ou une autorisation de release.

## Validation du 13 octobre 2026

- Découverte depuis `src/features/**/*.feature`, filtrée par `@applicatio-4` :
  exactement les deux features de référence, huit scénarios et 25 étapes.
- Contrôle Cucumber sans navigateur : réussi, aucune étape manquante ou ambiguë.
- Exécution Chromium headless, sans retry : huit scénarios et 25 étapes réussis,
  41 statuts PASSED avec les hooks.
- Rapports locaux : `logs/login-consolidation-20261013/dry-run.json` et
  `logs/login-consolidation-20261013/browser.json` (ne pas committer).
- Seul le périmètre Login a été exécuté ; aucune publication Plane ou validation
  de la suite complète n'est impliquée.
