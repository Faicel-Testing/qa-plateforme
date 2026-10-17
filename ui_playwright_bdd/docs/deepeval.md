# Évaluation DeepEval

DeepEval 4.2.6 évalue les réponses IA dans un environnement Python isolé. Le module est lancé à la demande, séparément des tests Playwright/Cucumber et des vérificateurs d'agents. Il ne s'exécute pas automatiquement après chaque réponse. RAGAS n'est pas installé par cette intégration.

```text
Questions de référence → recherche BM25 → contexte exact → réponse du LLM
                                        ↓                  ↓
                         samples.json → DeepEval → juge LLM via Node
                                           ↓              ↓
                                  rapports HTML/JSON   tokens/coûts/durée
```

## Configuration actuelle : Groq uniquement

Depuis le 16 octobre 2026, les agents et le juge utilisent exclusivement Groq.
La recherche utilise BM25 (`RAG_MODE=bm25`), avec reranking Groq selon la
configuration. Aucun service d’embeddings local n’est requis. Le mode CLI
`--mode hybrid` n’est plus accepté. Les anciens rapports sont conservés comme
historique ; ils peuvent mentionner d’anciens fournisseurs.

```powershell
npm.cmd run eval:deepeval -- --limit 1
```

Une clé `GROQ_API_KEY` est nécessaire pour les appels IA. Une absence de clé ou
un échec du fournisseur donne une erreur explicite, sans secours vers un autre
fournisseur. Les tests Playwright restent indépendants de cette disponibilité.

## Commandes

Prérequis : Node, dépendances npm, Python 3.10+, environnement
`.venv-deepeval` et clé Groq configurée.

```powershell
npm.cmd run eval:setup
npm.cmd run eval:deepeval:check
npm.cmd run eval:deepeval -- --limit 1
npm.cmd run metrics:report
```

Réévaluer un ancien fichier dont les cas sont `ERROR` ne relance pas leur collecte.
Lancer une nouvelle évaluation sans `--input` pour produire un nouvel échantillon.
Les rapports sont écrits dans `logs/deepeval/<identifiant>/report.html` et `report.json`.

## Métriques et paramètres

Par défaut : 2 cas, top-k 4, recherche BM25 stricte, seuil 0,7 et deux métriques :

| Métrique | Question évaluée |
| --- | --- |
| `faithfulness` | Les affirmations sont-elles soutenues par le contexte fourni ? |
| `answer_relevancy` | La réponse répond-elle à la question ? |
| `contextual_precision` | Les extraits utiles sont-ils bien classés ? Nécessite une réponse attendue. |
| `contextual_recall` | Le contexte couvre-t-il les informations attendues ? Nécessite une réponse attendue. |

```powershell
npm run eval:deepeval -- --limit 4 --top-k 4 --threshold 0.7 --metrics faithfulness,answer_relevancy,contextual_precision,contextual_recall
npm run eval:deepeval -- --limit 2 --mode bm25
```

La limite `DEEPEVAL_MAX_JUDGE_CALLS` vaut 30 par défaut. Une évaluation avec davantage de cas/métriques peut nécessiter une augmentation explicite. Atteindre cette limite produit une erreur, jamais une réussite. Les appels au juge sont séquentiels, avec délai limite et sans retries SDK ; un cas nécessite plusieurs appels.

