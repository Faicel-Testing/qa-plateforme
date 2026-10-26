"""Support autonome HTML animé et imprimable pour préparer l'entretien QA."""
from pathlib import Path
from html import escape
import json

ROOT = Path(__file__).resolve().parent

def card(title, definition, role='', source=''):
    return f'<article class="card" tabindex="0" data-note="{escape(definition + " " + role, quote=True)}"><h3>{escape(title)}</h3><p>{escape(definition)}</p>{f"<p class=role>{escape(role)}</p>" if role else ""}{f"<code>{escape(source)}</code>" if source else ""}</article>'

def grid(items, columns=3):
    return f'<div class="grid cols-{columns}">' + ''.join(card(*item) for item in items) + '</div>'

def note(text):
    return '<aside class="note">' + text + '</aside>'

def flow(items):
    return '<div class="flow">' + ''.join(f'<div class="node" tabindex="0" data-note="{escape(desc, quote=True)}"><b>{escape(title)}</b><span>{escape(desc)}</span></div>' for title, desc in items) + '</div>'

slides = []
def slide(kicker, title, intro, body):
    slides.append((kicker, title, intro, body))

slide('01 / LE MESSAGE À RETENIR', 'Playwright BDD & IA',
      'Architecture expliquée • Définitions • Parcours guidé • Préparation à l’entretien',
      '<div class="hero"><div class="hero-label">UI_PLAYWRIGHT_BDD</div><p>Des tests exécutables.<br>Des preuves observables.<br>Une assistance IA contrôlée.</p></div>'
      + grid([
          ('Socle de test', 'Cucumber interprète les scénarios Gherkin ; Playwright pilote le navigateur.', 'Les assertions établissent le résultat du test.'),
          ('Assistance IA', 'Les agents aident à préparer les tests, analyser les échecs et formuler des recommandations.', 'Le modèle peut proposer une réponse incorrecte.'),
          ('LLM harness', 'Infrastructure qui encadre le modèle : contexte, appels, contrôles et suivi.', 'Ce terme regroupe plusieurs modules existants.')
      ])
      + note('Périmètre : <b>ui_playwright_bdd uniquement</b>. État décrit d’après le code et les documents locaux consultés le 29 septembre 2026. La présence du code ne prouve pas la disponibilité actuelle des services externes.'))

slide('02 / LA VUE D’ENSEMBLE', 'Deux chaînes complémentaires',
      'La chaîne de tests produit des résultats. La chaîne IA aide à les préparer et à les interpréter.',
      '<h2>Chaîne fonctionnelle</h2>' + flow([
          ('Exigences', 'Jira et critères d’acceptation'), ('Features', 'Scénarios Gherkin revus'),
          ('Steps & pages', 'Code TypeScript et Page Objects'), ('Exécution', 'Cucumber + Playwright'),
          ('Preuves', 'Résultats, traces et Allure')])
      + '<h2>Chaîne d’assistance</h2>' + flow([
          ('Agents QA', 'Génération, analyse, recommandation'), ('LLM harness', 'Prépare et contrôle les échanges'),
          ('Groq / Ollama', 'Fournisseur cloud ou moteur local'), ('Vérificateurs', 'Contrôles des sorties et références'),
          ('Revue QA', 'Décision fondée sur les preuves')])
      + grid([
          ('Avant les tests', 'Planning examine la couverture. Codegen propose des scénarios et du code.', 'La revue métier reste nécessaire.'),
          ('Après les tests', 'Quality et Bug exploitent les échecs ; Advisor formule une recommandation.', 'Une hypothèse de cause doit être vérifiée.'),
          ('Pilotage', 'Pipeline ordonne les commandes et suit leurs états.', 'Tous les modules ne s’exécutent pas à chaque commande.')
      ]) + note('Le diagramme exprime des responsabilités. Il ne signifie pas qu’une revue humaine ou qu’un appel IA est automatiquement déclenché à chaque flèche.'))

slide('03 / LE SOCLE BDD', 'Du langage métier à la preuve',
      'Exemple pédagogique : vérifier qu’une tâche créée est visible dans la liste.',
      grid([
          ('Feature / scénario', 'Un fichier .feature décrit un comportement attendu avec Given, When, Then.', 'Exemple : une tâche saisie doit apparaître.', 'src/features/'),
          ('Step definition', 'Une fonction TypeScript associée à une phrase Gherkin.', 'Elle orchestre les actions et vérifications.', 'src/steps/'),
          ('Page Object', 'Classe qui regroupe les interactions avec une page.', 'Un changement de sélecteur est centralisé.', 'src/pages/'),
          ('World', 'Objet contenant l’état d’un scénario : page, contexte navigateur, données.', 'Il évite le partage accidentel d’état entre scénarios.', 'src/core/world.ts'),
          ('Hooks', 'Fonctions Before et After exécutées autour des scénarios.', 'Préparation, preuves, diagnostic et nettoyage.', 'src/hooks/hooks.ts'),
          ('Assertion', 'Comparaison entre résultat observé et résultat attendu.', 'Exemple : vérifier qu’un élément est visible.', 'Playwright expect')
      ]) + '<div class="example"><b>À expliquer :</b> « Cucumber trouve la fonction associée à la phrase. Le step utilise un Page Object. Playwright agit sur le navigateur, puis une assertion vérifie le résultat. »</div>'
      + note('<b>Distinction essentielle :</b> le runner de ce projet UI est <b>CucumberJS</b>. Playwright est utilisé pour l’automatisation et les assertions. Ne pas présenter ce projet comme une suite pilotée par le runner Playwright Test.'))

