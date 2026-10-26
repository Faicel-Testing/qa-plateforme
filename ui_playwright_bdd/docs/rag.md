# RAG hybride local : BM25 et embeddings

Sources locales → découpage → BM25 + embeddings multilingues → fusion RRF
→ reranking Groq optionnel → contexte → réponse Groq → vérification.

Depuis le 22 octobre 2026, les embeddings sont opérationnels sur CPU avec
`@huggingface/transformers` et `Xenova/multilingual-e5-small` quantifié q8 (384 dimensions).
Le fournisseur de génération reste Groq. Aucun serveur Ollama, Chroma ou service
d’embeddings payant n’est requis. Les vecteurs sont stockés dans PostgreSQL + pgvector
sur ce poste (`RAG_VECTOR_STORE=pgvector`, base dédiée `qa_rag`). Le cache JSON local
reste un mode portable alternatif. Voir [la connexion pgvector](rag-pgvector.md).
Le mode portable reste BM25 par défaut ; le poste est configuré en `RAG_MODE=hybrid`.

## Reranking intégré

Le module `scripts/agents/shared/reranker.js` fait réévaluer la pertinence des candidats par **Groq / openai/gpt-oss-20b**. C'est un reranker LLM, pas un cross-encoder local. Il est activé dans la configuration `.env` de ce poste et dans `.env.example` ; sans variable explicite, il reste désactivé.

```dotenv
RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=openai/gpt-oss-20b
RAG_RERANK_CANDIDATES=12
RAG_RERANK_STRICT=false
```

Après le classement BM25, les 12 premiers candidats au maximum sont notés de 0 à 100 par un appel distinct. Le top-k (4 par défaut) et le budget de contexte sont appliqués **après** ce classement. Si un nombre de candidats inférieur au top-k est configuré, le pool est élargi au top-k. En mode BM25 ou fallback lexical, la même étape s'applique au classement lexical. Avec moins de deux candidats, aucun appel n'est effectué.

Les identifiants retournés doivent correspondre exactement aux candidats : aucun ajout, doublon ni score manquant n'est accepté. Le modèle ne réécrit pas les extraits. Les chemins, lignes et empreintes sont conservés ; `rerankScore`, `rerankAdjustedScore` et `retrievalRank` rendent le classement inspectable. L'historique IA non vérifié conserve une pénalité de 0,6. Les égalités gardent l'ordre de recherche précédent. Le score de pertinence n'est pas une probabilité de vérité.

La question est limitée explicitement à 4 000 caractères pour cet appel, avec `queryTruncated` dans les métadonnées. Les candidats sont les chunks déjà bornés par le RAG. Un changement du corpus pendant le scoring invalide la recherche. Une réponse invalide ou une panne conserve le classement initial et indique `reranking.status=UNAVAILABLE`. En mode strict (`--strict` ou `RAG_RERANK_STRICT=true`), elle provoque une erreur. Un refus du gateway reste toujours bloquant.

L'appel utilise le **gateway commun**, les autorités TLS configurées, un délai SDK de 30 secondes, aucun retry SDK et un plafond de 2 048 tokens de sortie. Les questions et extraits candidats sont envoyés à Groq, lorsque le reranking est activé. Ce module n'appelle pas `llm.chat`, donc il ne peut pas déclencher une boucle RAG/reranking récursive.

Les consommations apparaissent sous la catégorie `reranking` dans le rapport JSON des métriques ; le rapport HTML par tâche inclut ces appels. Les échantillons DeepEval conservent les métadonnées de reranking. Pour comparer avant/après, évaluer les mêmes questions avec `RAG_RERANK_ENABLED=false`, puis `true`. L'intégration technique ne démontre pas à elle seule une amélioration métier : mesurer pertinence, fidélité, latence et coût sur un dataset revu.

```powershell
# Avec les certificats de confiance déjà configurés, voir docs/ai-gateway.md :
npm run rag:search -- "Comment vérifier la suppression d'une tâche ?" --strict
npm run metrics:report
node --test scripts/agents/tests/reranker.test.js
# Test réel synthétique (un appel Groq, sans extraits du projet) :
node scripts/measure-task.js scripts/check-reranker.js --live
```

## Sources

### Confluence : dossier de spécification

Le connecteur `scripts/agents/shared/confluence-rag.js` lit uniquement les six pages explicitement autorisées dans `config/confluence-rag.json`. Il vérifie leur espace, leur parent, leur statut courant et leur version. La page sommaire sert à contrôler le dossier ; l'archive initiale, les pièces jointes et les liens sortants ne sont pas importés. Une nouvelle page doit être ajoutée explicitement à la liste autorisée.

```powershell
npm.cmd run confluence:sync
npm.cmd run confluence:status
npm.cmd run rag:index
npm.cmd run rag:search -- "Quelle est la limite cible des tâches Todo ?"
```

