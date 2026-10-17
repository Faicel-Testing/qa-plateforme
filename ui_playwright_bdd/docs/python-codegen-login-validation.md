# Validation réelle de codegen — APPLICATIO-4

Date : 13 octobre 2026. Story Plane : APPLICATIO-4, connexion utilisateur.

## Résultat

- Lecture réelle de la story via le bridge Python/Node : réussie.
- Génération via LangChain/LangGraph et la passerelle IA configurée : réussie.
- Contrat Pydantic et parsing Gherkin : acceptés.
- Cucumber sans exécution : 8 scénarios, 25 étapes, aucune étape manquante ou ambiguë.
- Exécution navigateur sur une copie isolée : 8 scénarios réussis, 25 étapes réussies,
  41 résultats PASSED en comptant les hooks ; aucun retry.
- Suite Python après modification de la sélection du contexte : 54 tests réussis.
- Aucune proposition appliquée aux sources et aucune publication Plane/CI.

## Proposition et preuves locales

Identifiant : `f35b0933-7cc8-4a29-af6d-2f018264b7f2`.

Empreinte SHA-256 du contenu :
`f3bdb7a803dfaa68627b6f18c37fba377c4b0e13cc7d81305fd3ef376ec7d045`.

Les fichiers suivants sont locaux, sous `logs/`, et ne doivent pas être committés :

- `logs/change-proposals/f35b0933-7cc8-4a29-af6d-2f018264b7f2.json`
- `logs/proposal-validation/f35b0933-7cc8-4a29-af6d-2f018264b7f2/candidate.feature`
- `logs/proposal-validation/f35b0933-7cc8-4a29-af6d-2f018264b7f2/dry-run.json`
- `logs/proposal-validation/f35b0933-7cc8-4a29-af6d-2f018264b7f2/browser.json`

## Correction issue de l'essai

La génération sans sources signalait des prérequis manquants. L'envoi de tous les
steps/POM a ensuite échoué au niveau du service IA, alors qu'une requête minimale
fonctionnait. La cause exacte côté fournisseur n'a pas été établie.

Le contexte Gherkin est désormais limité aux features référencées par la story,
aux steps de même nom et à leurs imports relatifs vers les POM, transitivement.
La génération avec ce contexte réduit a réussi. La transmission de ces sources
au fournisseur a été explicitement autorisée par l'utilisateur.

## Revue et limites

Les scénarios reprennent les huit cas déjà présents dans `Id02_LoginTest.feature`
et `Id05_LoginNegativeTest.feature`, avec les steps et fixtures existants. Le résultat
ne constitue donc pas une nouvelle couverture. Ajouter cette proposition telle quelle
dupliquerait les tests Login ; une consolidation est nécessaire avant intégration.

La story indique que ses critères proviennent des tests et restent à valider métier.
Cet essai démontre le fonctionnement de la génération et de ces scénarios à cet instant,
pas l'acceptation métier, la réussite de la suite complète ou une autorisation de release.
Le rapport navigateur est propre à cet essai ; il ne constitue pas un manifeste du
pipeline Python et ne doit pas être présenté comme tel à `quality` ou `advisor`.
