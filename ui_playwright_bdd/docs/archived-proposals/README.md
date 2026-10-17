# Propositions archivées

`applicatio-4.feature.txt` conserve à l'identique l'ancien fichier généré
`src/features/applicatio-4.feature`. Son extension et son emplacement l'excluent
de la découverte Cucumber. Il ne doit pas être utilisé comme référence de test.

Consolidation autorisée le 13 octobre 2026 : ses sept cas (un positif et six lignes
d'exemples négatifs) sont déjà couverts par les huit scénarios des features
`Id02_LoginTest.feature` et `Id05_LoginNegativeTest.feature`. Aucun cas supplémentaire
n'a été identifié. Les sources de référence utilisent les fixtures et assertions
existantes ; elles portent désormais le tag `@applicatio-4`.

La proposition IA `f35b0933-7cc8-4a29-af6d-2f018264b7f2` n'a pas été appliquée :
elle reproduit également ces huit scénarios. Après modification des tags, son
empreinte de contexte est périmée et la revue existante doit en refuser l'application.
