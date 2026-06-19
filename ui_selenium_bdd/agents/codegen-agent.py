# ============================================================
# Codegen Agent — Génération de code Java Selenium BDD
# ============================================================
# Commandes :
#   python agents/codegen-agent.py feature <titre>    → .feature Gherkin
#   python agents/codegen-agent.py steps <feature>    → step definitions Java
#   python agents/codegen-agent.py page <nom>         → Page Object Java
#   python agents/codegen-agent.py tc [--tc=N]        → cas de test depuis TC list
#   python agents/codegen-agent.py full               → feature + steps + page
# ============================================================
# TCs disponibles : 26 (automationexercise.com)
# ============================================================

import sys, os, json, re, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(__file__))

import llm
from prompt_store import PromptStore

_ps = PromptStore()

FRAMEWORK    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEATURES_DIR = os.path.join(FRAMEWORK, "src", "test", "resources", "features")
STEPS_DIR    = os.path.join(FRAMEWORK, "src", "test", "java", "com", "qacart", "todo", "steps")
PAGES_DIR    = os.path.join(FRAMEWORK, "src", "test", "java", "com", "qacart", "todo", "pages")

R = "\033[31m"; G = "\033[32m"; Y = "\033[33m"; C = "\033[36m"
W = "\033[1m";  E = "\033[0m"

PACKAGE_STEPS = "com.qacart.todo.steps"
PACKAGE_PAGES = "com.qacart.todo.pages"

# Catalogue des 26 TCs d'automationexercise.com
TEST_CASES = {
    1:  ("Register User",                           ["@smoke","@regression","@auth"]),
    2:  ("Login User with correct credentials",     ["@smoke","@regression","@auth"]),
    3:  ("Login User with incorrect credentials",   ["@regression","@auth","@negative"]),
    4:  ("Logout User",                             ["@regression","@auth"]),
    5:  ("Register User with existing email",       ["@regression","@auth","@negative"]),
    6:  ("Contact Us Form",                         ["@regression","@contact"]),
    7:  ("Verify Test Cases Page",                  ["@regression","@navigation"]),
    8:  ("Verify All Products and product detail",  ["@smoke","@regression","@products"]),
    9:  ("Search Product",                          ["@smoke","@regression","@products"]),
    10: ("Verify Subscription in home page",        ["@regression","@subscription"]),
    11: ("Verify Subscription in Cart page",        ["@regression","@subscription"]),
    12: ("Add Products in Cart",                    ["@critical","@regression","@cart"]),
    13: ("Verify Product quantity in Cart",         ["@regression","@cart"]),
    14: ("Place Order: Register while Checkout",    ["@critical","@regression","@order"]),
    15: ("Place Order: Register before Checkout",   ["@critical","@regression","@order"]),
    16: ("Place Order: Login before Checkout",      ["@critical","@regression","@order"]),
    17: ("Remove Products From Cart",               ["@regression","@cart"]),
    18: ("View Category Products",                  ["@regression","@navigation","@products"]),
    19: ("View & Cart Brand Products",              ["@regression","@products"]),
    20: ("Search Products and Verify Cart After Login", ["@regression","@cart","@products"]),
    21: ("Add review on product",                   ["@regression","@products"]),
    22: ("Add to cart from Recommended items",      ["@regression","@cart"]),
    23: ("Verify address details in checkout page", ["@regression","@order"]),
    24: ("Download Invoice after purchase order",   ["@regression","@order"]),
    25: ("Verify Scroll Up using Arrow button",     ["@regression","@ui"]),
    26: ("Verify Scroll Up without Arrow button",   ["@regression","@ui"]),
}

