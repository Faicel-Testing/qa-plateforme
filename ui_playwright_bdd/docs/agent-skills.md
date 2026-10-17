# Procédures des agents

Les agents JavaScript chargent les procédures de `skills/<nom>/SKILL.md` avec `scripts/agents/shared/skill-store.js`. Ce mécanisme appartient au framework ; il n'installe pas automatiquement ces skills dans Codex.

| Skill | Appelant |
|---|---|
| analyse-echec | Bug analyze, via llm-analysis.js |
| proposition-correction | Bug repair |
| triage-rca | Quality triage et RCA |
| audit-sources | Quality verify, via source-verification.js |
| generation-gherkin | Codegen spec et gherkin |
| generation-steps | Codegen steps |
| generation-pages | Codegen pages |
| recommandation-release | Advisor advise, predict et gate |

Le nom est choisi explicitement par le code dans une liste autorisée. Aucun chemin proposé par le LLM, téléchargement ou outil défini par un skill n'est exécuté. Le chargeur vérifie le chemin réel, le format du frontmatter, le nom et la taille du fichier. Un fichier obligatoire absent ou invalide provoque une erreur, sans procédure de secours silencieuse.

Les instructions incluent une empreinte SHA-256 : la version utilisée apparaît dans le prompt et sa modification change la clé du cache fondé sur le prompt. Les fichiers sont relus lors de la construction des instructions. Le chargement du skill d'analyse est comptabilisé dans son budget de contexte ; les lots d'audit incluent aussi la procédure dans leur budget.

Les procédures d'audit des sources et de génération Steps/Page Objects ont été extraites du JavaScript. Les prompts versionnés existants restent conservés : ils portent encore les consignes propres aux tâches et les formats, auxquels les autres skills ajoutent une procédure commune. Il ne s'agit pas d'une suppression complète du prompt store.

Les schémas de sortie, validations, permissions d'outils, budgets, contrôles du gateway et approbations restent dans le code. Modifier un skill ne donne aucune permission supplémentaire. Les skills transitent par le client LLM et le gateway comme les autres instructions.

Pour modifier une procédure, éditer son SKILL.md et effectuer une revue de code. Le chargeur prend en charge un frontmatter simple, avec les lignes `name` et `description`, suivi du corps Markdown. Ne pas ajouter d'instructions contradictoires aux contrats d'action ou aux seuils imposés par le code.

Vérification locale sans fournisseur :

```powershell
node --test scripts/agents/tests/skill-store.test.js scripts/agents/tests/agent-reliability.test.js scripts/agents/tests/analysis-evidence.test.js scripts/agents/tests/source-verification.test.js
```

Ces tests vérifient le chargement, le contexte réellement transmis aux appels simulés et les contrôles existants. Ils ne mesurent pas une amélioration des réponses d'un modèle réel ; une évaluation DeepEval distincte est nécessaire pour comparer cette qualité.
