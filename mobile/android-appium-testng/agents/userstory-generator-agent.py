# ============================================================
# User Story Generator Agent — SauceLabs My Demo App
# ============================================================
# Génère les user stories (format BDD Gherkin) à partir du spec doc.
# Chaque user story est structurée pour être importée dans Jira.
#
# Usage:
#   python agents/userstory-generator-agent.py generate   → génère toutes les US
#   python agents/userstory-generator-agent.py dump        → affiche les US existantes
#   python agents/userstory-generator-agent.py preview     → affiche un résumé
# ============================================================

import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

FEATURES_INPUT = [
    {
        "id": "F-001",
        "name": "Login",
        "scenarios": [
            "Connexion avec identifiants valides",
            "Connexion avec mot de passe incorrect",
            "Connexion avec compte verrouillé",
            "Connexion avec champs vides",
            "Déconnexion depuis le menu"
        ]
    },
    {
        "id": "F-002",
        "name": "Products Catalog",
        "scenarios": [
            "Affichage de la liste des produits après connexion",
            "Tri des produits par nom A-Z",
            "Tri des produits par prix croissant",
            "Navigation vers le détail d'un produit"
        ]
    },
    {
        "id": "F-003",
        "name": "Product Detail",
        "scenarios": [
            "Affichage des détails du produit (nom, prix, description, image)",
            "Ajout d'un produit au panier depuis le détail",
            "Modification de la quantité avant ajout au panier"
        ]
    },
    {
        "id": "F-004",
        "name": "Shopping Cart",
        "scenarios": [
            "Ajout d'un produit au panier depuis le catalogue",
            "Suppression d'un article du panier",
            "Affichage du panier vide avec bouton Go Shopping",
            "Vérification du badge panier après ajout"
        ]
    },
    {
        "id": "F-005",
        "name": "Checkout Address",
        "scenarios": [
            "Remplissage valide du formulaire d'adresse",
            "Validation avec champs obligatoires vides",
            "Navigation vers l'étape paiement"
        ]
    },
    {
        "id": "F-006",
        "name": "Checkout Payment",
        "scenarios": [
            "Remplissage valide des informations de paiement",
            "Validation avec numéro de carte invalide",
            "Navigation vers la revue de commande"
        ]
    },
    {
        "id": "F-007",
        "name": "Checkout Review & Complete",
        "scenarios": [
            "Revue de la commande avant validation",
            "Passage de commande avec succès",
            "Affichage du message de confirmation"
        ]
    },
    {
        "id": "F-008",
        "name": "Navigation Menu",
        "scenarios": [
            "Ouverture du menu burger",
            "Navigation vers le catalogue depuis le menu",
            "Navigation vers le panier depuis le menu"
        ]
    }
]


def generate_stories_for_feature(feature: dict) -> list:
    schema = {
        "feature_id": "string",
        "feature_name": "string",
        "stories": [
            {
                "id": "US-001",
                "title": "string — titre court de la user story",
                "as_a": "string — rôle utilisateur",
                "i_want": "string — action souhaitée",
                "so_that": "string — bénéfice",
                "priority": "High | Medium | Low",
                "story_points": "integer 1-8",
                "labels": ["liste de labels pour Jira"],
                "gherkin": "string — scénario Gherkin complet (Given/When/Then)",
                "acceptance_criteria": ["liste de critères d'acceptation testables"]
            }
        ]
    }

    messages = [{
        "role": "user",
        "content": (
            f"Tu es un expert QA et Scrum Master. Génère des user stories professionnelles "
            f"pour la feature suivante d'une application de shopping mobile.\n\n"
            f"Feature : {feature['id']} — {feature['name']}\n"
            f"Scénarios à couvrir : {json.dumps(feature['scenarios'], ensure_ascii=False)}\n\n"
            f"Application : SauceLabs My Demo App (Android shopping demo)\n"
            f"Test user : bob@example.com / 10203040\n\n"
            f"Pour chaque scénario, génère une user story avec :\n"
            f"- Titre court et descriptif\n"
            f"- Format As a / I want / So that\n"
            f"- Priorité (High pour login/checkout, Medium pour catalog/cart, Low pour navigation)\n"
            f"- Story points réalistes (1-3 pour simple, 5-8 pour complexe)\n"
            f"- Scénario Gherkin complet (Given/When/Then) en anglais\n"
            f"- Labels : 'mobile', 'android', 'appium' + label spécifique à la feature\n"
            f"- 3-5 critères d'acceptation testables\n\n"
            f"Sois précis et orienté test automation Appium."
        )
    }]

    result = llm.chat_structured(messages, schema)
    return result.get("stories", [])