slide('04 / LA CARTE DU CODE', 'Où retrouver chaque responsabilité ?',
      'Chemins relatifs au dossier ui_playwright_bdd ; seules les branches utiles à l’architecture sont affichées.',
      '<div class="two"><pre class="tree">ui_playwright_bdd/\n├── cucumber.js\n├── package.json\n├── src/\n│   ├── features/\n│   ├── steps/\n│   ├── pages/\n│   ├── core/world.ts\n│   ├── hooks/hooks.ts\n│   ├── api/QACartApiClient.ts\n│   ├── support/\n│   ├── config/\n│   └── utils/\n├── scripts/agents/\n│   ├── *-agent.js\n│   ├── llm.js\n│   ├── jira-fetcher.js\n│   └── shared/\n├── prompts/\n├── qa-knowledge/\n├── evaluation/deepeval/\n├── config/\n└── docs/</pre><div>'
      + card('Tests et préparation API', 'Les steps et les pages portent le comportement des tests ; le client API prépare des données.', 'L’application testée est QACart Todo.')
      + card('Configuration', 'cucumber.js définit les profils, tags, fichiers chargés et reporters.', 'Les variables d’environnement choisissent URL, navigateur et fournisseurs.')
      + card('Artefacts d’exécution', 'allure-runs/, test-results/, logs/ et memory/ accueillent les résultats et traces selon les commandes.', 'Ces données sont distinctes du code source.')
      + '</div></div>')

agents = [
 ('Pipeline', 'Orchestrateur : lance les étapes et collecte leurs états.', 'Pas de LLM propre.', 'pipeline-agent.js'),
 ('Planning', 'Analyse couverture, exigences et cas manquants.', 'Suggestions IA selon la commande.', 'planning-agent.js'),
 ('Codegen', 'Propose Gherkin, steps et Page Objects.', 'Le code reste à contrôler.', 'codegen-agent.js'),
 ('Runner', 'Exécute Cucumber et exploite les résultats.', 'Résumé IA optionnel.', 'runner-agent.js'),
 ('Allure', 'Génère et consulte le rapport de tests.', 'Reporting technique.', 'allure-agent.js'),
 ('Quality', 'Triage, causes possibles et cohérence.', 'Analyse appuyée sur les preuves.', 'quality-agent.js'),
 ('Bug', 'Analyse les défauts et propose des corrections.', 'Réparation : mode distinct.', 'bug-agent.js'),
 ('Advisor', 'Recommande GO/NO-GO et applique le gate.', 'Dépend des preuves et contrôles.', 'advisor-agent.js'),
 ('Reporting', 'Produit les dashboards et intégrations.', 'Envois externes selon la commande.', 'reporting-agent.js'),
 ('Observability', 'Suit traces, métriques et coûts.', 'Calculs principalement déterministes.', 'observability-agent.js'),
 ('CI', 'Interagit avec Git et GitHub Actions.', 'IA pour certains textes.', 'ci-agent.js'),
 ('Governance', 'Expose audits et validations de décisions.', 'Contrôles selon la politique.', 'governance-agent.js'),
 ('QA Workflow', 'Suit les étapes de revue et leurs statuts.', 'Module de pilotage distinct.', 'qa-workflow-agent.js')]
slide('05 / LES AGENTS', '13 points d’entrée, des rôles différents',
      'Un module nommé « agent » n’utilise pas nécessairement un LLM pour chaque opération.',
      '<div class="compact">' + grid(agents, 4) + '</div>'
      + note('À retenir : <b>l’agent porte la tâche QA</b> ; <b>le harness fournit l’infrastructure IA</b> ; <b>le modèle produit une réponse</b>.'))