TC_STEPS = {
    1: [
        "Navigate to https://automationexercise.com",
        "Verify home page is visible",
        "Click 'Signup / Login' button",
        "Verify 'New User Signup!' is visible",
        "Enter name and email address",
        "Click 'Signup' button",
        "Verify 'ENTER ACCOUNT INFORMATION' is visible",
        "Fill account details: Title, Name, Email, Password, Date of birth",
        "Check 'Sign up for our newsletter!'",
        "Fill address details: First name, Last name, Company, Address, Country, State, City, Zipcode, Mobile Number",
        "Click 'Create Account' button",
        "Verify 'ACCOUNT CREATED!' message",
        "Click 'Continue' button",
        "Verify logged-in user name is visible",
        "Click 'Delete Account' button",
        "Verify 'ACCOUNT DELETED!' message",
    ],
    2: [
        "Navigate to https://automationexercise.com",
        "Verify home page is visible",
        "Click 'Signup / Login' button",
        "Verify 'Login to your account' is visible",
        "Enter correct email and password",
        "Click 'login' button",
        "Verify logged-in user name is visible",
        "Click 'Delete Account' button",
        "Verify 'ACCOUNT DELETED!' message",
    ],
    12: [
        "Navigate to https://automationexercise.com",
        "Verify home page is visible",
        "Click 'Products' button",
        "Hover over first product and click 'Add to cart'",
        "Click 'Continue Shopping' button",
        "Hover over second product and click 'Add to cart'",
        "Click 'View Cart' button",
        "Verify both products are added to cart",
        "Verify their prices, quantities and total price",
    ],
    14: [
        "Navigate to https://automationexercise.com",
        "Verify home page is visible",
        "Add products to cart",
        "Click 'Cart' button and verify cart page",
        "Click 'Proceed To Checkout' button",
        "Click 'Register / Login' button",
        "Fill all details and create account",
        "Verify 'ACCOUNT CREATED!' and click Continue",
        "Verify logged-in user name is visible",
        "Click 'Cart' and click 'Proceed To Checkout'",
        "Verify Address Details and Review Your Order",
        "Enter description in comment text area",
        "Click 'Place Order' button",
        "Enter payment details and click 'Pay and Confirm Order'",
        "Verify success message 'Your order has been placed successfully!'",
        "Click 'Delete Account' button",
        "Verify 'ACCOUNT DELETED!' message",
    ],
}


