"""Generate a PDF map of the ui_playwright_bdd AI agents."""
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = os.path.dirname(__file__)
OUTPUT = os.path.join(ROOT, "docs", "playwright-agents-cartographie.pdf")
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

NAVY = colors.HexColor("#172554")
BLUE = colors.HexColor("#1D4ED8")
TEAL = colors.HexColor("#0F766E")
ORANGE = colors.HexColor("#C2410C")
RED = colors.HexColor("#B91C1C")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
PALE = colors.HexColor("#F8FAFC")
WHITE = colors.white


def styles():
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=WHITE, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=11, leading=15, textColor=colors.HexColor("#DBEAFE"), alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=NAVY, spaceBefore=12, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=BLUE, spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK, spaceAfter=3),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=INK),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=10, textColor=INK),
        "cell_bold": ParagraphStyle("cell_bold", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=INK),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=7, leading=9, textColor=INK),
    }


def p(text, style):
    return Paragraph(text, style)


def bullet(items, s):
    return "<br/>".join("• " + item for item in items)


AGENTS = [
    ("1. Codegen Agent", "codegen-agent.js", "Génération LLM de Gherkin, step definitions TypeScript et Page Objects Playwright.", ["User Stories Jira", "fichiers .feature", "llm.chat()"], ["src/features/", "src/steps/", "src/pages/", "tracer.js"], ["Jira REST API", "Groq ou Ollama"]),
    ("2. Runner Agent", "runner-agent.js", "Résumé narratif LLM ; exécution et statistiques principalement déterministes.", ["features, steps, pages", "World et hooks", "allure-results/"], ["Cucumber.js", "Playwright", "Allure", "memory-store.js", "tracer.js"], ["Application QACart Todo", "Groq ou Ollama pour le résumé"]),
    ("3. Quality Agent", "quality-agent.js", "Classification real_bug/flaky/env_issue/false_positive, score de confiance, vérification adversariale, RCA et JSON structuré.", ["résultats Allure", "historique mémoire", "échantillons features/steps"], ["llm.chatConfident()", "chatAdversarial()", "chatCot()", "chatStructured()", "prompt-store.js", "memory-store.js"], ["Groq ou Ollama"]),
    ("4. Bug Agent", "bug-agent.js", "Boucle agentique avec outils read_file, apply_fix et report_analysis ; RCA et génération de patch.", ["échecs Allure", "fichiers projet", "prompt repair_patch"], ["fs", "memory-store.js", "prompt-store.js", "tracer.js", "src/steps et src/features"], ["Groq ou Ollama"]),
    ("5. Reporting Agent", "reporting-agent.js", "Résumé LLM pour les notifications ; KPI, dashboard et synchronisation Jira déterministes.", ["allure-results/", "webhooks Slack/Teams", "configuration Jira"], ["dashboard HTML", "tracer.js", "llm.chat()"], ["Slack", "Microsoft Teams", "Jira REST API", "Chart.js CDN"]),
    ("6. Planning Agent", "planning-agent.js", "Analyse déterministe de couverture et suggestions Gherkin par LLM.", ["stories, boards et sprints Jira", "features existantes", "tags et scénarios"], ["jira-fetcher.js", "Jira Agile API", "src/features/", "tracer.js"], ["Jira REST/Agile API", "Groq ou Ollama"]),
    ("7. Advisor Agent", "advisor-agent.js", "Self-consistency, votes majoritaires, prédiction de risque et quality gate GO/NO-GO.", ["résultats Allure", "épisodes mémoire", "prompts release_vote et predict_gate"], ["memory-store.js", "prompt-store.js", "llm.chatSelfConsistent()", "chatStructured()", "tracer.js"], ["Groq ou Ollama"]),
    ("8. Observability Agent", "observability-agent.js", "Aucune IA : calculs déterministes de latence, P95, erreurs, coûts et anomalies.", ["traces JSONL", "état circuit breaker", "cache LLM", "prompts"], ["tracer.js", "circuit-breaker.js", "prompt-store.js"], ["Aucun service externe"]),
    ("9. CI Agent", "ci-agent.js", "Génération IA de messages de commit, descriptions de PR et release notes.", ["état Git, diff et historique", "options CI/PR/release"], ["git", "GitHub CLI gh", "GitHub Actions", "fs", "tracer.js", "llm.chat()"], ["GitHub", "dépôt Git distant", "Groq ou Ollama"]),
    ("10. Pipeline Agent", "pipeline-agent.js", "Aucune IA propre : orchestration déterministe des autres agents.", ["modes full, quick, report, status", "artefacts des étapes précédentes"], ["spawnSync('node', ...)", "Allure", "memory/", "logs/", "docs/"], ["Indirectement Jira, Groq/Ollama, Slack/Teams et GitHub"]),
]