Pour les comptes soumis à une limite de débit, définir `$env:DEEPEVAL_JUDGE_INTERVAL_SECONDS = '25'` espace les débuts d'appels du juge (0 par défaut, maximum 60 secondes). Une erreur HTTP 429 reste une erreur technique, pas un mauvais score de l'agent. Les juges Groq `openai/gpt-oss-120b` et `openai/gpt-oss-20b` utilisent le JSON Schema DeepEval en mode `strict: false`, afin de conserver ses champs facultatifs ; la réponse est ensuite validée par Pydantic. Les autres modèles conservent le mode JSON précédent. Voir les [sorties structurées Groq](https://console.groq.com/docs/structured-outputs).

Codes de sortie : `0` = métriques réussies, `1` = au moins un score sous le seuil, `2` = erreur technique ou données invalides. Une erreur de recherche/génération ou de juge n'est pas transformée en score valide.

## Évaluer une sortie d'agent existante

Le collecteur fourni exerce le RAG partagé sur des questions QA. Il ne lance pas les 13 agents et ne prétend pas couvrir leurs résultats automatiquement. Pour évaluer une réponse existante, fournir son contexte réellement utilisé :

```json
{
  "datasetReviewStatus": "DRAFT",
  "cases": [{
    "id": "agent-exemple-1",
    "input": "Question posée à l'agent",
    "actual_output": "Réponse réellement produite",
    "expected_output": "Réponse de référence revue par un humain",
    "retrieval_context": ["Extrait réellement transmis à l'agent"]
  }]
}
```

```powershell
npm run eval:deepeval -- --input chemin/samples.json --limit 1
```

Cette commande évalue les sorties fournies sans régénération ni nouvelle recherche. Le juge reçoit toujours les données nécessaires aux métriques.

## Configuration et limites

### Capturer les échanges d'un agent

Le préchargement optionnel `scripts/capture-agent-eval.js` enregistre les messages exacts après augmentation RAG et les réponses effectivement retournées par le circuit breaker Groq, y compris les réponses du cache. Il exclut les réponses de secours. Aucun autre fournisseur n’est appelé.

```powershell
$env:NODE_OPTIONS = '--require=./scripts/capture-agent-eval.js'
node scripts/measure-task.js scripts/agents/quality-agent.js rca
Remove-Item Env:NODE_OPTIONS
# Utiliser le chemin samples.json affiché par [DeepEval capture] :
npm run eval:deepeval -- --input logs/deepeval/capture-IDENTIFIANT/samples.json --limit 2
```

Ne garder ce préchargement actif que pendant la capture choisie. Les fichiers contiennent le contenu réel des échanges et restent sous `logs/`, ignoré par Git. Aucun en-tête d'authentification n'est capturé. Une capture évalue chaque réponse LLM utilisée par l'agent, pas automatiquement sa décision finale agrégée. Son contexte comprend les consignes et les preuves fournies ; les réponses antérieures de l'assistant sont conservées dans `messages` pour audit mais exclues des preuves de fidélité, car elles ne constituent pas une source indépendante. Les scores doivent donc être interprétés en tenant compte de ce périmètre.

Sur cette machine Windows, le juge nécessite les autorités de confiance Windows pour vérifier la chaîne TLS de Groq. Un export local des certificats publics est disponible dans `logs/deepeval/windows-ca.pem` (ignoré par Git). Dans une nouvelle session PowerShell, avant une évaluation :

```powershell
$env:NODE_EXTRA_CA_CERTS = Join-Path (Get-Location) 'logs/deepeval/windows-ca.pem'
$env:NODE_TLS_REJECT_UNAUTHORIZED = '1'
```

Ce chemin est propre à cette installation ; sur une autre machine, utiliser le bundle CA approuvé par votre organisation si nécessaire. Le [gateway commun](ai-gateway.md) contrôle désormais les appels du juge, de génération et d'embeddings ; il refuse le TLS désactivé. Les anciens bypass TLS des agents ont été retirés.

`DEEPEVAL_JUDGE_PROVIDER=groq` et `DEEPEVAL_JUDGE_MODEL` permettent de choisir le juge. Groq est le seul fournisseur accepté. Le juge n'a pas de fallback fournisseur. Le générateur conserve le comportement du helper LLM existant : `generatorConfiguration` décrit sa configuration, tandis que les événements de métriques identifient les fournisseurs effectivement appelés.

Les rapports restent locaux, la télémétrie DeepEval est désactivée et aucune publication Confident AI n'est déclenchée. Avec Groq, les questions, contextes et réponses nécessaires sont envoyés à l'API Groq. Les rapports et échantillons contiennent du contenu du projet et sont ignorés par Git.

Le dataset de quatre cas est **DRAFT** : réponses attendues et seuil doivent être revus avec les experts métier. Les scores d'un juge LLM sont faillibles ; employer le même modèle pour générer et juger peut introduire un biais. DeepEval complète les assertions Playwright, les contrôles déterministes et la revue humaine ; il n'autorise aucune release.

Références : [métriques DeepEval](https://deepeval.com/docs/metrics-introduction), [modèles personnalisés](https://deepeval.com/guides/guides-using-custom-llms), [confidentialité](https://deepeval.com/docs/data-privacy).
