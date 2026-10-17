# Coût et temps par tâche

Une tâche correspond à une invocation de processus (par exemple `quality-agent verify`
ou `rag search`). Les commandes npm des agents et `rag:index/search/status` passent
par `scripts/measure-task.js`. Le runtime du pipeline mesure aussi chaque sous-processus.
L'interface publique de `llm.js` reste inchangée ; ses clients utilisent un transport instrumenté.

```powershell
npm run agent:quality -- verify --local-only
npm run rag:search -- "Comment supprimer une tâche ?" --strict
npm run metrics:report
```

Pour une commande Node lancée directement, utiliser :

```powershell
npm run metrics:run -- scripts/agents/runner-agent.js smoke
```

Le rapport interactif local est `logs/metrics/report.html`, son équivalent JSON
`logs/metrics/report.json`, et le journal append-only `logs/metrics/events.jsonl`.
Ces fichiers sont ignorés par Git. Le rapport est généré à la demande, sans appel IA.
`observability-agent cost` utilise désormais ces données et abandonne caractères/4.

## Mesures et périmètre

- Durée de tâche : temps écoulé du lancement jusqu'à la fermeture du processus,
  mesuré avec une horloge monotone ; inclut les outils, attentes et retries.
- Durée d'appel : temps observé par le client HTTP, y compris lecture de la réponse.
  Sa somme peut dépasser le temps réel si des appels sont parallèles.
- Groq : `usage.prompt_tokens`, `usage.completion_tokens`, tokens d'entrée en cache
  lorsqu'ils sont fournis. Les raisonnements inclus dans le total de sortie ne sont pas additionnés une seconde fois.
- Ollama : `prompt_eval_count`, `eval_count` ; `/api/embed` est compté séparément comme embeddings.
- Chaque tentative HTTP, y compris les retries du SDK, est enregistrée. Les erreurs,
  réponses sans usage et streams interrompus ont un usage/coût inconnu si non fourni.
- Un hit dans le cache applicatif ne crée aucun nouvel appel fournisseur. Les embeddings
  de documents déjà présents dans le cache ne sont pas recomptés.
- Les appels faits directement sans wrapper ont un identifiant de tâche nul : ils restent
  visibles dans le total et dans `unassignedCalls`, sans durée de tâche inventée.
- RAGAS n'est pas installé et ne produit donc pas encore de métriques ici.

Le journal contient uniquement identifiants, compteurs, statuts, modèles et tarifs.
Il ne contient ni prompts, ni réponses, ni arguments libres de la commande, ni clés API.
Une perte du journal est signalée. Une interruption forcée peut laisser une tâche
`INCOMPLETE` : elle ne compte pas comme tâche terminée.

## Coût

`config/ai-pricing.json` fournit des prix catalogue USD par million de tokens,
avec source et date de vérification. Les tarifs sont copiés dans chaque événement
pour ne pas recalculer silencieusement l'historique après un changement de prix.
Ajouter les tarifs contractuels des autres modèles si nécessaire ; un modèle sans
tarif reste `UNKNOWN`. Les niveaux de service non pris en charge restent inconnus.

Sans tarif de cache fourni, les tokens d'entrée sont évalués au tarif normal :
l'estimation ne reflète pas une éventuelle remise de cache. Les quotas gratuits,
remises commerciales, taxes, outils payants et frais d'autres services sont exclus.
Ce n'est pas une facture. Les totaux connus restent séparés des appels inconnus.

Pour Ollama local, `LOCAL_API_ONLY` indique zéro frais API local ; le coût de
l'électricité, du matériel et de l'hébergement reste **non chiffré**, pas nul.
Le coût total d'exploitation du framework n'est donc pas encore calculé.

Les lignes parentes incluent les appels des enfants. Le total global compte chaque
appel une fois. Ne pas additionner manuellement les lignes de tâches imbriquées.
Les moyennes par tâche terminée concernent les tâches racines `PROCESS_OK` : réussite
du processus, pas preuve de qualité métier. Le verdict du vérificateur est affiché
séparément lorsqu'il est transmis par le pipeline.

## Historique et configuration

Le dernier `logs/pipeline-summary.json` fournit des durées historiques affichées
dans une section distincte. Ses anciens coûts restent inconnus. Les traces historiques
basées sur les caractères ne sont pas converties arbitrairement en tokens.

- `QA_METRICS_FILE` : journal alternatif, notamment pour isoler les tests.
- `QA_METRICS_PRICING_FILE` : catalogue de tarifs alternatif.
- `QA_METRICS_DISABLED=true` : désactiver l'enregistrement.
- `QA_TASK_TIMEOUT_MS` : délai maximal du wrapper (2 heures par défaut).

Sources : [tarifs Groq](https://console.groq.com/docs/models),
[API chat Ollama](https://docs.ollama.com/api/chat),
[API embeddings Ollama](https://docs.ollama.com/api/embed).
