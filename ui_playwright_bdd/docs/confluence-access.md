# Rétablir la synchronisation Confluence

Diagnostic du 16 octobre 2026 sur le site configuré :

- Le site répond : HTTP 200 sur `/_edge/tenant_info`.
- Le compte du connecteur reçoit HTTP 403 sur `/wiki/rest/api/user/current` :
  `Request rejected because caller cannot access Confluence`.
- La page racine et l’espace renvoient HTTP 404, également sur la passerelle
  officielle Atlassian avec le cloudId du site.

Le connecteur ne peut donc pas établir que les pages sont supprimées. Il faut
d’abord rétablir les droits du compte et du jeton configurés dans `.env`.

1. Dans l’administration Atlassian du site, vérifier que le compte correspondant
   à `CONFLUENCE_EMAIL` est actif et dispose d’un accès produit Confluence.
2. Vérifier que ce compte peut ouvrir l’espace et le dossier spécifiés dans
   `config/confluence-rag.json`, avec les restrictions de pages applicables.
3. Vérifier que `CONFLUENCE_API_TOKEN` appartient à ce même compte, n’est pas
   expiré et autorise les lectures requises. Sinon configurer localement les
   identifiants d’un compte autorisé, sans les publier dans un ticket ou le chat.
4. Si le jeton utilise des scopes, employer l’URL de passerelle Atlassian adaptée
   au cloudId et les scopes requis ; le connecteur actuel utilise l’URL directe
   du site. Le test `--platform` permet de comparer les statuts sans modifier
   les pages ni afficher leur contenu. Un 404 sur les deux routes ne justifie
   pas de changer automatiquement l’allowlist.
5. Relancer :

```powershell
node scripts/check-confluence-access.cjs --platform
npm.cmd run confluence:sync
npm.cmd run confluence:status
node scripts/check-confluence-rag.cjs
```

Résultat attendu : `READY` avec les six pages, puis `verified: true` pour la
présence des règles Confluence dans le contexte RAG. Le contrôle RAG désactive
le reranking pour ne pas appeler Groq.

Le connecteur conserve l’exclusion des anciennes données dès que la lecture
échoue ; il ne remplace pas une source inaccessible par une copie périmée.
Il distingue désormais un refus d’accès produit d’un simple 404 de page.

Référence : [jetons API avec scopes Confluence](https://support.atlassian.com/confluence/kb/scoped-api-tokens-in-confluence-cloud/).
