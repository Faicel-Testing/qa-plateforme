# Gateway de sécurité IA

La couche applicative commune est `scripts/agents/shared/ai-gateway.js`. La politique versionnée est `config/ai-gateway.json`.

```text
Agents : llm.js (chat, outils, streaming, Groq uniquement)
Juge DeepEval : deepeval-judge.js
Embeddings : embedding-client.js
                    ↓
             Gateway commun
                    ↓
      Transport mesuré : meteredFetch
                    ↓
               Groq
```

## Contrôles appliqués

- Origines, routes et modèles explicitement autorisés dans la politique. Seul Groq est autorisé, avec HTTPS. Identifiants dans l'URL, query strings, redirections, en-têtes Host/proxy et transports TLS personnalisés sont refusés.
- Blocage avant envoi des valeurs de secrets connues dans les variables d'environnement, des formats de clés reconnus, des Bearer tokens et des clés privées. Les valeurs JSON décodées sont inspectées, y compris les arguments d'outils et les entrées d'embeddings. Les en-têtes d'authentification du SDK restent utilisables.
- Précontrôle des messages avant la recherche RAG et avant le cache de `llm.js`. Un refus du gateway n'entraîne pas un fallback vers un autre modèle.
- Corps JSON limité à 200 000 octets ; sorties limitées à 4 096 tokens par appel. Les demandes explicites dépassant ce plafond sont refusées ; sans limite fournie, le plafond est ajouté. Une seule complétion par appel.
- Délai de transport maximal de 120 secondes, compatible avec l'annulation de l'appelant et le streaming.
- Maximum de 60 requêtes par minute dans ce workspace, toutes catégories confondues. Chaque tentative HTTP et chaque retry consomme une réservation.
- Budget conservateur de 1 000 000 unités réservées par tâche sur 24 heures : octets du corps JSON + plafond de sortie. **Ce ne sont pas des tokens mesurés ni un plafond de facture en dollars.** Les coûts réels estimés restent dans les métriques existantes.
- L'identifiant `QA_GATEWAY_BUDGET_ID` est propagé aux sous-processus par le runtime : agents enfants et juges Python/Node partagent le budget de la tâche racine. Hors runtime, le budget est associé au processus.

## Audit et refus

`logs/gateway/audit.jsonl` contient ALLOW/BLOCK, motif, fournisseur/modèle autorisé, identifiant de tâche et limites. Il ne contient ni prompts, réponses, secrets ni en-têtes. ALLOW signifie admission avant le réseau, pas réussite du fournisseur : consulter les métriques pour la réussite HTTP.

`logs/gateway/quota.json` partage les réservations entre processus, avec verrou exclusif pour la lecture/écriture et synchronisation sur disque avant envoi. Une écriture interrompue peut laisser un journal invalide : il sera refusé, jamais réinitialisé silencieusement. Un journal corrompu, un audit impossible ou un verrou occupé bloque l'appel. Après un crash, un verrou résiduel nécessite une intervention locale après vérification qu'aucun processus ne l'utilise. Ne pas effacer le quota pour contourner un budget.

Les refus portent le code `AI_GATEWAY_BLOCKED`. Les appels bloqués avant le réseau n'ont pas de coût fournisseur mesuré ; ils apparaissent dans l'audit de sécurité, pas dans les appels HTTP des métriques. Le cache ne déclenche pas de réservation réseau.

## TLS et certificats

Le lanceur `scripts/measure-task.js` charge maintenant `.env` avant de démarrer le processus Node de l'agent. Sur ce poste, `NODE_EXTRA_CA_CERTS=logs/plane/windows-ca.pem` est résolu en chemin absolu et transmis au processus enfant. Cela rend le bundle effectif pour les commandes npm qui utilisent ce lanceur. Pour un lancement direct `node scripts/agents/...`, définir la variable dans le shell avant Node, comme ci-dessous. Ne pas utiliser `NODE_TLS_REJECT_UNAUTHORIZED=0`.

