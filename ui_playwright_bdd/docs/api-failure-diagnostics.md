# Preuves API pour l’agent Bug

Le client API enregistre désormais, dans le journal du runner et dans les pièces
jointes JSON Allure des scénarios qui l’utilisent : origine de la cible sans
identifiants, méthode, chemin API fixe, durée, statut HTTP ou code d’erreur réseau,
timeout de 30 secondes, zéro retry et appel HTTP réel. Les paramètres TLS existants
restent inchangés et sont signalés explicitement dans la trace.

Ni corps HTTP, ni mot de passe, ni token ne sont ajoutés au diagnostic. Une réponse
d’authentification sans token valide est un échec explicite.

L’agent Python Bug reçoit automatiquement les sources citées par la stack,
`QACartApiClient.ts`, `world.ts` et les hooks. Ces lectures sont bornées et désignées
comme **code actuel**, pas comme configuration historique. Les pièces jointes API
et URL enregistrées sont sélectionnées par UUID du test et identifiant du run.
Les nouveaux rapports `bug-analysis.json` listent `source_files_read` et `recorded_api`.

Une ancienne exécution sans trace API reste `NOT_RECORDED`. On ne déduit ni
disponibilité du serveur ni réglages historiques à partir du `.env` courant.
Une erreur de création du compte fixture n’établit pas une anomalie de validation
de longueur Todo : le test a échoué avant d’atteindre cette assertion.

Pour produire de nouvelles traces, reproduire le seul scénario concerné avec le
runner existant, puis sélectionner explicitement le nouveau run pour l’analyse.
Le diagnostic reste une hypothèse ; l’agent n’applique aucune correction.