slide('06 / LE LLM HARNESS', 'L’environnement autour du modèle',
      'Harness : ensemble des mécanismes qui rendent l’usage du LLM contrôlable et observable.',
      flow([('Contexte', 'Instructions et sources pertinentes'), ('Appel', 'Interface commune llm.js'), ('Transport', 'Gateway, quotas et fournisseur'), ('Sortie', 'Contrôles selon l’opération')])
      + grid([
          ('Instructions', 'Les prompts précisent le rôle, la tâche et le format attendu.', 'prompt-store.js + prompts/'),
          ('Contexte', 'Le RAG recherche des extraits ; la mémoire conserve des épisodes.', 'hybrid-rag.js + memory-store.js'),
          ('Interface LLM', 'llm.js uniformise l’accès à Groq et Ollama.', 'Texte, JSON structuré, analyses et comparaisons.'),
          ('Résilience', 'Cache et circuit breaker limitent les appels inutiles ou les échecs répétés.', 'circuit-breaker.js'),
          ('Vérification', 'Les sorties sont contrôlées selon leur nature et leur utilisation.', 'agent-verifier.js, generated-code.js, source-verification.js'),
          ('Observabilité', 'Trace les appels et mesure durées, consommation et coûts estimés.', 'tracer.js + task-metrics.js')
      ]) + note('Il n’existe pas un fichier unique « llm-harness ». Cette frontière regroupe plusieurs modules. Les vérificateurs sont appelés par les agents/pipeline concernés, pas systématiquement après chaque appel LLM.'))

slide('07 / LE RAG', 'Rechercher avant de répondre',
      'RAG = Retrieval-Augmented Generation : génération enrichie par des informations retrouvées dans un corpus.',
      flow([('Sources', 'Connaissances, specs et features'), ('Chunks', 'Extraits découpés par lignes'), ('Recherche', 'BM25 et embeddings'), ('Fusion RRF', 'Combine les classements'), ('Reranking', 'Reclassement si activé'), ('Top-k + budget', 'Sélection finale du contexte')])
      + grid([
          ('BM25', 'Recherche lexicale : valorise les correspondances de mots.', 'Utile pour un nom de test ou une erreur exacte.'),
          ('Embedding', 'Vecteur numérique représentant le contenu d’un extrait.', 'La similarité aide à retrouver un sens proche ; embeddings via Ollama.'),
          ('RRF', 'Reciprocal Rank Fusion : combine les positions de plusieurs classements.', 'Associe recherche lexicale et sémantique.'),
          ('Reranking', 'Un modèle réévalue la pertinence des extraits candidats.', 'Optionnel ; peut envoyer les extraits à Groq.'),
          ('Top-k', 'Nombre maximal d’extraits à retenir dans le contexte.', '4 par défaut ; le budget peut réduire le nombre réellement transmis.'),
          ('Provenance', 'Chemin, lignes et empreinte permettent de retrouver les sources.', 'Les épisodes IA restent non vérifiés ; les vecteurs sont stockés localement.')
      ]) + note('Le RAG améliore l’accès au contexte ; il ne garantit pas l’exactitude. La documentation du module exclut notamment les .env et les logs bruts de l’index.'))

slide('08 / CHUNKS', 'Un document devient des extraits traçables',
      'Chunk = fragment de texte utilisé comme unité de recherche. Ce n’est ni un token, ni un embedding.',
      flow([('Document source', 'Texte lu depuis le corpus autorisé'), ('Découpage', 'Regroupe les lignes entières'), ('Chunks', 'Fragments de 1 800 caractères maximum'), ('Index', 'Termes BM25 et vecteurs associés')])
      + grid([
          ('Pourquoi découper ?', 'Retrouver un passage pertinent sans transmettre un document complet au modèle.', 'Un même document peut fournir plusieurs chunks.'),
          ('Comment dans ce code ?', 'chunkFile() accumule les lignes jusqu’à la limite de 1 800 caractères.', 'Pas de chevauchement explicite. Une ligne trop longue est omise et signalée.', 'scripts/agents/shared/rag.js'),
          ('Que conserve un chunk ?', 'Texte, identifiant, chemin, lignes de début et de fin, empreinte de la source et type.', 'Ces métadonnées permettent de retrouver et vérifier l’extrait.'),
          ('Chunk et embedding', 'Le chunk est du texte lisible ; l’embedding est sa représentation numérique.', 'Le vecteur aide à chercher. Le texte retenu constitue le contexte du LLM.'),
          ('Taille et compromis', 'Un fragment court cible mieux un passage, mais peut perdre du contexte.', 'Un fragment long contient plus de contexte, mais peut ajouter du bruit.'),
          ('Cas de la mémoire IA', 'Le découpage traite séparément les lignes d’épisodes sélectionnés.', 'L’historique reste identifié comme non vérifié, même après indexation.')
      ]) + note('À dire au client : « Je découpe les sources en passages identifiables. Le RAG retrouve ces passages et conserve leur provenance pour permettre la vérification. »'))

