# Diagnostic du pipeline — 15 octobre 2026

## Commande concernée

`npm.cmd run agent:pipeline:full` lance l'orchestrateur historique JavaScript.
`npm.cmd run agents:pipeline -- full` lance le pipeline natif Python, qui exécute
les tests puis analyse les échecs ; il ne génère pas de nouvelles features.
Ces parcours ont des périmètres différents, même si le runtime des agents enfants
du pipeline historique peut être configuré en Python.

## Story sans exigences : APPLICATIO-6

La description Plane indique explicitement un titre historique non spécifié et des
exigences à clarifier. Le codegen JavaScript refuse désormais cette entrée avant
l'appel de génération et affiche `A CLARIFIER`, sans inventer de scénario.
Les descriptions absentes et les évolutions explicitement marquées « exigences
historiques à confirmer » sans scénario associé sont également bloquées.
Cette vérification n'est pas une certification de complétude des autres stories.

Le code de sortie reste non nul si une story requise est à clarifier. Corriger le
backlog avec des exigences validées est nécessaire pour terminer cette génération.
Le bilan distingue propositions non appliquées, erreurs techniques et stories à clarifier.

## Refus de la passerelle

L'événement du 13 octobre à 21:30:08 UTC concerne Ollama. Un verrou `quota.lock`
portant le même instant était encore présent, alors que son processus propriétaire
n'existait plus. Le script de récupération l'a archivé après ses vérifications ;
le registre des quotas a été conservé. L'erreur système originale n'était pas
enregistrée, donc sa cause exacte ne peut pas être reconstituée avec certitude.

La libération du verrou retente maintenant les erreurs transitoires Windows
EPERM/EBUSY/EACCES au plus cinq fois. Un échec persistant reste bloquant avec le motif
`QUOTA_RELEASE_FAILED`. Quelques codes système non sensibles peuvent être journalisés
pour les autres erreurs imprévues, sans corps de requête ni secret. Les limites,
destinations et contrôles TLS restent inchangés. Un appel modèle minimal réel a
réussi après récupération du verrou.

## Confluence

La synchronisation réelle renvoie HTTP 404. Cela peut correspondre à une page
absente ou non accessible avec les identifiants configurés. Le message affiche
désormais ce code et invite à vérifier les identifiants de pages et leurs droits.
Le corpus Confluence indisponible reste exclu ; aucun contenu périmé n'est réintroduit.
Les références sont dans `config/confluence-rag.json`. Ne pas remplacer les pages
ou les droits par des valeurs supposées pour masquer ce problème.

## Pourquoi les tests continuent

Le codegen enregistre des propositions soumises à revue ; le runner exécute les
sources existantes. Il peut donc fournir les résultats de régression même après
une génération incomplète. Le pipeline l'annonce maintenant explicitement et
continue de bloquer sa validation globale si une étape requise échoue.

## Vérifications

- 58 tests locaux de génération, passerelle et pipeline réussis.
- Vérification réelle d'APPLICATIO-6 : refus explicite avant génération, aucun candidat créé.
- Appel modèle minimal : `MODEL_AVAILABLE`.
- Aucun run complet, publication externe ou modification des features n'a été lancé
  pour reproduire la capture.