`CONFLUENCE_RAG_ENABLED=true` active le rafraîchissement à la demande, avant une recherche ou une indexation, lorsque la dernière copie a plus de 15 minutes. Ce n'est pas un service de surveillance en arrière-plan. Planning, Codegen, Quality, Bug et Advisor utilisent déjà le RAG commun dans leurs appels `chat` ; aucun changement du moteur LLM n'est nécessaire. Les chemins qui n'appellent pas ce RAG, notamment le streaming, ne sont pas enrichis.

Les accès restent dans `.env` (`CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`), jamais dans les extraits. `CONFLUENCE_CA_FILE` permet un bundle d'autorités approuvées sans désactiver TLS. Les requêtes sont exclusivement GET sur l'hôte configuré, sans suivi de redirections ; elles sont limitées à 15 secondes et 1 Mio par page.

La copie locale atomique `.qa-rag/confluence.json`, ignorée par Git, remplace le corpus précédent uniquement après lecture complète. Un échec invalide les pages Confluence précédentes ; les sources locales du RAG restent disponibles avec une exclusion explicite de Confluence. Un cache de plus de 24 heures ou incompatible avec la liste autorisée est exclu. Les droits révoqués ou déplacements sont détectés au prochain rafraîchissement, pas instantanément. Après échec, une minute de temporisation évite les appels répétés ; `confluence:sync` force une nouvelle tentative.

Chaque passage conserve pageId, titre, version, URL, date de synchronisation et statut `UNAPPROVED_REFERENCE`. Aucun texte de page ne peut s'auto-déclarer approuvé ; les documents actuels sont tous des références de travail. Les agents doivent distinguer règles proposées, décisions ouvertes et constats historiques. Les données restent non fiables et passent par le gateway existant avant le LLM. Les URL et emails du corps sont masqués avant stockage/embeddings ; l'URL de provenance reste disponible localement et peut être masquée par le gateway avant génération. Les références pageId/version permettent de retrouver la source sans exposer son adresse au fournisseur.

Les versions modifiées invalident les fragments et leurs vecteurs. Cette intégration ne déclenche aucune modification des tests, aucune acceptation métier et aucune publication vers Confluence.

- `qa-knowledge/` et `specs/` : `.md`, `.txt`, `.feature`, si présents.
- `src/features/` : scénarios existants.
- `memory/episodes.jsonl` : résumé et champs sélectionnés des épisodes, identifiés
  comme historique IA non vérifié et pondérés à la baisse dans la recherche.
  Les épisodes de démonstration (`trigger: seed`) sont exclus.

Les `.env`, logs bruts, pièces jointes et résultats Allure ne sont pas indexés.
Les preuves du run courant restent fournies par les agents comme auparavant.
Cette version ne synchronise pas Jira dans l'index.

## Commandes

Depuis `ui_playwright_bdd` :

```powershell
npm run rag:setup
npm run rag:index
npm run rag:status
npm run rag:check
npm run rag:search -- "Pourquoi la connexion est refusée ?" --strict
```

`rag:setup` télécharge uniquement les cinq fichiers nécessaires du modèle, depuis
la révision épinglée `761b726dd34fb83930e26aab4e9ac3899aa1fa78` de Hugging Face,
puis construit l’index hybride. Il ne modifie pas `.env` : y choisir `RAG_MODE=hybrid`
pour les commandes suivantes. Les fichiers sont stockés dans `.qa-rag/local-models/`,
ignoré par Git. TLS reste activé. Le manifeste SHA-256 détecte les modifications
locales des fichiers ; il ne constitue pas une signature indépendante de l’éditeur.
Le téléchargement ne reçoit aucun texte du corpus. L’inférence interdit les
chargements distants et les requêtes réseau dans son worker.

`rag:index` écrit un instantané dans `.qa-rag/index.json`, ignoré par Git.
La recherche utilise les sources actuelles et un cache en mémoire : l'instantané
disque n'est jamais accepté comme preuve sans les sources. Une modification ou
suppression invalide le cache. Aucune réindexation manuelle n'est nécessaire pour
que les agents voient les changements.

En mode fichier, le cache `.qa-rag/vectors-*.json` associe chaque vecteur au modèle, à son digest,
aux préfixes de requête/document et au contenu du fragment. Les documents inchangés
ne sont pas recalculés. Un changement de modèle ou de source invalide les entrées
concernées ; les documents supprimés disparaissent des recherches. Les requêtes
identiques sont mises en cache en mémoire (64 entrées maximum).
En mode pgvector, les documents sont persistés dans `qa_rag.chunks` et la similarité
cosinus est calculée par SQL. Les 40 meilleurs candidats sémantiques au maximum
sont fusionnés avec BM25 ; `semantic.matched` compte ces candidats retournés,
pas tous les passages au-dessus du seuil dans l’ensemble de la base.