slide('09 / TOP-K', 'Combien de chunks envoyer au modèle ?',
      'Top-k = plafond du nombre d’extraits sélectionnés après classement. Le budget de contexte s’applique aussi.',
      flow([('Chunks candidats', 'Résultats BM25 et sémantiques'), ('Classement', 'Fusion RRF puis reranking si activé'), ('Sélection', 'Au plus k chunks qui tiennent dans le budget'), ('LLM', 'Reçoit les textes et leurs références')])
      + '<div class="two"><div><h2>Exemple fictif : k = 4</h2><div class="ranking">'
      + ''.join(f'<div class="rank {"chosen" if i <= 4 else "rejected"}"><b>C{i}</b><span>{escape(label)}</span><strong>{"RETENU" if i <= 4 else "NON RETENU"}</strong></div>' for i,label in enumerate(['Règle métier de connexion', 'Scénario de connexion existant', 'Précondition du compte de test', 'Note QA sur le message attendu', 'Ancienne analyse peu pertinente', 'Règle de suppression sans rapport'],1))
      + '</div><p class="role">Illustration uniquement : ces six extraits ne proviennent pas d’une recherche exécutée. On suppose que les quatre premiers tiennent dans le budget.</p></div>'
      + '<div>' + card('Valeurs par défaut du code', 'topK = 4 et maxChars = 4 500.', 'Le coût utilisé est la longueur du chunk sérialisé en JSON, métadonnées comprises. Ce ne sont pas 4 500 tokens.', 'rag.js : selectHits() ; hybrid-rag.js : search()')
      + card('Pourquoi moins de quatre ?', 'Le corpus peut être insuffisant ou le budget ne pas permettre de retenir quatre chunks.', 'Un extrait qui dépasse le budget restant est sauté ; la sélection peut en retenir un suivant plus petit.')
      + card('Ne pas confondre', 'k est le nombre maximal de chunks, pas le nombre de documents ou de réponses du LLM.', 'La limite de candidats du reranker est une étape distincte du top-k final.')
      + '</div></div>'
      + note('À dire au client : « Je classe les chunks, puis je sélectionne au maximum quatre extraits dans le budget prévu. Augmenter k peut enrichir le contexte, mais aussi ajouter du bruit et de la consommation. »'))

slide('08 / CONTRÔLES ET GOUVERNANCE', 'Trois questions à séparer',
      'Peut-on envoyer la requête ? Peut-on utiliser la réponse ? Peut-on prendre la décision ?',
      grid([
          ('1 · Gateway IA', 'Contrôle les destinations, modèles, secrets reconnus, tailles, délais et quotas.', 'ai-gateway.js + config/ai-gateway.json'),
          ('2 · Vérificateurs', 'Contrôlent format, code, références et contraintes selon la sortie.', 'Un JSON valide ne démontre pas une conclusion métier.'),
          ('3 · Gouvernance', 'Suit les validations et les décisions nécessitant une intervention humaine.', 'governance-agent.js + ai-governance.js')
      ]) + '<h2>Le workflow de revue disponible</h2>'
      + flow([('Gherkin', 'Valider le comportement décrit'), ('Script', 'Relire l’implémentation'), ('Exécution', 'Contrôler les preuves'), ('Analyse', 'Examiner les conclusions'), ('Décision', 'Approuver ou bloquer')])
      + note('Le module qa-workflow existe séparément. Il ne faut pas affirmer que toutes ces revues sont automatiquement imposées par chaque commande du pipeline. Le gateway est applicatif : ce n’est ni un pare-feu ni une garantie contre toutes les fuites ou injections.'))

pipeline = [
 ('01 · Planning', 'Analyse de couverture.'), ('02 · Codegen', 'Génération des spécifications.'),
 ('03 · Runner', 'Exécution des tests.'), ('04 · Allure', 'Production du rapport.'),
 ('05 · Quality', 'Triage et analyse complète.'), ('06 · Bug', 'Analyse des échecs.'),
 ('07 · Reporting', 'Dashboard KPI.'), ('08 · Jira', 'Synchronisation si --sync-jira.'),
 ('09 · Advisor', 'Recommandation de livraison.'), ('10 · Observability', 'Métriques du traitement.'),
 ('11 · CI', 'Consultation de l’état GitHub.'), ('12 · Gate', 'Contrôle final de validation.')]
slide('09 / ORCHESTRATION', 'Ce que fait réellement le mode full',
      'Une séquence définie dans pipeline-agent.js ; ce n’est pas un agent qui choisit librement toutes ses actions.',
      '<div class="pipeline">' + grid(pipeline, 4) + '</div>'
      + grid([
          ('quick', 'Smoke → Allure → triage → dashboard → gate.', 'Un parcours plus court.'),
          ('report', 'Exploite les résultats existants pour produire des rapports.', 'Ne valide pas une nouvelle exécution.'),
          ('Limite du mode full', 'Il appelle codegen spec et bug analyze.', 'Il ne génère pas systématiquement tous les scripts et ne répare pas automatiquement les tests.')
      ]) + note('Le contrôle final tient compte de l’exécution complète, des résultats du run et des étapes obligatoires. Une recommandation IA ne remplace pas ces conditions.'))

