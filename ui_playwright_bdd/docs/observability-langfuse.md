# Observabilité IA locale : Langfuse et OpenTelemetry

Langfuse est auto-hébergé dans une stack Docker dédiée au framework. Les SDK
officiels Python et JavaScript exportent les traces via OpenTelemetry vers
`http://127.0.0.1:3000`. Aucun compte Langfuse Cloud n’est nécessaire.

## Démarrer et consulter

Docker doit être démarré. Depuis `ui_playwright_bdd` :

```powershell
npm.cmd run obs:setup   # première configuration locale, idempotente
npm.cmd run obs:up      # démarrer les services et conserver les données
npm.cmd run obs:status  # vérifier le serveur et les clés du projet
npm.cmd run obs:check   # vérifier la trace de bout en bout
npm.cmd run obs:verify  # relire la dernière preuve, sans réexécuter le graphe
npm.cmd run obs:open    # ouvrir l’interface
npm.cmd run obs:stop    # arrêter sans supprimer les volumes
```

`obs:up` confirme le lancement des conteneurs, pas la disponibilité de l’API.
Attendre `obs:status` avec `READY`, puis `obs:check` avec `PASS` avant de considérer
la réception des traces comme validée. Le premier démarrage applique les migrations
PostgreSQL et ClickHouse et peut prendre beaucoup plus de temps.

Les identifiants de connexion sont dans `.langfuse/connexion.txt`, ignoré de Git.
Les clés du projet sont enregistrées dans `.env`, également ignoré. Ne jamais
publier ces fichiers ni partager leur contenu dans un ticket ou un chat.

L’interface est exposée uniquement sur localhost. PostgreSQL, ClickHouse, Redis
et le stockage S3 compatible MinIO restent sur le réseau Docker interne. Cette
stack utilise ses propres volumes et ne modifie pas `qa_test_data` ou `qa_rag`.
Les images utilisées sont décrites dans `observability/compose.yaml` ; figer leurs
digests et définir les sauvegardes avant un déploiement chez un client.

## Ce qui est observé

```text
Commande / agent Python
  └─ Graphe LangGraph : préparation, exécution, validation, analyse, rapport
       ├─ Événements LangChain : chaînes, modèles et outils
       └─ Pont Python → Node.js
            ├─ Recherche RAG
            │    ├─ BM25
            │    ├─ Embeddings locaux
            │    ├─ Recherche pgvector en SQL
            │    └─ Reranking si demandé
            └─ Requête Groq : statut, durée, tokens disponibles
```

Les étapes apparaissent seulement lorsqu’elles sont exécutées. Un pipeline qui
ne consulte pas le RAG ne produit pas de recherche artificielle. Les appels
structurés Python peuvent désactiver le RAG lorsque leurs preuves suffisent.
Les preuves des tests restent dans Allure ; elles ne sont pas indexées comme logs
bruts dans le RAG et ne sont pas copiées dans Langfuse.

Le contexte W3C `traceparent` est transmis par `QA_TRACEPARENT` entre processus.
`QA_TRACE_RUN_ID` transporte l’identifiant de run, sans contenu documentaire.
Les métriques existantes restent conservées ; les coûts sont des estimations au
tarif catalogue lorsqu’une mesure de tokens et un tarif sont disponibles.
Un coût inconnu n’est pas inventé. Une requête streaming est terminée dans la
trace lorsque son flux est consommé ou annulé, comme dans les métriques existantes.

## Confidentialité et comportement en erreur

L’instrumentation est volontairement limitée aux métadonnées autorisées : noms
d’étapes, modèles, compteurs, statuts et identifiants techniques. Aucun prompt,
réponse complète, argument d’outil, SQL brut, document, token ou en-tête HTTP n’est
assigné aux observations. Les événements d’exception ne recopient pas les messages
arbitraires ; le statut utilise `OPERATION_FAILED`.

Le callback LangChain est un adaptateur du framework limité aux métadonnées,
pas le callback standard qui capture automatiquement les entrées et sorties.
Les processeurs n’exportent que le scope d’instrumentation `qa-framework` ; aucune
auto-instrumentation HTTP/SQL générique n’est activée.

`LANGFUSE_ENABLED=false` désactive cette intégration. Une indisponibilité de
Langfuse n’autorise aucune opération métier et ne doit pas changer le résultat
des tests. Les exports disposent d’un délai court et les flush sont bornés.
La télémétrie a un transport séparé du gateway Groq, vers l’URL configurée et
validée ; tout endpoint distant exige HTTPS. Ce n’est pas une protection DLP
universelle contre de futures modifications de code : conserver une revue des
attributs et des accès à l’interface.

## Vérification

`obs:check` construit un petit graphe de contrôle LangGraph, utilise LangChain,
propage le contexte vers Node et exécute une vraie recherche hybride dans le
corpus pgvector. Son appel fournisseur est **simulé**, marqué `qa.simulated=true`,
sans requête Groq payante ni estimation de coût réel. Le contrôle vérifie la
présence des observations Python/Node dans la même trace et l’absence de capture
des entrées/sorties, ainsi que le lien parent entre Python et Node. La lecture
utilise l’API observations v2 de Langfuse v4 ; l’ancienne API traces est indisponible
en mode `events_only`. Rapport privé : `.langfuse/integration-check.json`.
La preuve technique est conservée dans `.langfuse/last-proof.json` avant la
vérification de réception. Si l’ingestion est retardée, `obs:verify` contrôle
uniquement cette exécution enregistrée ; il ne lance aucun nouveau scénario.

Ce contrôle ne lance pas toute la régression Playwright et ne démontre pas une
amélioration de qualité des réponses. Allure reste le rapport de tests et DeepEval
reste l’évaluation des réponses IA. Langfuse n’est pas une base vectorielle.

## Exploitation chez le client

Le premier téléchargement et le démarrage des six services demandent du temps,
du disque et plusieurs Go de RAM. Le PC de développement de 8 Go peut être sous
pression ; privilégier un serveur Linux ou Kubernetes dimensionné chez le client.
Si Docker renvoie des erreurs 500/502 ou si l’API ne répond pas, vérifier d’abord
la RAM et l’espace disque disponibles. Libérer les applications inutilisées avant
de relancer Docker, puis `obs:up`, `obs:status` et `obs:check`. Ne pas supprimer les
volumes pour résoudre un simple manque de ressources : ils contiennent les traces
et la configuration du projet.

Un échec Docker `Wsl/Service/RegisterDistro/CreateVm/ERROR_TIMEOUT` concerne le
démarrage de la VM WSL. Vérifier `wsl --version`, `wsl --update --web-download` et
`wsl --list --verbose`. Si les distributions sont arrêtées et que WSL reste bloqué,
`wsl --shutdown`, puis un redémarrage du service `WslService` depuis un PowerShell
administrateur peuvent être nécessaires avant de relancer Docker Desktop.
Ne pas interrompre d’autres distributions en cours d’utilisation.
La version open source couvre le cœur d’observabilité ; certaines fonctionnalités
Enterprise et le service cloud ont une tarification distincte. Définir les droits,
la conservation, les sauvegardes et l’intégration à la supervision du client.

Références : [Docker Compose officiel](https://langfuse.com/self-hosting/deployment/docker-compose),
[initialisation automatique](https://langfuse.com/self-hosting/administration/headless-initialization),
[intégration LangChain/LangGraph](https://langfuse.com/integrations/frameworks/langchain).
