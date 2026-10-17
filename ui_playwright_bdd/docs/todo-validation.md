# Validation des tâches : règle cible

Règle proposée le 20 septembre 2026 à la demande de l'utilisateur :
une tâche contient **1 à 200 caractères après suppression des espaces en début et fin**.
Une chaîne vide, uniquement composée d'espaces ou dépassant 200 caractères doit
être rejetée, sans insertion, avec un message de validation compréhensible.
L'interface et l'API doivent appliquer la même règle ; l'API doit notamment rejeter
les requêtes invalides même si elles contournent le formulaire.

Cette règle est une exigence cible, pas une limite constatée de l'application QACart.
Le test de dépassement utilise désormais 201 caractères (anciennement 250).
Les critères d'acceptation aux limites sont 1 et 200 acceptés ; 0 après trim et
201 rejetés. Les tests ne corrigent pas les données envoyées pour masquer un défaut.

## Constats sur l'exécution existante

Run `1789856064726-7016ad5a-ec8b-44ef-be9e-29039f76f6c6` :
29 scénarios terminés, 27 réussis et 2 en échec.

- Espaces seuls : après soumission et rechargement, la liste passe de 0 à 1 tâche.
  L'assertion de non-insertion détecte une divergence avec le scénario attendu.
- Longueur : aucune erreur de longueur visible après l'envoi de 250 caractères.
  Cette ancienne exécution ne constitue pas un test de la nouvelle limite de 201.

Les preuves (erreurs, capture et HTML) sont dans le rapport Allure de ce run.
Le code applicatif QACart n'est pas présent dans ce dépôt d'automatisation :
le rejet des entrées doit être implémenté dans l'application/API pour lever ces
blocages. Ne pas supprimer les assertions ni convertir ces échecs en succès.

Les correctifs des agents Quality/Bug portent sur l'analyse et sa fiabilité ;
ils ne corrigent pas à eux seuls ces comportements applicatifs.