slide('10 / PREUVES ET ÉVALUATION', 'Mesurer les tests et mesurer l’IA',
      'Deux objets différents : le comportement de l’application et la qualité des réponses des modèles.',
      grid([
          ('Allure', 'Rapport de tests avec statuts et pièces jointes.', 'Un rapport peut être partiel ; sa présence ne signifie pas réussite.'),
          ('Traces et captures', 'Éléments pour reconstituer un échec navigateur.', 'Les hooks collectent les informations selon les conditions du run.'),
          ('Manifeste de run', 'Identifie l’exécution et conserve sa complétude et son code de sortie.', 'Évite d’utiliser de vieux résultats comme preuve nouvelle.'),
          ('Métriques IA', 'Durée, consommation et coûts estimés des appels.', 'Un tarif inconnu ne doit pas devenir un coût nul.'),
          ('DeepEval', 'Évalue les réponses IA sur un jeu de cas et leur contexte.', 'Lancé à la demande, dans un environnement Python séparé.'),
          ('Fidélité / pertinence', 'Fidélité : appui sur le contexte. Pertinence : réponse à la question.', 'Ces scores ne prouvent pas la conformité de l’application.')
      ]) + note('DeepEval ne juge pas automatiquement chaque réponse de chaque agent. Ses résultats dépendent du jeu de référence, du contexte fourni et du juge.'))

slide('11 / CI ET COMMANDES', 'Deux chemins d’exécution',
      'Le workflow GitHub existant exécute les tests ; le pipeline d’agents est une commande distincte.',
      '<div class="two"><div><h2>GitHub Actions</h2>'
      + flow([('Installation', 'Node, npm ci, Chromium'), ('Tests', 'Cucumber : @regression hors @wip'), ('Artefacts', 'Rapport Allure et preuves')])
      + '<p>Déclenchements présents : push, pull request, lancement manuel et planification. Le fichier de référence est <code>.github/workflows/ci-playwright.yml</code>, à la racine du dépôt.</p></div>'
      + '<div><h2>Commandes à expliquer</h2><pre class="commands"># Tests UI\nnpm run test:headless\n\n# Pipeline court / complet\nnpm run agent:pipeline:quick\nnpm run agent:pipeline:full\n\n# Recherche et métriques\nnpm run rag:status\nnpm run metrics:report\n\n# Évaluation IA à la demande\nnpm run eval:deepeval</pre></div></div>'
      + note('Ces commandes sont des repères de préparation, pas la preuve qu’elles ont été exécutées ici. Certaines nécessitent les accès Jira, au fournisseur LLM et à l’application. Le workflow CI consulté ne lance pas l’intégralité des agents IA.'))

questions = [
 ('Pourquoi Cucumber et Playwright ?', 'Cucumber relie les scénarios métier aux steps. Playwright exécute les actions navigateur et fournit les assertions.'),
 ('Agent, modèle et harness : quelle différence ?', 'L’agent porte une tâche QA. Le modèle génère une réponse. Le harness prépare, encadre et observe l’utilisation du modèle.'),
 ('Comment vérifiez-vous le code généré ?', 'Par des contrôles de syntaxe, de types selon le chemin utilisé, une revue métier et une exécution. Aucun de ces contrôles seul ne suffit.'),
 ('Le RAG évite-t-il les hallucinations ?', 'Il fournit des sources pertinentes et traçables, mais une réponse peut encore être fausse. Je vérifie ses références et ses conclusions.'),
 ('Qui décide du GO / NO-GO ?', 'Advisor formule une recommandation et un gate. La décision doit respecter les preuves, les blocages techniques et la gouvernance humaine applicable.'),
 ('Le framework répare-t-il tout seul ?', 'Un mode de réparation existe, mais le pipeline full consulté lance bug analyze. Je ne promets pas une réparation automatique de tous les échecs.'),
 ('Que se passe-t-il si le LLM est indisponible ?', 'Les mécanismes de résilience et les erreurs sont gérés selon le chemin d’appel. Le Runner peut lancer Cucumber sans attendre un résumé IA.'),
 ('Tout est-il branché à la CI ?', 'La CI UI lance Cucumber/Playwright et Allure. Le pipeline complet des agents constitue actuellement un autre chemin.')]
slide('12 / ENTRAÎNEMENT', 'Les questions probables du client',
      'Dans la version HTML, cliquez sur une question pour révéler la réponse. Dans le PDF, toutes les réponses sont visibles.',
      '<div class="questions">' + ''.join(f'<details><summary>{escape(q)}</summary><p>{escape(a)}</p></details>' for q,a in questions) + '</div>'
      + note('Si un détail vous échappe : « Je préfère vérifier le chemin d’exécution dans le code. Je peux vous montrer le module qui le gère. »'))

