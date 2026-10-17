# Vérification des sorties des huit agents IA

Le module `scripts/agents/shared/agent-verifier.js` est appelé par codegen,
quality, bug, advisor, planning, reporting, ci et les fonctions IA du runner.
Il ne lance aucun appel LLM supplémentaire.

## Verdicts et preuves

- `VALIDATED` : les critères du périmètre annoncé sont démontrés. Actuellement,
  ce statut concerne les résumés déterministes égaux aux comptages fournis.
  Il ne garantit ni la couverture des tests ni la fraîcheur de données externes.
- `REJECTED` : réponse inutilisable, schéma invalide ou contradiction contrôlable.
- `UNVERIFIED` : contrôles de structure réussis, mais exactitude métier non démontrée.
  Une confiance élevée, plusieurs votes ou une relecture par un modèle ne suffisent pas.

Les journaux JSONL contiennent l'agent, l'opération, le run, l'invocation,
les empreintes du résultat et du contexte, les contrôles et leurs limites.
Ils ne recopient pas les prompts ou les réponses dans le journal de vérification.
Les logs existants des agents conservent leur fonctionnement antérieur.

Exécution directe : `logs/agent-verification/<agent>-<invocation>.jsonl`.
Pipeline : fichier `*.verification.jsonl` dans le dossier de logs de l'exécution,
avec verdict repris dans le résumé du pipeline. Un dry-run n'écrit pas ce journal.

## Comportement par agent

| Agent | Contrôle et effet |
|---|---|
| codegen | Parse réellement Gherkin/TypeScript et compile le projet avec le candidat TypeScript en mémoire, avant écriture. Rejette les erreurs. Un candidat compilable reste `UNVERIFIED` sur le plan métier. |
| planning | Parse les scénarios suggérés ; les affiche comme propositions non vérifiées. |
| quality | Vérifie les schémas de triage/RCA et les bornes de confiance. Attache le verdict aux analyses. Les vérifications existantes des sources et d'Allure restent actives. |
| bug | Vérifie la structure d'analyse. Une cause reste une hypothèse. Une modification appliquée n'est plus annoncée comme réparation réussie : sans preuve avant/après et régression, `repair` termine en échec. |
| advisor | Contrôle schémas et cohérence avec l'exécution. Les avis restent consultatifs ; un avis LLM non vérifié n'autorise plus automatiquement une release, même après vote. |
| reporting | Vérifie le texte IA puis utilise un résumé chiffré déterministe pour la notification externe. |
| ci | Contrôle descriptions PR, notes de release et messages de commit. Affiche les brouillons, mais bloque leur publication/commit automatique tant que le contenu demeure non vérifié. Les autres commandes Git/CI sont inchangées. |
| runner | Vérifie les résumés IA et les explications de flakiness ; les marque comme hypothèses. Les contrôles déterministes d'exécution ne sont pas dupliqués. |

Le pipeline peut poursuivre l'exécution de tests et la collecte de diagnostics
sur des candidats non vérifiés. Il bloque la décision automatique de release
lorsqu'une sortie IA précédente est rejetée ou non vérifiée. Un processus qui
retourne zéro n'efface pas un rejet enregistré dans le journal.

## Limites opérationnelles

Ce changement ne crée pas un démonstrateur de vérité métier. Les parcours CI et
advisor concernés sont désormais conservateurs : leur texte libre ne peut pas
atteindre `VALIDATED` avec les seules preuves actuellement fournies. Il faut
relire les brouillons et utiliser le processus normal de revue/publication ;
aucune option ne transforme arbitrairement un avis IA en vérité vérifiée.

Les correctifs de `bug repair` peuvent toujours modifier les sources. Le verdict
non vérifié ne les annule pas : examiner le diff, exécuter les tests ciblés et
la régression avant de conserver un correctif. La génération ne garantit pas
la conformité aux exigences ni l'exécution UI. Sans tsconfig disponible,
la compilation du candidat reste explicitement non vérifiée.

## Tests locaux

Depuis `ui_playwright_bdd` :

```powershell
node --test scripts/agents/tests/*.test.js
```

Les tests utilisent des réponses simulées et des dossiers temporaires ; aucun
appel fournisseur, aucune notification et aucune publication GitHub ne sont requis.
