# ============================================================
# Spec Generator Agent — SauceLabs My Demo App
# ============================================================
# Génère le document de spécification fonctionnelle de l'application
# SauceLabs My Demo App (Android) à partir des données connues de l'app.
#
# Usage:
#   python agents/spec-generator-agent.py generate   → génère le spec doc
#   python agents/spec-generator-agent.py dump        → affiche le spec brut
# ============================================================

import sys, os, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm

FRAMEWORK = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR  = os.path.join(FRAMEWORK, "docs")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

APP_CONTEXT = """
Application : SauceLabs My Demo App v2.2.0 (Android)
Package     : com.saucelabs.mydemoapp.android
APK         : mda-2.2.0-25.apk

ÉCRANS CONNUS :
1. Login Screen
   - Champs : Username (email), Password
   - Bouton : LOGIN
   - Lien   : Sign Up (navigation vers écran signup)
   - Erreurs: "Username is required", "Password is required",
              "Username and password do not match any user in this service."
   - Identifiants valides : bob@example.com / 10203040
   - Identifiants problème: alice@example.com / 10203040 (performance glitch)
   - Compte verrouillé   : fiona@example.com / 10203040

2. Products Catalog Screen
   - Titre        : "PRODUCTS"
   - Liste produits (RecyclerView) avec : image, nom, prix, bouton Add to Cart
   - Sort button (icône entonnoir) → options : Name (A to Z), Name (Z to A), Price (low to high), Price (high to low)
   - Badge panier dans la toolbar
   - Navigation burger menu (hamburger)

3. Product Detail Screen
   - Image produit (grande), nom, description, prix
   - Bouton "Add to Cart"
   - Quantité (+ / -)
   - Navigation retour

4. Cart Screen
   - Liste des produits ajoutés (nom, prix, quantité, image)
   - Bouton "Remove" pour chaque article
   - Bouton "Proceed To Checkout"
   - Bouton "Go Shopping" (si panier vide)
   - Badge avec le nombre d'articles

5. Checkout - Address Screen
   - Champs : Full Name, Address Line 1, City, State/Region, Zip Code, Country
   - Bouton "To Payment"
   - Validation : tous les champs requis

6. Checkout - Payment Screen
   - Champs : Card Number, Expiration Date, Security Code
   - Case à cocher : "My billing and delivery address are the same"
   - Bouton "Review Order"

7. Checkout - Review Screen
   - Récapitulatif de la commande : articles, adresse, paiement, total
   - Bouton "Place Order"

8. Checkout - Complete Screen
   - Message de succès : "THANK YOU FOR YOUR ORDER"
   - Numéro de commande
   - Bouton "Continue Shopping"

9. Navigation Menu (Sidebar)
   - Éléments : Home, Catalog, My Carts, My Favorites, Login/Logout
   - Fermeture par geste ou bouton X

RÈGLES MÉTIER :
- L'utilisateur doit être connecté pour accéder au panier et au checkout
- Les stocks ne diminuent pas (app de démo)
- Les paiements sont simulés (aucune transaction réelle)
- La quantité par article peut aller de 1 à N
"""


def generate_spec() -> dict:
    schema = {
        "app_name": "string",
        "version": "string",
        "platform": "string",
        "overview": "string — description générale de l'application en 2-3 phrases",
        "features": [
            {
                "id": "F-001",
                "name": "string",
                "description": "string",
                "screens": ["liste des écrans concernés"],
                "acceptance_criteria": ["liste des critères d'acceptation"],
                "priority": "High | Medium | Low"
            }
        ],
        "test_accounts": [
            {"role": "string", "email": "string", "password": "string", "notes": "string"}
        ],
        "constraints": ["liste des contraintes techniques ou métier"]
    }

    messages = [{
        "role": "user",
        "content": (
            f"Tu es un expert QA Analyste. À partir du contexte suivant sur l'application mobile, "
            f"génère un document de spécification fonctionnelle structuré et complet.\n\n"
            f"CONTEXTE DE L'APPLICATION :\n{APP_CONTEXT}\n\n"
            f"Génère un spec doc professionnel avec :\n"
            f"- Vue d'ensemble de l'app\n"
            f"- Au moins 8 features (Login, Catalog, ProductDetail, Cart, CheckoutAddress, "
            f"CheckoutPayment, CheckoutReview, CheckoutComplete, Navigation)\n"
            f"- Critères d'acceptation précis et testables pour chaque feature\n"
            f"- Comptes de test documentés\n"
            f"- Contraintes techniques\n\n"
            f"Sois précis, professionnel, orienté QA/test automation."
        )
    }]

    print(f"  {C}Génération du document de spécification via LLM...{E}")
    return llm.chat_structured(messages, schema)