slide('13 / VOTRE PRÉSENTATION', 'Un pitch de 60 secondes',
      'L’objectif : expliquer le parcours d’un test et situer l’IA avec précision.',
      '<blockquote>« Mon framework UI repose sur Cucumber, Playwright et TypeScript. Les features décrivent les comportements métier ; les steps s’appuient sur des Page Objects et un contexte isolé par scénario. Les assertions et les preuves Allure permettent d’analyser le résultat.<br><br>J’ai ajouté une couche d’agents pour la préparation, l’analyse des échecs et les recommandations. Leur LLM harness rassemble le contexte documentaire, les appels aux modèles, les contrôles, la résilience et les métriques.<br><br>Je distingue toujours une proposition IA d’un résultat démontré : je vérifie les sources, le code et les tests, et je conserve les validations QA nécessaires. »</blockquote>'
      + grid([
          ('À montrer en premier', 'Une feature, son step, son Page Object et l’assertion associée.', 'Expliquez ce parcours avant les agents.'),
          ('À montrer ensuite', 'Un rapport avec les preuves, puis le rôle du harness.', 'Partez d’un exemple concret d’échec.'),
          ('À éviter', 'Promettre une IA autonome et infaillible ou une couverture totale.', 'Distinguez code présent, configuration et exécution prouvée.')
      ]))

sources = [
 ('BDD', 'cucumber.js ; src/core/world.ts ; src/hooks/hooks.ts ; src/pages/BasePage.ts'),
 ('Orchestration', 'scripts/agents/pipeline-agent.js ; shared/pipeline-runtime.js ; docs/pipeline-execution.md'),
 ('LLM et harness', 'scripts/agents/llm.js ; scripts/agents/shared/ ; prompts/'),
 ('RAG', 'docs/rag.md ; scripts/agents/shared/hybrid-rag.js ; reranker.js'),
 ('Gateway', 'docs/ai-gateway.md ; config/ai-gateway.json ; scripts/agents/shared/ai-gateway.js'),
 ('Vérification', 'docs/agent-verification.md ; scripts/agents/shared/agent-verifier.js'),
 ('Gouvernance', 'scripts/agents/governance-agent.js ; qa-workflow-agent.js ; shared/qa-workflow-engine.js'),
 ('Évaluation', 'docs/deepeval.md ; evaluation/deepeval/ ; scripts/deepeval.js'),
 ('CI', '.github/workflows/ci-playwright.yml à la racine du dépôt QA_Plateforme')]
slide('14 / SOURCES ET LEXIQUE', 'Retrouver, vérifier, expliquer',
      'Le code des commandes prévaut sur les anciens résumés du README lorsque les descriptions diffèrent.',
      '<div class="two"><div class="sources">' + ''.join(f'<p><b>{escape(t)}</b><br><code>{escape(s)}</code></p>' for t,s in sources) + '</div>'
      + '<div>' + grid([
          ('Oracle', 'Résultat de référence permettant de juger un test.'),
          ('Flaky', 'Test dont le résultat varie sans changement fonctionnel pertinent.'),
          ('RCA', 'Root Cause Analysis : recherche de la cause d’un échec.'),
          ('Quality gate', 'Conditions à satisfaire pour autoriser la suite du processus.'),
          ('Circuit breaker', 'Mécanisme de protection face aux échecs répétés d’un service.'),
          ('Token', 'Unité utilisée par un modèle pour traiter et produire du texte.')
      ], 2) + '</div></div>'
      + note('Support pédagogique construit à partir du dépôt local. Aucun appel Jira, fournisseur LLM ou pipeline de production n’a été nécessaire à sa création. Le PDF est une version fixe ; l’animation et les contrôles sont dans le HTML compagnon.'))