RRF combine les 40 premiers résultats de chaque classement avec `1 / (60 + rang)`.
Un document trouvé par les deux méthodes reçoit les deux contributions. Les doublons
sont fusionnés par identifiant. Le résultat expose les rangs et scores de chaque méthode.
L'historique IA garde une pondération réduite, sans devenir une preuve validée.

Configuration dans `.env` :

```dotenv
RAG_MODE=hybrid
RAG_EMBEDDING_MODEL=Xenova/multilingual-e5-small
RAG_EMBEDDING_TIMEOUT_MS=120000
RAG_EMBEDDING_BATCH_SIZE=8
RAG_MIN_SIMILARITY=0.35
```

Les préfixes `query: ` et `passage: ` sont ajoutés selon le type d’entrée. Le worker
utilise le CPU avec deux threads. Les entrées longues sont traitées par fenêtres
de 400 tokens et leurs vecteurs moyennés, sans troncature silencieuse. Le worker
est interrompu à l’annulation ou au délai maximal. Préindexer avec `rag:index`
évite de recalculer les passages inchangés à chaque commande.

`RAG_MODE=bm25` désactive tous les appels d'embeddings. Le seuil de similarité est
un paramètre de recherche, pas une probabilité de vérité ; il doit être évalué avec
les questions du projet. Pour un autre modèle, configurer si nécessaire
`RAG_QUERY_PREFIX` et `RAG_DOCUMENT_PREFIX` selon ses instructions.

Une panne, un modèle absent ou des vecteurs invalides produisent `mode: bm25-fallback`
et une raison explicite, jamais une fausse réussite hybride. `--strict` échoue dans
ce cas. `rag:index` exige lui aussi une indexation sémantique réussie en mode hybride.
Un délai de 15 secondes évite les tentatives répétées après une panne.

L'enrichissement est actif par défaut dans `llm.chat` pour `codegen`, `planning`,
`quality`, `bug` et `advisor`, y compris les helpers structurés qui passent par chat.
Désactivation : `RAG_ENABLED=false` ou `chat(messages, { rag: false })`.
Les fonctions streaming ne sont pas enrichies dans cette version.

Les embeddings sont calculés localement dans un worker Node/ONNX sans transport HTTP.
Le masquage existant reste appliqué. Les extraits retenus sont ensuite envoyés à Groq
si le reranking ou la génération est demandé, via le gateway existant. Les motifs de secrets usuels sont masqués ;
ce filtre ne garantit pas la suppression de toute donnée sensible.

## Limites et traçabilité

Chaque extrait contient son identifiant, le fichier, les lignes, l'empreinte du
fichier et son type de source. Les données récupérées sont séparées des règles du
système et présentées comme non fiables. Les explications sont invitées à citer
les sources ; les citations du modèle ne sont pas automatiquement contrôlées ici.
Le vérificateur commun conserve ses statuts : retrieval ne signifie pas validation.

Au maximum quatre extraits sont sélectionnés dans un budget de 4 500 caractères
de JSON, auquel s'ajoutent les règles fixes. Sans correspondance, aucun contexte
n'est ajouté. Limites : 1 Mio par fichier, 10 Mio pour le corpus et 1 800 caractères
par extrait. Les fichiers ignorés et lignes trop longues sont signalés.

Multilingual E5 apporte la recherche sémantique multilingue ; elle ne garantit pas
la pertinence de chaque extrait. La qualité dépend aussi des documents, des questions
et du seuil. Les requêtes sémantiques sont limitées explicitement à 4 000 caractères
et le résultat signale une limitation éventuelle. Le worker traite les entrées par fenêtres au lieu de les tronquer.

## Tests sans fournisseur externe

```powershell
node --test scripts/agents/tests/rag.test.js scripts/agents/tests/hybrid-rag.test.js
```

Pertinence sur petits corpus, fraîcheur, budget, historique, exclusions, masquage,
index altéré et injection dans le vrai client LLM avec fournisseur simulé.
Les tests hybrides vérifient aussi la recherche sans mots communs avec vecteurs simulés,
RRF, l'invalidation du cache, les dimensions, les pannes et la fraîcheur pendant les appels.
`rag:check` vérifie le corpus réel sans reranking et exige le succès sémantique
si le mode hybride est sélectionné. Le contrôle réel multilingue séparé est :

```powershell
node scripts/check-local-embeddings.cjs
```

Il utilise deux questions françaises et trois documents anglais synthétiques,
vérifie le résultat attendu, les 384 dimensions, le cache et l’annulation avant
appel. Rapport : `.qa-rag/local-embedding-check.json`. Ce contrôle d’intégration
limité ne démontre pas un gain global de pertinence ; comparer le même dataset
revu en BM25 et hybride avec DeepEval et une revue métier.

Références : [Transformers.js, modèles locaux](https://huggingface.co/docs/transformers.js/custom_usage),
[modèle E5 multilingue](https://huggingface.co/Xenova/multilingual-e5-small).