def save_spec_json(spec: dict) -> str:
    os.makedirs(DOCS_DIR, exist_ok=True)
    path = os.path.join(DOCS_DIR, "spec-mydemoapp.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    return path


def save_spec_markdown(spec: dict) -> str:
    os.makedirs(DOCS_DIR, exist_ok=True)
    lines = [
        f"# {spec.get('app_name', 'SauceLabs My Demo App')} — Specification Document",
        f"",
        f"**Version** : {spec.get('version', '2.2.0')}  ",
        f"**Platform** : {spec.get('platform', 'Android')}  ",
        f"**Date** : 2026-06-12  ",
        f"",
        f"## Overview",
        f"",
        spec.get("overview", ""),
        f"",
        f"## Features",
        f"",
    ]

    for feat in spec.get("features", []):
        lines += [
            f"### {feat.get('id', '')} — {feat.get('name', '')}",
            f"",
            f"**Priority** : {feat.get('priority', 'Medium')}  ",
            f"**Screens** : {', '.join(feat.get('screens', []))}",
            f"",
            f"{feat.get('description', '')}",
            f"",
            f"**Acceptance Criteria :**",
        ]
        for ac in feat.get("acceptance_criteria", []):
            lines.append(f"- {ac}")
        lines.append("")

    lines += [
        "## Test Accounts",
        "",
        "| Role | Email | Password | Notes |",
        "|------|-------|----------|-------|",
    ]
    for acc in spec.get("test_accounts", []):
        lines.append(f"| {acc.get('role','')} | {acc.get('email','')} | {acc.get('password','')} | {acc.get('notes','')} |")

    lines += [
        "",
        "## Technical Constraints",
        "",
    ]
    for c in spec.get("constraints", []):
        lines.append(f"- {c}")

    lines += ["", "---", "_Generated by spec-generator-agent.py_"]

    path = os.path.join(DOCS_DIR, "spec-mydemoapp.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def cmd_generate():
    print(f"\n{W}SPEC GENERATOR AGENT — SauceLabs My Demo App{E}\n")
    spec = generate_spec()

    json_path = save_spec_json(spec)
    md_path   = save_spec_markdown(spec)

    print(f"\n{G}✅ Spec document généré :{E}")
    print(f"   JSON     : {json_path}")
    print(f"   Markdown : {md_path}")
    print(f"\n{W}Features générées ({len(spec.get('features', []))}) :{E}")
    for f in spec.get("features", []):
        prio_color = R if f.get("priority") == "High" else Y if f.get("priority") == "Medium" else G
        print(f"  {prio_color}[{f.get('priority','?'):6}]{E} {f.get('id',''):<8} {f.get('name','')}")

    return spec


def cmd_dump():
    path = os.path.join(DOCS_DIR, "spec-mydemoapp.json")
    if not os.path.exists(path):
        print(f"{R}Spec non trouvé — lance d'abord : python agents/spec-generator-agent.py generate{E}")
        return
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    print(json.dumps(spec, ensure_ascii=False, indent=2))


def print_help():
    print(f"""
{W}SPEC GENERATOR AGENT — SauceLabs My Demo App{E}

  python agents/spec-generator-agent.py generate   Génère le spec document (JSON + Markdown)
  python agents/spec-generator-agent.py dump        Affiche le spec JSON existant
""")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "generate":
        cmd_generate()
    elif cmd == "dump":
        cmd_dump()
    else:
        print_help()