css = r'''
:root{--navy:#12243d;--teal:#087f8c;--cyan:#e9f7f6;--orange:#b55b15;--ink:#26354a;--muted:#596b7d;--line:#dce4ed}
*{box-sizing:border-box}body{margin:0;background:#dce5ed;color:var(--ink);font-family:Arial,sans-serif;font-size:15px;line-height:1.42}
.slide{width:297mm;height:210mm;background:#fff;margin:24px auto;position:relative;padding:34px 44px 47px;overflow:hidden;box-shadow:0 10px 36px #172b4d22;border-top:7px solid var(--teal)}
.eyebrow{font-size:12px;letter-spacing:2px;color:var(--teal);font-weight:bold;margin:0 0 9px}h1{font-size:34px;line-height:1.1;color:var(--navy);margin:0 0 10px}h2{font-size:18px;margin:18px 0 10px;color:var(--navy)}.intro{color:var(--muted);font-size:16px;margin:0 0 22px;max-width:970px}
.grid{display:grid;gap:13px;margin:15px 0}.cols-3{grid-template-columns:repeat(3,1fr)}.cols-4{grid-template-columns:repeat(4,1fr)}.cols-2{grid-template-columns:repeat(2,1fr)}.card{padding:15px 17px;border:1px solid var(--line);border-radius:11px;background:#f8fafc;transition:background .3s,box-shadow .3s,transform .3s;cursor:pointer;min-width:0}.card h3{font-size:17px;line-height:1.2;color:var(--navy);margin:0 0 8px}.card p{margin:0 0 8px}.card p:last-child{margin-bottom:0}.role{font-size:13px;color:var(--muted)}code{font-family:Consolas,monospace;font-size:12px;overflow-wrap:anywhere;color:#28516a}.card code{display:block;margin-top:7px;font-size:11px}
.note{border-left:4px solid var(--teal);background:var(--cyan);padding:12px 16px;margin-top:17px;font-size:14px;border-radius:0 8px 8px 0}.hero{background:var(--navy);padding:22px 30px;color:white;border-radius:14px;margin:20px 0}.hero p{font-size:32px;line-height:1.18;font-weight:bold;margin:12px 0}.hero-label{font-size:12px;letter-spacing:3px;color:#8fe2df}.two{display:grid;grid-template-columns:1fr 1fr;gap:25px}.two .card{margin-bottom:14px}.tree{background:var(--navy);color:#e5f2ff;border-radius:12px;font-size:14px;line-height:1.35;padding:20px;margin:0}.commands{background:#eef3f7;padding:18px;border-radius:10px;font-size:14px;line-height:1.5}.example{padding:16px;background:#fff7ed;border-radius:10px;margin-top:20px}
.flow{display:flex;gap:17px;margin:14px 0 23px}.node{position:relative;flex:1;min-width:0;background:var(--navy);color:white;border-radius:10px;padding:14px 12px;cursor:pointer;transition:transform .3s,background .3s}.node b{font-size:15px;display:block;margin-bottom:7px}.node span{font-size:12px;line-height:1.3;display:block;color:#d6e7f5}.node:not(:last-child):after{content:'→';position:absolute;right:-16px;top:35%;color:var(--teal);font-weight:bold}.compact .card{padding:12px}.compact .card h3{font-size:15px}.compact .card p{font-size:12px;margin-bottom:5px}.compact .card .role{font-size:11px}.compact .grid{gap:10px}.pipeline .card{padding:12px}.pipeline .card h3{font-size:15px}.pipeline .card p{font-size:13px}
.questions{display:grid;grid-template-columns:1fr 1fr;gap:12px}.questions details{border:1px solid var(--line);border-radius:10px;background:#f8fafc;padding:13px 16px}.questions summary{font-size:15px;font-weight:bold;color:var(--navy);cursor:pointer}.questions p{font-size:14px;margin:9px 0 0}blockquote{font-size:21px;line-height:1.5;background:#eef6fa;border-left:5px solid var(--teal);border-radius:0 12px 12px 0;margin:20px 0;padding:22px 28px}.sources p{margin:0 0 12px;font-size:13px}.sources code{font-size:11px}
.ranking{display:grid;gap:8px}.rank{display:grid;grid-template-columns:35px 1fr 82px;gap:9px;align-items:center;border:1px solid var(--line);border-radius:8px;padding:11px;font-size:13px}.rank strong{font-size:10px;text-align:right}.chosen{background:#e9f7f6;border-left:4px solid var(--teal)}.rejected{background:#f2f3f5;color:var(--muted)}
#slide-9 .two .card{padding:10px 13px;margin-bottom:9px}#slide-9 .card h3{font-size:16px;margin-bottom:5px}#slide-9 .card p{font-size:13px;margin-bottom:5px}#slide-9 .card code{font-size:10px;margin-top:4px}#slide-9 .two h2{margin-top:0}#slide-9 .note{margin-top:10px;font-size:13px}
footer{position:absolute;bottom:15px;left:44px;right:44px;border-top:1px solid var(--line);padding-top:9px;color:var(--muted);font-size:11px;display:flex;justify-content:space-between}
.toolbar{position:sticky;top:0;z-index:10;background:#12243df2;color:white;display:flex;align-items:center;gap:10px;padding:12px 22px;box-shadow:0 3px 10px #0002}.toolbar button,.toolbar select{background:#fff;color:var(--navy);border:0;border-radius:6px;padding:9px 13px;cursor:pointer;font:inherit;font-size:13px}.toolbar .brand{margin-right:auto;font-weight:bold}.toolbar button:focus-visible,.card:focus-visible,.node:focus-visible,summary:focus-visible{outline:3px solid #e79842;outline-offset:3px}.narration{position:fixed;bottom:0;left:0;right:0;background:var(--navy);color:#fff;z-index:10;padding:13px 24px;font-size:15px;min-height:53px}.interactive body{padding-bottom:70px}.interactive .slide{display:none;animation:appear .3s ease}.interactive .slide.current{display:block}.active-card{box-shadow:0 0 0 3px var(--teal);background:#e9f7f6;transform:translateY(-2px)}.node.active-card{background:var(--teal);box-shadow:0 0 0 3px #70c7cb}.progress{height:3px;background:#1bb4b0;position:fixed;top:0;left:0;z-index:30;transition:width .3s}.hint{font-size:11px;color:#b8d4e5}
@keyframes appear{from{opacity:.2;transform:translateY(8px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media print{@page{size:A4 landscape;margin:0}body{background:white;padding:0!important}.toolbar,.narration,.progress{display:none!important}.slide,.interactive .slide{display:block!important;margin:0;box-shadow:none;break-after:page;page-break-after:always;animation:none!important;transform:none!important}.slide:last-of-type{break-after:auto;page-break-after:auto}.active-card{box-shadow:none;transform:none;background:#f8fafc}.node.active-card{background:var(--navy)}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}details>p{display:block!important}details::details-content{content-visibility:visible!important}summary{list-style:none}}
'''