def cmd_generate() -> list:
    print(f"\n{W}USER STORY GENERATOR AGENT — SauceLabs My Demo App{E}\n")
    all_stories = []

    for i, feature in enumerate(FEATURES_INPUT, 1):
        print(f"  {C}[{i}/{len(FEATURES_INPUT)}]{E} Génération US pour {feature['id']} — {feature['name']}...", end=" ", flush=True)
        stories = generate_stories_for_feature(feature)
        for story in stories:
            story["feature_id"]   = feature["id"]
            story["feature_name"] = feature["name"]
            all_stories.append(story)
        print(f"{G}✓{E} ({len(stories)} stories)")

    os.makedirs(DOCS_DIR, exist_ok=True)
    out_path = os.path.join(DOCS_DIR, "user-stories-mydemoapp.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_stories, f, ensure_ascii=False, indent=2)

    _save_stories_markdown(all_stories)

    print(f"\n{G}✅ {len(all_stories)} user stories générées{E}")
    print(f"   JSON     : {out_path}")
    print(f"   Markdown : {os.path.join(DOCS_DIR, 'user-stories-mydemoapp.md')}")

    _print_summary(all_stories)
    return all_stories


def _save_stories_markdown(stories: list):
    lines = [
        "# SauceLabs My Demo App — User Stories",
        "",
        "**Projet** : SauceLabs My Demo App (MDA)  ",
        "**Date** : 2026-06-12  ",
        f"**Total** : {len(stories)} user stories  ",
        "",
    ]

    current_feature = None
    for s in stories:
        if s.get("feature_id") != current_feature:
            current_feature = s.get("feature_id")
            lines += ["", f"## {current_feature} — {s.get('feature_name', '')}", ""]

        prio_badge = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(s.get("priority", ""), "⚪")
        lines += [
            f"### {s.get('id', '')} — {s.get('title', '')}",
            "",
            f"{prio_badge} **Priority**: {s.get('priority', '')} | **Points**: {s.get('story_points', '?')} | **Labels**: {', '.join(s.get('labels', []))}",
            "",
            f"**As a** {s.get('as_a', '')}  ",
            f"**I want** {s.get('i_want', '')}  ",
            f"**So that** {s.get('so_that', '')}  ",
            "",
            "**Gherkin Scenario:**",
            "```gherkin",
            s.get("gherkin", ""),
            "```",
            "",
            "**Acceptance Criteria:**",
        ]
        for ac in s.get("acceptance_criteria", []):
            lines.append(f"- {ac}")
        lines.append("")

    lines += ["---", "_Generated by userstory-generator-agent.py_"]

    path = os.path.join(DOCS_DIR, "user-stories-mydemoapp.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _print_summary(stories: list):
    by_prio = {"High": 0, "Medium": 0, "Low": 0}
    for s in stories:
        p = s.get("priority", "Medium")
        by_prio[p] = by_prio.get(p, 0) + 1

    print(f"\n  {W}Répartition par priorité :{E}")
    print(f"  {R}High   : {by_prio['High']}{E}")
    print(f"  {Y}Medium : {by_prio['Medium']}{E}")
    print(f"  {G}Low    : {by_prio['Low']}{E}")

    total_pts = sum(int(s.get("story_points", 3)) for s in stories)
    print(f"\n  Total story points : {W}{total_pts}{E}")


def cmd_dump():
    path = os.path.join(DOCS_DIR, "user-stories-mydemoapp.json")
    if not os.path.exists(path):
        print(f"{R}User stories non trouvées — lance d'abord : python agents/userstory-generator-agent.py generate{E}")
        return
    with open(path, encoding="utf-8") as f:
        stories = json.load(f)
    print(json.dumps(stories, ensure_ascii=False, indent=2))


def cmd_preview():
    path = os.path.join(DOCS_DIR, "user-stories-mydemoapp.json")
    if not os.path.exists(path):
        print(f"{R}User stories non trouvées — lance d'abord generate{E}")
        return
    with open(path, encoding="utf-8") as f:
        stories = json.load(f)

    print(f"\n{W}USER STORIES — SauceLabs My Demo App ({len(stories)} total){E}\n")
    current_feature = None
    for s in stories:
        if s.get("feature_id") != current_feature:
            current_feature = s.get("feature_id")
            print(f"\n  {C}{current_feature} — {s.get('feature_name','')}{E}")
        prio_color = R if s.get("priority") == "High" else Y if s.get("priority") == "Medium" else G
        pts = s.get("story_points", "?")
        print(f"    {prio_color}[{s.get('priority','?'):6}]{E} {s.get('id',''):<8} {s.get('title','')[:60]} ({pts}pts)")


def print_help():
    print(f"""
{W}USER STORY GENERATOR AGENT — SauceLabs My Demo App{E}

  python agents/userstory-generator-agent.py generate   Génère toutes les user stories
  python agents/userstory-generator-agent.py preview     Affiche le résumé des US existantes
  python agents/userstory-generator-agent.py dump        Affiche le JSON brut
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "generate":
        cmd_generate()
    elif cmd == "dump":
        cmd_dump()
    elif cmd == "preview":
        cmd_preview()
    else:
        print_help()