def table_for_agent(agent, s):
    name, file_name, technique, inputs, internal, external = agent
    rows = [
        [p("Agent", s["label"]), p(name, s["cell_bold"])],
        [p("Fichier", s["label"]), p("scripts/agents/" + file_name, s["code"])],
        [p("Technique IA", s["label"]), p(technique, s["cell"])],
        [p("Entrées", s["label"]), p(bullet(inputs, s), s["cell"])],
        [p("Communications framework", s["label"]), p(bullet(internal, s), s["cell"])],
        [p("Services externes", s["label"]), p(bullet(external, s), s["cell"])],
    ]
    table = Table(rows, colWidths=[4.2 * cm, 12.4 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E0F2FE")),
        ("BACKGROUND", (1, 0), (1, -1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(1.7 * cm, 1.1 * cm, "ui_playwright_bdd - Cartographie des agents IA")
    canvas.drawRightString(19.3 * cm, 1.1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    s = styles()
    story = []
    cover = Table([[p("Cartographie des agents IA", s["title"])], [p("Framework ui_playwright_bdd · Playwright + Cucumber BDD + TypeScript", s["subtitle"])]] , colWidths=[16.6 * cm])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, 0), 28),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("TOPPADDING", (0, 1), (-1, 1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 22),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story += [cover, Spacer(1, 14), p("Périmètre", s["h1"]), p("Ce document décrit les 10 agents présents dans ui_playwright_bdd, les techniques IA qu’ils utilisent et leurs communications avec les composants du framework et les services externes.", s["body"]), p("Généré le " + date.today().strftime("%d/%m/%Y"), s["small"]), Spacer(1, 8)]

    story.append(p("Architecture de communication", s["h1"]))
    story.append(p("Les agents sont lancés comme des processus Node.js indépendants. Ils échangent surtout via des artefacts persistants plutôt que par des appels directs entre agents.", s["body"]))
    architecture = [
        [p("Source", s["label"]), p("Artefact partagé", s["label"]), p("Consommateurs", s["label"])],
        [p("Jira", s["cell"]), p("Stories, critères, sprints", s["cell"]), p("Planning, Codegen", s["cell"])],
        [p("Code généré", s["cell"]), p("features / steps / pages", s["cell"]), p("Runner", s["cell"])],
        [p("Runner", s["cell"]), p("allure-results/", s["cell"]), p("Quality, Bug, Reporting, Advisor", s["cell"])],
        [p("Agents", s["cell"]), p("memory/ et logs/", s["cell"]), p("Quality, Bug, Advisor, Observability", s["cell"])],
        [p("Pipeline", s["cell"]), p("docs/ et pipeline-summary.json", s["cell"]), p("CI, dashboards et suivi", s["cell"])],
    ]
    arch = Table(architecture, colWidths=[3.3 * cm, 6.5 * cm, 6.8 * cm])
    arch.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [arch, PageBreak(), p("Les 10 agents", s["h1"])]
    for index, agent in enumerate(AGENTS):
        story.append(p(agent[0], s["h2"]))
        story.append(table_for_agent(agent, s))
        story.append(Spacer(1, 7))
        if index in (3, 6):
            story.append(PageBreak())

    story += [PageBreak(), p("Modules transversaux", s["h1"]), p("llm.js expose chat, chatStream, chatCot, chatStructured, chatConfident, chatAdversarial et chatSelfConsistent. Groq est utilisé si GROQ_API_KEY est disponible ; Ollama sert de provider de repli.", s["body"]), p("memory-store.js conserve la mémoire épisodique dans memory/episodes.jsonl. prompt-store.js versionne les prompts. tracer.js écrit les traces dans logs/traces.jsonl. circuit-breaker.js fournit cache, protection contre les pannes et fallback.", s["body"]), p("RAG", s["h2"]), p("Le dossier RAG contient une base documentaire QA, notamment QA_ANALYSIS.md, mais aucun retriever, index vectoriel ou chargement opérationnel de ces documents n’a été identifié dans les agents analysés. La mémoire JSONL est utilisée comme contexte historique, mais elle ne constitue pas un RAG vectoriel.", s["body"]), p("Points de vigilance", s["h1"]), p(bullet(["Le Bug Agent peut modifier réellement les fichiers via apply_fix.", "Les corrections ne sont pas automatiquement validées par les tests ou TypeScript.", "Le Pipeline transmet surtout des fichiers et rapports, pas des objets structurés directement.", "Certains prompts présents dans prompts/ ne sont pas consommés directement par le code.", "Le Quality Gate Advisor dépend en partie d’une décision LLM, et non uniquement de seuils déterministes."], s), s["body"])]

    doc = SimpleDocTemplate(OUTPUT, pagesize=A4, rightMargin=1.7 * cm, leftMargin=1.7 * cm, topMargin=1.5 * cm, bottomMargin=1.7 * cm, title="Cartographie des agents IA - ui_playwright_bdd", author="QA Plateforme")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    build()
