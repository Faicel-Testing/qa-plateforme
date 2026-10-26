# PostgreSQL + pgvector pour le RAG

Le poste utilise désormais une véritable base vectorielle : **PostgreSQL 18 +
pgvector 0.8.7**, sur l’instance locale `127.0.0.1:5433`. La base `qa_rag` et le
compte non-superutilisateur `qa_rag` sont séparés de `qa_test_data` et `qa_data`.
Les mots de passe restent dans `.env` et les fichiers locaux ignorés de Git.

## Parcours actif

Sources autorisées → fragments → embeddings E5 locaux (384 dimensions) →
table `qa_rag.chunks` → similarité cosinus SQL + BM25 → fusion RRF →
reranking Groq optionnel → contexte des agents.

Le modèle reste local et gratuit. pgvector ne calcule pas les embeddings : il
les stocke et les compare. Aucun abonnement cloud n’est nécessaire sur ce poste.
Groq reste un service distinct pour le reranking et la génération.

## Commandes

```powershell
npm.cmd run rag:status
npm.cmd run rag:index
npm.cmd run rag:check
npm.cmd run rag:pg:test
```

`rag:index` importe automatiquement le cache vectoriel local compatible lors du
premier passage. Ensuite, les vecteurs de documents sont relus dans PostgreSQL.
Les recherches utilisent réellement l’opérateur cosinus `<=>` dans PostgreSQL.
Le cache JSON reste utilisable avec `RAG_VECTOR_STORE=file` ; il n’est pas le
stockage actif lorsque `RAG_VECTOR_STORE=pgvector` est configuré.

## Installation locale Windows reproductible

Prérequis : PostgreSQL 18, instance dédiée créée par `data:setup`, outils C++ x64
Visual Studio (sur ce poste : Build Tools 2019), Git et modèle d’embeddings installé.

```powershell
# TLS : utiliser les autorités approuvées par le client.
git clone --depth 1 --branch v0.8.7 https://github.com/pgvector/pgvector.git .qa-rag/pgvector-src
cmd /c scripts\build-pgvector.cmd
npm.cmd run rag:pg:setup
npm.cmd run rag:index
```

La compilation produit la DLL depuis la source officielle épinglée. Le setup la
place dans `.qa-rag/pgvector-extension`, configure `extension_control_path` pour
la base `qa_rag`, puis active l’extension comme administrateur local. Les appels
du framework utilisent ensuite le compte non-superutilisateur. Cette installation
utilise le mécanisme PostgreSQL 18 des extensions hors du répertoire système ;
elle ne demande pas de copie dans `Program Files`. Ne pas déplacer ni supprimer
le répertoire de l’extension pendant son utilisation. Une mise à jour de DLL
différente exige une opération de maintenance explicite.

Dans un environnement client, utiliser de préférence l’installation de pgvector
gérée par ses DBA. Le script local n’est pas une procédure universelle de production.

## Configuration

```dotenv
RAG_MODE=hybrid
RAG_VECTOR_STORE=pgvector
RAG_PGHOST=127.0.0.1
RAG_PGPORT=5433
RAG_PGDATABASE=qa_rag
RAG_PGUSER=qa_rag
RAG_PGPASSWORD=... # renseigner localement, ne jamais publier
```

`RAG_CORPUS_ID` permet de nommer un corpus partagé ; par défaut, le chemin racine
du projet est haché pour isoler les corpus. Deux machines souhaitant partager un
corpus doivent utiliser le même identifiant et des sources synchronisées. Ne pas
utiliser cet identifiant comme mécanisme d’autorisation entre utilisateurs.
Les connexions distantes imposent TLS avec vérification de certificat.

## Cohérence et limites

Chaque passage conserve source, lignes, type, empreinte du texte et du corpus,
identité du modèle et vecteur. La mise à jour se fait en transaction, avec verrou
par corpus. Les modifications et suppressions remplacent l’instantané concerné.
Les résultats SQL sont rapprochés des sources actuelles avant utilisation : un
contenu stocké ne devient pas une preuve métier validée.

Le compte applicatif possède les objets de sa base dédiée ; ce n’est pas un
superutilisateur PostgreSQL. Ce premier connecteur n’implémente pas la réplication
des permissions Confluence/Jira ni une isolation multi-tenant de production.
Les connecteurs Jira/Xray ne sont pas ajoutés par cette installation.

La recherche actuelle est exacte, sans index approximatif HNSW : ce choix convient
au petit corpus actuel et conserve le rappel. Évaluer volumes, latence, filtrage,
droits documentaires, sauvegardes et pertinence avant un déploiement grand compte.
Une panne SQL produit `bm25-fallback` avec une raison explicite ; `--strict` et
l’indexation échouent au lieu d’annoncer une réussite vectorielle.

Les requêtes de consultation pour pgAdmin/DBeaver sont dans
[`database/queries/rag-pgvector.sql`](../database/queries/rag-pgvector.sql).

Références : [pgvector](https://github.com/pgvector/pgvector),
[chemins d’extensions PostgreSQL 18](https://www.postgresql.org/docs/18/runtime-config-client.html).
