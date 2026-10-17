# Exécution avec Groq uniquement

Configuration active depuis le 16 octobre 2026 :

```dotenv
GROQ_API_KEY=<secret dans .env ou dans le gestionnaire de secrets>
GROQ_MODEL=openai/gpt-oss-120b
DEEPEVAL_JUDGE_PROVIDER=groq
DEEPEVAL_JUDGE_MODEL=openai/gpt-oss-120b
RAG_MODE=bm25
RAG_RERANK_ENABLED=true
RAG_RERANK_MODEL=openai/gpt-oss-20b
```

Les agents LangChain, les scripts Node.js, le reranker et le juge DeepEval
utilisent le même fournisseur Groq, derrière la gateway existante. Les tests UI
Playwright/Cucumber et les rapports Allure ne nécessitent pas le LLM.

La recherche BM25 s’exécute localement sans embeddings ni service Ollama.
Le reranking peut transmettre à Groq la question et les extraits candidats.
Ce mode perd la recherche sémantique par vecteurs de l’ancienne configuration :
la pertinence doit être évaluée sur les questions métier.

```powershell
npm.cmd run rag:setup
npm.cmd run rag:check
npm.cmd run rag:status
npm.cmd run agents:pipeline -- full
npm.cmd run eval:deepeval:check
npm.cmd run eval:deepeval -- --limit 1
npm.cmd run allure:report
```

Le circuit breaker/cache existant est conservé pour les appels des agents.
En cas de panne Groq ou de circuit ouvert, le transport échoue explicitement :
aucun autre fournisseur et aucune réponse artificielle de secours ne sont utilisés.
Le juge reste sans secours fournisseur. Les délais, quotas et contrôles TLS sont conservés.
Une ancienne variable `AI_LOCAL_ONLY=true` bloque les appels cloud ; elle ne
sélectionne plus de fournisseur local.

Le SDK npm, les commandes pull/list et l’installateur Ollama sont supprimés.
Les anciens journaux, rapports, modèles téléchargés et caches ne sont pas effacés.
Les compteurs historiques peuvent encore mentionner cet ancien fournisseur.
Les rapports d’évaluation existants ne sont jamais réécrits en PASS.