def _write_file(path: str, content: str, label: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        print(f"  {Y}[WARN] Fichier existant : {label} — écrasé{E}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  {G}✓ Généré : {label}{E}")


# ── Génération feature ─────────────────────────────────────────────────────────

def cmd_feature(tc_id: int):
    if tc_id not in TEST_CASES:
        print(f"  {R}TC{tc_id} inconnu (1-26){E}")
        return
    title, tags = TEST_CASES[tc_id]
    steps = TC_STEPS.get(tc_id, [])
    steps_hint = "\n".join(f"    {i+1}. {s}" for i, s in enumerate(steps)) if steps else "  (steps à détailler)"

    _tpl = _ps.get("tc_generate") or (
        "Génère un fichier Gherkin (.feature) complet pour ce cas de test Selenium BDD :\n\n"
        "TC ID   : {tc_id}\n"
        "Titre   : {tc_title}\n"
        "Tags    : {tags}\n"
        "Application : automationexercise.com (e-commerce)\n"
        "Steps prévus :\n{steps}\n\n"
        "Génère un Feature file Gherkin propre avec :\n"
        "- Feature et Background si nécessaire\n"
        "- Scénario avec les tags appropriés\n"
        "- Steps Given/When/Then bien rédigés\n"
        "- Données de test incluses si besoin\n"
        "Réponds UNIQUEMENT avec le contenu du fichier .feature (pas de markdown)."
    )
    messages = [{"role": "user", "content": _fmt_simple(_tpl,
        tc_id=str(tc_id), tc_title=title,
        tags=" ".join(tags), steps=steps_hint,
    )}]
    print(f"  {C}Génération feature TC{tc_id} : {title}...{E}", flush=True)
    try:
        content = llm.chat(messages)
        _ps.record_usage("tc_generate")
        filename = f"TC{tc_id:02d}_{re.sub(r'[^a-zA-Z0-9]', '', title.replace(' ','_'))}.feature"
        path = os.path.join(FEATURES_DIR, filename)
        _write_file(path, content.strip(), filename)
        return path
    except Exception as ex:
        print(f"  {R}LLM erreur : {ex}{E}")
        return None


def _fmt_simple(template: str, **kw) -> str:
    result = template
    for k, v in kw.items():
        result = result.replace("{" + k + "}", str(v))
    return result


# ── Génération steps Java ──────────────────────────────────────────────────────

def cmd_steps(feature_file: str, tc_id: int = None):
    if not os.path.exists(feature_file):
        feature_file = os.path.join(FEATURES_DIR, feature_file)
    if not os.path.exists(feature_file):
        print(f"  {R}Feature introuvable : {feature_file}{E}")
        return
    with open(feature_file, encoding="utf-8") as f:
        feature_content = f.read()
    title = TEST_CASES.get(tc_id, ("Feature",))[0] if tc_id else "Feature"
    class_name = re.sub(r'[^a-zA-Z0-9]', '', title.replace(' ', '_')) + "Steps"

    messages = [{"role": "user", "content": (
        f"Génère les Step Definitions Java pour ce fichier Gherkin :\n\n"
        f"```gherkin\n{feature_content}\n```\n\n"
        f"Contraintes :\n"
        f"- Package : {PACKAGE_STEPS}\n"
        f"- Classe : {class_name}\n"
        f"- Framework : Selenium 4 + Cucumber 7 + TestNG\n"
        f"- Utilise WebDriver injecté via ScenarioContext\n"
        f"- Utilise les annotations @Given, @When, @Then de io.cucumber.java.en\n"
        f"- Utilise ElementActions et Waiter pour les interactions\n"
        f"- Imports nécessaires inclus\n"
        f"Réponds UNIQUEMENT avec le code Java (pas de markdown)."
    )}]
    print(f"  {C}Génération steps Java pour {os.path.basename(feature_file)}...{E}", flush=True)
    try:
        content = llm.chat_structured(messages, {"type": "string"}) if False else llm.chat(messages)
        path = os.path.join(STEPS_DIR, f"{class_name}.java")
        _write_file(path, content.strip(), f"{class_name}.java")
        return path
    except Exception as ex:
        print(f"  {R}LLM erreur : {ex}{E}")
        return None


# ── Génération Page Object Java ────────────────────────────────────────────────

def cmd_page(page_name: str, url_path: str = "/"):
    class_name = page_name.replace(" ", "").replace("-", "") + "Page"
    messages = [{"role": "user", "content": (
        f"Génère un Page Object Java pour la page '{page_name}' d'automationexercise.com{url_path}\n\n"
        f"Contraintes :\n"
        f"- Package : {PACKAGE_PAGES}\n"
        f"- Classe : {class_name} extends BasePage\n"
        f"- Selenium 4 — utilise By.cssSelector() (pas XPath sauf si nécessaire)\n"
        f"- Constantes pour tous les sélecteurs\n"
        f"- Méthodes métier claires (clickSignup(), enterEmail(), etc.)\n"
        f"- Attentes explicites via WebDriverWait (ElementActions/Waiter)\n"
        f"- Imports nécessaires inclus\n"
        f"Réponds UNIQUEMENT avec le code Java (pas de markdown)."
    )}]
    print(f"  {C}Génération Page Object : {class_name}...{E}", flush=True)
    try:
        content = llm.chat(messages)
        path = os.path.join(PAGES_DIR, f"{class_name}.java")
        _write_file(path, content.strip(), f"{class_name}.java")
        return path
    except Exception as ex:
        print(f"  {R}LLM erreur : {ex}{E}")
        return None


def cmd_full(tc_ids: list):
    print(f"\n{W}CODEGEN — Génération complète pour TC{tc_ids}{E}\n")
    for tc_id in tc_ids:
        if tc_id not in TEST_CASES:
            print(f"  {R}TC{tc_id} inconnu{E}")
            continue
        title, _ = TEST_CASES[tc_id]
        print(f"\n  {W}TC{tc_id}: {title}{E}")
        feature_path = cmd_feature(tc_id)
        if feature_path:
            cmd_steps(feature_path, tc_id)
        page_name = title.split()[0] if title else "Page"
        cmd_page(page_name)


def cmd_list():
    print(f"\n{W}CODEGEN — 26 cas de test automationexercise.com{E}\n")
    for tc_id, (title, tags) in TEST_CASES.items():
        existing = "✓" if os.path.exists(
            os.path.join(FEATURES_DIR, f"TC{tc_id:02d}_{re.sub(r'[^a-zA-Z0-9]','',title.replace(' ','_'))}.feature")
        ) else " "
        print(f"  [{existing}] TC{tc_id:02d} {title[:50]:<50} {' '.join(tags[:2])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Codegen Agent — Selenium BDD Java")
    parser.add_argument("command", choices=["feature", "steps", "page", "full", "tc", "list"])
    parser.add_argument("target", nargs="?", default=None)
    parser.add_argument("--tc", type=int, nargs="+", default=None)
    args = parser.parse_args()

    if args.command == "list":
        cmd_list()
    elif args.command == "feature":
        tc_id = args.tc[0] if args.tc else (int(args.target) if args.target else None)
        if tc_id:
            cmd_feature(tc_id)
        else:
            print(f"  {R}Usage: codegen-agent.py feature --tc=1{E}")
    elif args.command == "steps":
        cmd_steps(args.target or "", args.tc[0] if args.tc else None)
    elif args.command == "page":
        cmd_page(args.target or "Home")
    elif args.command in ("full", "tc"):
        tcs = args.tc or ([int(args.target)] if args.target else list(range(1, 5)))
        cmd_full(tcs)