Le gateway attend au maximum 2,5 secondes lorsqu'un autre processus détient brièvement le verrou de quota. Les refus de budget et de fréquence restent immédiats. Les nouveaux verrous enregistrent le PID et leur date. Après une interruption, `scripts/repair-gateway-lock.ps1` peut archiver un verrou ancien uniquement si aucun processus Node actuel ne peut l'avoir détenu ; il ne réinitialise jamais `quota.json`. En cas de doute, il refuse la récupération.

Les affectations qui désactivaient globalement TLS ont été retirées des scripts d'agents. `.env.example` et la configuration locale utilisent `NODE_TLS_REJECT_UNAUTHORIZED=1`. Si un processus réintroduit la valeur `0`, le gateway refuse ses appels.

Sur cette machine, charger le bundle public des autorités Windows **avant de démarrer Node** :

```powershell
$env:NODE_EXTRA_CA_CERTS = Join-Path (Get-Location) 'logs/deepeval/windows-ca.pem'
$env:NODE_TLS_REJECT_UNAUTHORIZED = '1'
```

Sur un autre poste, utiliser les autorités approuvées par votre organisation. Une variable chargée par dotenv après le démarrage ne suffit pas à charger des CA supplémentaires. Voir la [documentation Node sur NODE_EXTRA_CA_CERTS](https://nodejs.org/api/cli.html#node_extra_ca_certsfile). Les autres intégrations HTTPS des scripts bénéficient aussi du rétablissement du TLS ; elles peuvent nécessiter le même bundle.

## Périmètre et limites

C'est un gateway **dans l'application**, pas un reverse proxy, un pare-feu réseau ou une authentification multi-tenant. Il couvre les clients LLM existants ; du nouveau code appelant directement un SDK doit également être branché sur ce module. Un processus disposant de droits d'écriture sur la politique ou le quota peut les modifier : ce n'est pas une frontière contre du code local hostile.

La détection de secrets n'est pas un DLP exhaustif : secrets inconnus, encodés autrement ou données personnelles non reconnues peuvent lui échapper. Elle ne garantit pas la détection des injections de prompt ni la sécurité d'une action demandée par le modèle. Les extraits RAG restent des données non fiables, et les validations d'outils, vérificateurs et contrôles métier demeurent nécessaires.

Les secrets connus et les formats de clés reconnus provoquent un blocage. Les autres contenus passent par `payload-privacy.js` : adresses email, identifiants explicites, cookies et autorisations sont masqués. Les URL HTTP(S) présentes dans les données sont remplacées par un hôte anonyme sans chemin, paramètres ou fragment. Les destinations réseau du fournisseur restent contrôlées séparément. Ce traitement inclut les objets imbriqués et les arguments d'outils JSON.

Le chat filtre avant le RAG et le cache, puis le gateway filtre à nouveau avant le transport pour couvrir aussi streaming, juge, reranking et embeddings. Les réponses Groq du chat sont contrôlées avant stockage dans le cache commun, et les anciennes réponses de ce cache sont contrôlées à la lecture. Les erreurs du tracer sont enregistrées sans leur contenu. Les anciens journaux, captures, mémoires et caches ne sont pas nettoyés rétroactivement.

Pour interdire tout envoi cloud via le gateway, définir `AI_LOCAL_ONLY=true` avant le lancement. Les appels IA sont alors bloqués : aucun fournisseur local de secours n’est configuré. Cela ne constitue pas une règle réseau pour les services externes non IA.

Le masquage peut limiter la précision des analyses : un extrait cité avec des valeurs masquées peut nécessiter une revue locale pour correspondre au fichier original. Les données personnelles non reconnues et les documents confidentiels sans marqueur restent hors garantie ; seules des données autorisées doivent être sélectionnées comme sources. L'audit Quality exclut les dossiers fixtures, credentials, sessions et .auth.

## Vérification locale

```powershell
node --test scripts/agents/tests/ai-gateway.test.js scripts/agents/tests/ai-gateway-integration.test.js
```

Les tests utilisent des transports simulés : aucun appel fournisseur n'est nécessaire. Ils vérifient les blocages avant envoi, le quota persistant, les vrais chemins SDK du chat/streaming/juge/embeddings et l'absence de fallback après refus.