sections = []
for i, (kicker, title, intro, body) in enumerate(slides, 1):
    kicker = f'{i:02d} / ' + kicker.split(' / ', 1)[1]
    sections.append(f'<section class="slide" id="slide-{i}" aria-label="{escape(title, quote=True)}"><div class="eyebrow">{escape(kicker)}</div><h1>{escape(title)}</h1><p class="intro">{escape(intro)}</p>{body}<footer><span>UI Playwright BDD · Support de préparation · 29/09/2026</span><span>{i:02d} / {len(slides):02d}</span></footer></section>')

script = r'''
const pages=[...document.querySelectorAll('.slide')];let current=0,timer=null,step=-1;
const select=document.querySelector('#pages'),status=document.querySelector('#status'),play=document.querySelector('#play');
pages.forEach((p,i)=>{const option=document.createElement('option');option.value=i;option.textContent=`${i+1}. ${p.querySelector('h1').textContent}`;select.append(option)});
document.documentElement.classList.add('interactive');
function clearCards(){document.querySelectorAll('.active-card').forEach(e=>e.classList.remove('active-card'))}
function show(i){current=Math.max(0,Math.min(pages.length-1,i));pages.forEach((p,j)=>p.classList.toggle('current',j===current));select.value=current;step=-1;clearCards();status.textContent='Cliquez sur un bloc pour son explication, ou lancez le parcours animé.';document.querySelector('.progress').style.width=((current+1)/pages.length*100)+'%';document.querySelector('#prev').disabled=current===0;document.querySelector('#next').disabled=current===pages.length-1}
function explain(e){clearCards();e.classList.add('active-card');status.textContent=e.dataset.note}
function stop(){clearInterval(timer);timer=null;play.textContent='▶ Parcours animé';play.setAttribute('aria-pressed','false')}
function tick(){const cards=[...pages[current].querySelectorAll('[data-note]')];step++;if(step>=cards.length){if(current===pages.length-1){stop();return}show(current+1);return}explain(cards[step])}
document.querySelector('#prev').onclick=()=>{stop();show(current-1)};document.querySelector('#next').onclick=()=>{stop();show(current+1)};
select.onchange=()=>{stop();show(Number(select.value))};play.onclick=()=>{if(timer){stop()}else{play.textContent='⏸ Pause';play.setAttribute('aria-pressed','true');tick();timer=setInterval(tick,5500)}};
document.querySelectorAll('[data-note]').forEach(e=>{e.onclick=()=>explain(e);e.onkeydown=event=>{if(event.key==='Enter'){explain(e)}}});
document.querySelector('#answers').onclick=()=>{const details=[...document.querySelectorAll('details')];const open=details.some(d=>!d.open);details.forEach(d=>d.open=open)};
document.addEventListener('keydown',e=>{if(['SELECT','INPUT','BUTTON','SUMMARY'].includes(e.target.tagName))return;if(e.key==='ArrowRight'){stop();show(current+1)}if(e.key==='ArrowLeft'){stop();show(current-1)}});
document.querySelector('#print').onclick=()=>window.print();
window.addEventListener('beforeprint',()=>{stop();document.querySelectorAll('details').forEach(d=>d.open=true)});
show(0);
'''

html = '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Architecture Playwright BDD & IA — Préparation</title><style>' + css + '</style></head><body><div class="progress"></div><nav class="toolbar" aria-label="Navigation du support"><span class="brand">Playwright BDD × IA</span><button id="prev" aria-label="Page précédente">←</button><select id="pages" aria-label="Choisir une page"></select><button id="next" aria-label="Page suivante">→</button><button id="play" aria-pressed="false">▶ Parcours animé</button><button id="answers">Réponses</button><button id="print">Imprimer / PDF</button></nav>' + ''.join(sections) + '<div class="narration" id="status" role="status" aria-live="polite"></div><script>' + script + '</script></body></html>'
target = ROOT / 'architecture-playwright-bdd-ia.html'
target.write_text(html, encoding='utf-8')
(ROOT / 'manifest.json').write_text(json.dumps({'pages': len(slides), 'titles': [s[1] for s in slides], 'scope': 'ui_playwright_bdd', 'source_date': '2026-09-29'}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'HTML genere : {target} ({len(slides)} pages)')
