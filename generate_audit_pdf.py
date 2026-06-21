"""Génère le PDF d'audit IA des deux frameworks QA."""
import sys
sys.path.insert(0, r'c:\users\lenovo\anaconda3\lib\site-packages')

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import date
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "docs", "audit-ia-frameworks.pdf")
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1B2A4A")
BLUE       = colors.HexColor("#2563EB")
TEAL       = colors.HexColor("#0891B2")
GREEN      = colors.HexColor("#16A34A")
ORANGE     = colors.HexColor("#EA580C")
RED        = colors.HexColor("#DC2626")
YELLOW_BG  = colors.HexColor("#FEF9C3")
GREEN_BG   = colors.HexColor("#DCFCE7")
RED_BG     = colors.HexColor("#FEE2E2")
ORANGE_BG  = colors.HexColor("#FFEDD5")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
GRAY_LINE  = colors.HexColor("#E2E8F0")
DARK_GRAY  = colors.HexColor("#374151")
MID_GRAY   = colors.HexColor("#6B7280")
WHITE      = colors.white

# ── Styles ────────────────────────────────────────────────────────────────
def make_styles():
    s = {}

    s['cover_title'] = ParagraphStyle(
        'cover_title', fontName='Helvetica-Bold', fontSize=28,
        textColor=WHITE, alignment=TA_CENTER, spaceAfter=6, leading=34
    )
    s['cover_sub'] = ParagraphStyle(
        'cover_sub', fontName='Helvetica', fontSize=13,
        textColor=colors.HexColor("#CBD5E1"), alignment=TA_CENTER, spaceAfter=4, leading=18
    )
    s['cover_date'] = ParagraphStyle(
        'cover_date', fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor("#94A3B8"), alignment=TA_CENTER
    )
    s['h1'] = ParagraphStyle(
        'h1', fontName='Helvetica-Bold', fontSize=16,
        textColor=NAVY, spaceBefore=18, spaceAfter=6, leading=20
    )
    s['h2'] = ParagraphStyle(
        'h2', fontName='Helvetica-Bold', fontSize=12,
        textColor=BLUE, spaceBefore=14, spaceAfter=4, leading=16
    )
    s['h3'] = ParagraphStyle(
        'h3', fontName='Helvetica-Bold', fontSize=10,
        textColor=TEAL, spaceBefore=10, spaceAfter=3, leading=14
    )
    s['body'] = ParagraphStyle(
        'body', fontName='Helvetica', fontSize=9,
        textColor=DARK_GRAY, spaceAfter=4, leading=13
    )
    s['body_small'] = ParagraphStyle(
        'body_small', fontName='Helvetica', fontSize=8,
        textColor=MID_GRAY, spaceAfter=3, leading=11
    )
    s['caption'] = ParagraphStyle(
        'caption', fontName='Helvetica-Oblique', fontSize=8,
        textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=6
    )
    s['code'] = ParagraphStyle(
        'code', fontName='Courier', fontSize=8,
        textColor=colors.HexColor("#1E293B"), backColor=colors.HexColor("#F1F5F9"),
        leftIndent=8, rightIndent=8, spaceAfter=6, leading=12,
        borderPad=4
    )
    s['badge_green'] = ParagraphStyle(
        'badge_green', fontName='Helvetica-Bold', fontSize=9,
        textColor=GREEN, alignment=TA_CENTER
    )
    s['badge_orange'] = ParagraphStyle(
        'badge_orange', fontName='Helvetica-Bold', fontSize=9,
        textColor=ORANGE, alignment=TA_CENTER
    )
    s['badge_red'] = ParagraphStyle(
        'badge_red', fontName='Helvetica-Bold', fontSize=9,
        textColor=RED, alignment=TA_CENTER
    )
    s['label'] = ParagraphStyle(
        'label', fontName='Helvetica-Bold', fontSize=8,
        textColor=DARK_GRAY
    )
    return s


# ── Helpers ────────────────────────────────────────────────────────────────

def hr(color=GRAY_LINE, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=6, spaceBefore=2)

def sp(h=6):
    return Spacer(1, h)

def check(ok):
    return "✅" if ok else "⚠️"


def score_bar_table(label, pct, color=GREEN):
    """Barre de progression inline dans un tableau."""
    bar_w  = 200
    filled = int(bar_w * pct / 100)
    empty  = bar_w - filled
    data = [[
        Paragraph(label, ParagraphStyle('lb', fontName='Helvetica-Bold', fontSize=8, textColor=DARK_GRAY)),
        Paragraph(f"{pct}%", ParagraphStyle('pct', fontName='Helvetica-Bold', fontSize=8, textColor=color, alignment=TA_RIGHT)),
    ]]
    t = Table(data, colWidths=[11*cm, 2*cm])
    t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    return t


def progress_table(rows, S):
    """rows = [(label, pct, color), ...]"""
    elements = []
    for label, pct, color in rows:
        bar_filled = int(9.5 * pct / 100)
        bar_empty  = 9 - bar_filled
        bar = "█" * bar_filled + "░" * bar_empty
        data = [[
            Paragraph(label, S['label']),
            Paragraph(bar, ParagraphStyle('bar', fontName='Courier', fontSize=9, textColor=color)),
            Paragraph(f"{pct}%", ParagraphStyle('pct', fontName='Helvetica-Bold', fontSize=9,
                                                 textColor=color, alignment=TA_RIGHT)),
        ]]
        t = Table(data, colWidths=[9*cm, 5*cm, 2*cm])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t)
    return elements


# ── Cover page ────────────────────────────────────────────────────────────

def build_cover(S):
    elements = []

    # Bannière de fond simulée via Table
    cover_data = [[
        Paragraph("Audit IA des Frameworks QA", S['cover_title']),
    ]]
    cover_t = Table(cover_data, colWidths=[17*cm])
    cover_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('TOPPADDING', (0,0), (-1,-1), 30),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('LEFTPADDING', (0,0), (-1,-1), 20),
        ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [NAVY]),
    ]))
    elements.append(cover_t)
    elements.append(sp(12))

    sub_data = [[
        Paragraph("playwright-bdd  ·  pytest-bdd", S['cover_sub']),
    ]]
    sub_t = Table(sub_data, colWidths=[17*cm])
    sub_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLUE),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(sub_t)
    elements.append(sp(20))

    # Cards résumé sur 2 colonnes
    card_style = TableStyle([
        ('BACKGROUND',    (0,0), (0,-1), GREEN_BG),
        ('BACKGROUND',    (1,0), (1,-1), LIGHT_BLUE),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ('RIGHTPADDING',  (0,0), (-1,-1), 10),
        ('BOX',           (0,0), (0,-1), 1, GREEN),
        ('BOX',           (1,0), (1,-1), 1, BLUE),
        ('ROUNDEDCORNERS', [4]),
    ])
    c1_style = ParagraphStyle('c1', fontName='Helvetica-Bold', fontSize=22, textColor=GREEN, alignment=TA_CENTER)
    c2_style = ParagraphStyle('c2', fontName='Helvetica-Bold', fontSize=22, textColor=BLUE, alignment=TA_CENTER)
    cl_style = ParagraphStyle('cl', fontName='Helvetica', fontSize=9, textColor=MID_GRAY, alignment=TA_CENTER)

    cards = Table([
        [Paragraph("10 + 10", c1_style), Paragraph("6 patterns LLM", c2_style)],
        [Paragraph("agents IA par framework", cl_style), Paragraph("chat · CoT · structured · confident · adversarial · self-consistent", cl_style)],
    ], colWidths=[8.3*cm, 8.3*cm], rowHeights=[None, None])
    cards.setStyle(card_style)
    elements.append(cards)
    elements.append(sp(10))

    cards2 = Table([
        [Paragraph("5 + 5", c2_style), Paragraph("3", ParagraphStyle('c3', fontName='Helvetica-Bold', fontSize=22, textColor=ORANGE, alignment=TA_CENTER))],
        [Paragraph("prompt templates versionnés", cl_style), Paragraph("gaps à combler", cl_style)],
    ], colWidths=[8.3*cm, 8.3*cm])
    cards2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), LIGHT_BLUE),
        ('BACKGROUND', (1,0), (1,-1), ORANGE_BG),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('BOX', (0,0), (0,-1), 1, BLUE),
        ('BOX', (1,0), (1,-1), 1, ORANGE),
    ]))
    elements.append(cards2)
    elements.append(sp(30))

    # Auteur et date
    footer_data = [[
        Paragraph("Faicel Ghanem — QA Automation Architect", S['body']),
        Paragraph(f"Généré le {date.today().strftime('%d/%m/%Y')}", S['body_small']),
    ]]
    footer_t = Table(footer_data, colWidths=[11*cm, 6*cm])
    footer_t.setStyle(TableStyle([
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LINEABOVE', (0,0), (-1,0), 0.5, GRAY_LINE),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(footer_t)

    return elements


# ── Section 1 : Vue d'ensemble ────────────────────────────────────────────

def build_overview(S):
    elements = []
    elements.append(Paragraph("1. Vue d'ensemble", S['h1']))
    elements.append(hr(NAVY, 1))
    elements.append(sp(4))
    elements.append(Paragraph(
        "Ce document présente l'audit complet des composants IA intégrés dans les deux frameworks "
        "de test automatisé de la plateforme QA. Chaque framework suit la même architecture agentique : "
        "10 agents domaine, 6 patterns LLM, et une infrastructure de résilience et d'observabilité.",
        S['body']
    ))
    elements.append(sp(8))

    # Tableau comparatif
    header_style = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE, alignment=TA_CENTER)
    cell_style   = ParagraphStyle('td', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY, alignment=TA_CENTER)
    left_style   = ParagraphStyle('tdl', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY)
    label_style  = ParagraphStyle('tlb', fontName='Helvetica-Bold', fontSize=8, textColor=DARK_GRAY)

    rows = [
        # Header
        [
            Paragraph("Composant", header_style),
            Paragraph("playwright-bdd", header_style),
            Paragraph("pytest-bdd", header_style),
            Paragraph("Statut", header_style),
        ],
        # Data
        [Paragraph("Agents domaine", label_style),   Paragraph("10 agents JS", cell_style),  Paragraph("10 agents Python", cell_style), Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Patterns LLM", label_style),      Paragraph("7 patterns", cell_style),    Paragraph("6 patterns", cell_style),       Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Circuit Breaker", label_style),   Paragraph("CLOSED/OPEN/HALF_OPEN", cell_style), Paragraph("CLOSED/OPEN/HALF_OPEN", cell_style), Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Memory Store", label_style),      Paragraph("JSONL épisodique", cell_style), Paragraph("JSONL épisodique", cell_style), Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Prompt Store", label_style),      Paragraph("Versioning semver", cell_style), Paragraph("Versioning semver", cell_style), Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Tracer LLM", label_style),        Paragraph("traces.jsonl", cell_style),  Paragraph("traces.jsonl", cell_style),     Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Jira Client", label_style),       Paragraph("jira-fetcher.js", cell_style), Paragraph("jira_fetcher_agent.py", cell_style), Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("agents.md", label_style),         Paragraph("✅", cell_style),            Paragraph("✅", cell_style),               Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("RAG / Knowledge Base", label_style), Paragraph("qa-knowledge.md", cell_style), Paragraph("qa-knowledge.md", cell_style), Paragraph("✅ Complet", ParagraphStyle('g', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER))],
        [Paragraph("Prompt Templates", label_style),  Paragraph("5 fichiers JSON", cell_style), Paragraph("5 fichiers JSON", cell_style), Paragraph("⚠️ Partiel", ParagraphStyle('o', fontName='Helvetica-Bold', fontSize=8, textColor=ORANGE, alignment=TA_CENTER))],
        [Paragraph("Câblage PromptStore", label_style), Paragraph("⚠️ Non câblé", cell_style), Paragraph("⚠️ Non câblé", cell_style),  Paragraph("⚠️ Gap", ParagraphStyle('o', fontName='Helvetica-Bold', fontSize=8, textColor=ORANGE, alignment=TA_CENTER))],
    ]

    col_w = [6*cm, 4*cm, 4*cm, 3*cm]
    t = Table(rows, colWidths=col_w)
    t.setStyle(TableStyle([
        # Header
        ('BACKGROUND',    (0,0), (-1,0), NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        # Alternating rows
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, colors.HexColor("#F8FAFC")]),
        # Lines
        ('GRID',          (0,0), (-1,-1), 0.3, GRAY_LINE),
        ('LINEBELOW',     (0,0), (-1,0), 1, NAVY),
        # Padding
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
    ]))
    elements.append(t)
    return elements


# ── Section 2 : 10 Agents ─────────────────────────────────────────────────

def build_agents(S):
    elements = []
    elements.append(sp(14))
    elements.append(Paragraph("2. Les 10 Agents IA", S['h1']))
    elements.append(hr(NAVY, 1))
    elements.append(sp(4))
    elements.append(Paragraph(
        "Chaque agent regroupe un domaine fonctionnel avec des sous-commandes. "
        "Architecture identique dans les deux frameworks (JS et Python).",
        S['body']
    ))
    elements.append(sp(8))

    agents = [
        ("runner-agent",       "Exécution des tests",    "run · smoke · critical · regression · gono-go · baseline",             GREEN),
        ("bug-agent",          "Triage & RCA",           "triage · rca · repair · report · loop (agentique)",                    RED),
        ("codegen-agent",      "Génération de code",     "spec · generate · tc · coverage · full",                               BLUE),
        ("quality-agent",      "Qualité & KPI",          "analyze · kpi · flaky · verify · gate",                                TEAL),
        ("reporting-agent",    "Rapports & Notifs",      "generate · serve · open · notify · publish",                           colors.HexColor("#7C3AED")),
        ("advisor-agent",      "Décision release",       "release (self-consistent) · predict · recommend",                      ORANGE),
        ("observability-agent","Observabilité",          "traces · circuit · memory · prompts · dashboard",                      colors.HexColor("#0369A1")),
        ("ci-agent",           "CI/CD & GitHub",         "commit · push · pr · ci · release · changelog",                       colors.HexColor("#374151")),
        ("planning-agent",     "Jira & Planning",        "setup · stories · sprint · tc · tickets · sync",                       colors.HexColor("#9333EA")),
        ("pipeline-agent",     "Orchestrateur maître",   "full · quick · nightly · report · gate · status",                      NAVY),
    ]

    header_s  = ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)
    agent_s   = ParagraphStyle('an', fontName='Helvetica-Bold', fontSize=8, textColor=DARK_GRAY)
    role_s    = ParagraphStyle('ar', fontName='Helvetica', fontSize=8, textColor=MID_GRAY)
    cmd_s     = ParagraphStyle('ac', fontName='Courier', fontSize=7, textColor=DARK_GRAY)

    rows = [[ Paragraph("Agent", header_s), Paragraph("Rôle", header_s), Paragraph("Sous-commandes", header_s) ]]
    for name, role, cmds, color in agents:
        rows.append([
            Paragraph(name, agent_s),
            Paragraph(role, role_s),
            Paragraph(cmds, cmd_s),
        ])

    t = Table(rows, colWidths=[4.5*cm, 4*cm, 8.5*cm])
    style = [
        ('BACKGROUND',    (0,0), (-1,0), NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',          (0,0), (-1,-1), 0.3, GRAY_LINE),
        ('LINEBELOW',     (0,0), (-1,0), 1, NAVY),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
    ]
    for i, (name, role, cmds, color) in enumerate(agents, 1):
        bg = WHITE if i % 2 == 1 else colors.HexColor("#F8FAFC")
        style.append(('BACKGROUND', (0, i), (0, i), colors.HexColor(f"{color.hexval()}")))
        style.append(('TEXTCOLOR', (0, i), (0, i), WHITE))
        style.append(('ROWBACKGROUNDS', (1, i), (-1, i), [bg]))

    t.setStyle(TableStyle(style))
    elements.append(t)
    return elements


# ── Section 3 : Patterns LLM ─────────────────────────────────────────────

def build_llm(S):
    elements = []
    elements.append(sp(14))
    elements.append(Paragraph("3. Patterns LLM", S['h1']))
    elements.append(hr(NAVY, 1))
    elements.append(sp(4))
    elements.append(Paragraph(
        "6 patterns LLM implémentés dans les deux frameworks, tous avec résilience "
        "via Circuit Breaker et fallback Ollama (offline). "
        "playwright-bdd dispose d'un pattern supplémentaire : chatStream (streaming temps-réel).",
        S['body']
    ))
    elements.append(sp(8))

    patterns = [
        ("chat",             "Génération texte libre",                 "reporting, planning, ci", GREEN,  "✅ PW · ✅ API"),
        ("chat_cot",         "Chain of Thought — raisonnement étape par étape", "bug triage, coverage", BLUE,  "✅ PW · ✅ API"),
        ("chat_structured",  "Sortie JSON schématisée (schema validation + retry)", "codegen, rca, release", TEAL, "✅ PW · ✅ API"),
        ("chat_confident",   "Avec score de confiance (threshold 0.70)", "rca critique, gate",  ORANGE, "✅ PW · ✅ API"),
        ("chat_adversarial", "Vérification contradictoire des outputs LLM", "quality verify",  RED,   "✅ PW · ✅ API"),
        ("chat_self_consistent", "Vote majoritaire N fois (self-consistency)", "release GO/NO-GO", colors.HexColor("#7C3AED"), "✅ PW · ✅ API"),
        ("chatStream",       "Streaming temps-réel (tokens au fil de l'eau)", "UI live feedback", MID_GRAY, "✅ PW · ❌ API"),
    ]

    header_s = ParagraphStyle('ph', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)
    name_s   = ParagraphStyle('pn', fontName='Courier', fontSize=8, textColor=DARK_GRAY)
    desc_s   = ParagraphStyle('pd', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY)
    use_s    = ParagraphStyle('pu', fontName='Helvetica-Oblique', fontSize=7, textColor=MID_GRAY)
    avail_s  = ParagraphStyle('pa', fontName='Helvetica-Bold', fontSize=7, textColor=DARK_GRAY, alignment=TA_CENTER)

    rows = [[ Paragraph("Pattern", header_s), Paragraph("Description", header_s), Paragraph("Utilisé dans", header_s), Paragraph("Disponibilité", header_s) ]]
    for name, desc, used, color, avail in patterns:
        rows.append([
            Paragraph(name, ParagraphStyle('pnc', fontName='Courier', fontSize=8, textColor=color)),
            Paragraph(desc, desc_s),
            Paragraph(used, use_s),
            Paragraph(avail, avail_s),
        ])

    t = Table(rows, colWidths=[4.5*cm, 6.5*cm, 3.5*cm, 2.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
        ('ALIGN',         (3,0), (3,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',          (0,0), (-1,-1), 0.3, GRAY_LINE),
        ('LINEBELOW',     (0,0), (-1,0), 1, NAVY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ('BACKGROUND',    (0,7), (-1,7), colors.HexColor("#F5F5F5")),
    ]))
    elements.append(t)
    return elements


# ── Section 4 : Prompt Templates ─────────────────────────────────────────

def build_prompts(S):
    elements = []
    elements.append(sp(14))
    elements.append(Paragraph("4. Prompt Templates", S['h1']))
    elements.append(hr(NAVY, 1))
    elements.append(sp(4))
    elements.append(Paragraph(
        "Les prompts sont versionnés (semver) et stockés dans <font name='Courier'>prompts/*.json</font>. "
        "Chaque template contient : contenu du prompt, historique des versions, métriques d'usage (calls, avg_confidence).",
        S['body']
    ))
    elements.append(sp(8))

    header_s = ParagraphStyle('tph', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)
    name_s   = ParagraphStyle('tpn', fontName='Courier', fontSize=8, textColor=DARK_GRAY)
    desc_s   = ParagraphStyle('tpd', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY)
    ag_s     = ParagraphStyle('tpa', fontName='Helvetica-Oblique', fontSize=7, textColor=MID_GRAY, alignment=TA_CENTER)
    ok_s     = ParagraphStyle('tok', fontName='Helvetica-Bold', fontSize=8, textColor=GREEN, alignment=TA_CENTER)
    miss_s   = ParagraphStyle('tmiss', fontName='Helvetica-Bold', fontSize=8, textColor=RED, alignment=TA_CENTER)

    templates = [
        ("triage_classify",   "Classifie un échec en catégorie (real_bug/flaky/env/config/test)", "bug-agent",       True),
        ("rca_analyze",       "Root cause analysis avec chaîne causale",                          "bug-agent",       True),
        ("tc_generate",       "Génère des TCs Gherkin depuis une User Story",                     "codegen-agent",   True),
        ("release_vote",      "Vote GO/NO-GO — utilisé en Self-Consistency (N votes)",             "advisor-agent",   True),
        ("qa_notify",         "Message Slack/Teams résumant le run QA",                           "reporting-agent", True),
        ("repair_patch",      "Génère un patch de code pour corriger un bug détecté",              "bug-agent",       False),
        ("predict_gate",      "Prédit si le quality gate va passer avant de lancer les tests",     "advisor-agent",   False),
        ("flaky_analyze",     "Analyse les patterns de flakiness sur N runs",                      "quality-agent",   False),
    ]

    rows = [[ Paragraph("Template", header_s), Paragraph("Description", header_s), Paragraph("Agent", header_s), Paragraph("Statut", header_s) ]]
    for name, desc, agent, exists in templates:
        status = Paragraph("✅ Créé", ok_s) if exists else Paragraph("❌ Manquant", miss_s)
        rows.append([
            Paragraph(name, name_s),
            Paragraph(desc, desc_s),
            Paragraph(agent, ag_s),
            status,
        ])

    t = Table(rows, colWidths=[4.5*cm, 7*cm, 3*cm, 2.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0), NAVY),
        ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
        ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
        ('ALIGN',         (2,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',          (0,0), (-1,-1), 0.3, GRAY_LINE),
        ('LINEBELOW',     (0,0), (-1,0), 1, NAVY),
        ('ROWBACKGROUNDS', (0,1), (-1,5), [WHITE, colors.HexColor("#F8FAFC")]),
        ('ROWBACKGROUNDS', (0,6), (-1,8), [RED_BG, colors.HexColor("#FFF0F0")]),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
    ]))
    elements.append(t)
    elements.append(sp(6))
    elements.append(Paragraph(
        "Les 3 templates manquants (en rouge) ont leurs prompts hardcodés dans les agents. "
        "Ils fonctionnent mais ne bénéficient pas du versioning ni des métriques d'usage.",
        ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=8, textColor=RED,
                       backColor=RED_BG, leftIndent=8, rightIndent=8, spaceAfter=4, leading=12)
    ))
    return elements


# ── Section 5 : Gaps & Score ─────────────────────────────────────────────

def build_gaps(S):
    elements = []
    elements.append(sp(14))
    elements.append(Paragraph("5. Gaps & Score de Maturité IA", S['h1']))
    elements.append(hr(NAVY, 1))
    elements.append(sp(8))

    # Score bars
    elements.append(Paragraph("Score par composant", S['h2']))
    elements.append(sp(4))
    score_rows = [
        ("Structure agentique (10 agents, CB, memory, tracer)", 100, GREEN),
        ("agents.md + RAG + documentation",                     100, GREEN),
        ("Patterns LLM (6/7 identiques entre frameworks)",       92, GREEN),
        ("Prompt templates (5/8 créés)",                         62, ORANGE),
        ("Câblage PromptStore dans les agents",                  10, RED),
    ]
    elements.extend(progress_table(score_rows, S))
    elements.append(sp(10))

    # Score global
    score_data = [[
        Paragraph("Score Global IA", ParagraphStyle('sg', fontName='Helvetica-Bold', fontSize=14, textColor=NAVY)),
        Paragraph("73 / 100", ParagraphStyle('sc', fontName='Helvetica-Bold', fontSize=26, textColor=ORANGE, alignment=TA_RIGHT)),
    ]]
    score_t = Table(score_data, colWidths=[10*cm, 7*cm])
    score_t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), ORANGE_BG),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
        ('BOX', (0,0), (-1,-1), 1.5, ORANGE),
    ]))
    elements.append(score_t)
    elements.append(sp(12))

    # Gap 1
    elements.append(Paragraph("Gap 1 — 3 Prompt Templates manquants", S['h2']))
    elements.append(Paragraph(
        "Les agents <font name='Courier'>bug-agent</font>, <font name='Courier'>advisor-agent</font> et "
        "<font name='Courier'>quality-agent</font> ont leurs prompts critiques hardcodés dans le code. "
        "Ils fonctionnent correctement mais ne bénéficient pas du versioning semver ni des métriques d'usage.",
        S['body']
    ))
    elements.append(sp(4))

    gap1_data = [
        [Paragraph("Template", ParagraphStyle('g1h', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
         Paragraph("Agent concerné", ParagraphStyle('g1h', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)),
         Paragraph("Prompt actuel", ParagraphStyle('g1h', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE))],
        [Paragraph("repair_patch", ParagraphStyle('g1n', fontName='Courier', fontSize=8, textColor=RED)),
         Paragraph("bug-agent — cmd repair", ParagraphStyle('g1d', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY)),
         Paragraph("Inline, ~12 lignes, génère PATCH_SCHEMA JSON", ParagraphStyle('g1c', fontName='Helvetica', fontSize=8, textColor=MID_GRAY))],
        [Paragraph("predict_gate", ParagraphStyle('g1n', fontName='Courier', fontSize=8, textColor=RED)),
         Paragraph("advisor-agent — cmd predict", ParagraphStyle('g1d', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY)),
         Paragraph("Inline, ~10 lignes, génère PREDICT_SCHEMA JSON", ParagraphStyle('g1c', fontName='Helvetica', fontSize=8, textColor=MID_GRAY))],
        [Paragraph("flaky_analyze", ParagraphStyle('g1n', fontName='Courier', fontSize=8, textColor=RED)),
         Paragraph("quality-agent — cmd flaky", ParagraphStyle('g1d', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY)),
         Paragraph("Inline, ~8 lignes, analyse de patterns multi-runs", ParagraphStyle('g1c', fontName='Helvetica', fontSize=8, textColor=MID_GRAY))],
    ]
    g1t = Table(gap1_data, colWidths=[4*cm, 5.5*cm, 7.5*cm])
    g1t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), RED),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [RED_BG, colors.HexColor("#FFF5F5")]),
        ('GRID', (0,0), (-1,-1), 0.3, GRAY_LINE),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(g1t)
    elements.append(sp(12))

    # Gap 2
    elements.append(Paragraph("Gap 2 — PromptStore non câblé dans les agents", S['h2']))
    elements.append(Paragraph(
        "Le <font name='Courier'>PromptStore</font> (versioning semver, métriques, rollback) est implémenté "
        "dans les deux frameworks mais n'est pas consommé par les agents. "
        "Résultat : les métriques <font name='Courier'>calls</font> et <font name='Courier'>avg_confidence</font> "
        "restent à 0 dans tous les JSON de prompts.",
        S['body']
    ))
    elements.append(sp(6))
    elements.append(Paragraph("Aujourd'hui (prompts inline) :", S['h3']))
    elements.append(Paragraph(
        'messages = [{"role": "user", "content": "Tu es un expert QA...\\nTest: {test_name}..."}]\n'
        'result = llm.chat_structured(messages, TRIAGE_SCHEMA)',
        S['code']
    ))
    elements.append(Paragraph("Ce qu'il faudrait (prompts depuis store) :", S['h3']))
    elements.append(Paragraph(
        'ps       = PromptStore()\n'
        'template = ps.get("triage_classify")          # charge depuis prompts/triage_classify.json\n'
        'content  = template.format(test_name=..., error_message=...)\n'
        'result   = llm.chat_structured([{"role": "user", "content": content}], TRIAGE_SCHEMA)\n'
        'ps.record_usage("triage_classify", confidence=result.get("confidence", 0))',
        S['code']
    ))

    return elements


# ── Section 6 : Plan d'action ────────────────────────────────────────────

def build_action_plan(S):
    elements = []
    elements.append(sp(14))
    elements.append(Paragraph("6. Plan d'action pour atteindre 100%", S['h1']))
    elements.append(hr(NAVY, 1))
    elements.append(sp(8))

    actions = [
        ("1", "Créer les 3 templates manquants",
         "Créer repair_patch.json, predict_gate.json, flaky_analyze.json "
         "dans prompts/ des deux frameworks. Suivre le même schéma que les 5 existants.",
         "30 min", GREEN, "Facile"),
        ("2", "Câbler PromptStore dans les agents",
         "Modifier bug-agent, advisor-agent et quality-agent pour charger les prompts "
         "via PromptStore().get() au lieu des strings inline. Ajouter record_usage() après chaque appel LLM.",
         "2–3h", ORANGE, "Moyen"),
        ("3", "Ajouter chatStream à pytest-bdd",
         "Porter llm.chatStream() de playwright-bdd vers llm.py (Python). "
         "Utiliser le streaming Groq SDK pour les outputs temps-réel dans terminal.",
         "1h", TEAL, "Facile"),
    ]

    header_s = ParagraphStyle('ah', fontName='Helvetica-Bold', fontSize=8, textColor=WHITE)
    for num, title, desc, effort, color, diff in actions:
        block_data = [[
            Paragraph(f"#{num}", ParagraphStyle('an', fontName='Helvetica-Bold', fontSize=14, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph(title, ParagraphStyle('at', fontName='Helvetica-Bold', fontSize=10, textColor=NAVY)),
            Paragraph(f"Effort : {effort}  |  Difficulté : {diff}",
                      ParagraphStyle('ae', fontName='Helvetica', fontSize=7, textColor=MID_GRAY)),
        ],[
            Paragraph("", S['body']),
            Paragraph(desc, ParagraphStyle('ad', fontName='Helvetica', fontSize=8, textColor=DARK_GRAY, leading=12)),
            Paragraph("", S['body']),
        ]]
        bt = Table(block_data, colWidths=[1.2*cm, 11.5*cm, 4.3*cm])
        bt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), color),
            ('BACKGROUND', (1,0), (-1,0), LIGHT_BLUE),
            ('BACKGROUND', (1,1), (-1,1), WHITE),
            ('SPAN', (0,0), (0,1)),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('VALIGN', (0,0), (0,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('BOX', (0,0), (-1,-1), 1, GRAY_LINE),
            ('LINEBELOW', (0,0), (-1,0), 0.5, GRAY_LINE),
        ]))
        elements.append(bt)
        elements.append(sp(6))

    elements.append(sp(8))
    # Projection score
    proj_data = [[
        Paragraph("Score actuel", ParagraphStyle('pa', fontName='Helvetica-Bold', fontSize=10, textColor=ORANGE, alignment=TA_CENTER)),
        Paragraph("→", ParagraphStyle('arr', fontName='Helvetica-Bold', fontSize=16, textColor=MID_GRAY, alignment=TA_CENTER)),
        Paragraph("Après action #1", ParagraphStyle('p1', fontName='Helvetica-Bold', fontSize=10, textColor=TEAL, alignment=TA_CENTER)),
        Paragraph("→", ParagraphStyle('arr', fontName='Helvetica-Bold', fontSize=16, textColor=MID_GRAY, alignment=TA_CENTER)),
        Paragraph("Après actions #1+2+3", ParagraphStyle('p2', fontName='Helvetica-Bold', fontSize=10, textColor=GREEN, alignment=TA_CENTER)),
    ],[
        Paragraph("73 / 100", ParagraphStyle('pv', fontName='Helvetica-Bold', fontSize=20, textColor=ORANGE, alignment=TA_CENTER)),
        Paragraph("", S['body']),
        Paragraph("83 / 100", ParagraphStyle('pv', fontName='Helvetica-Bold', fontSize=20, textColor=TEAL, alignment=TA_CENTER)),
        Paragraph("", S['body']),
        Paragraph("100 / 100", ParagraphStyle('pv', fontName='Helvetica-Bold', fontSize=20, textColor=GREEN, alignment=TA_CENTER)),
    ]]
    pt = Table(proj_data, colWidths=[3.8*cm, 1*cm, 3.8*cm, 1*cm, 3.8*cm])
    pt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), ORANGE_BG),
        ('BACKGROUND', (2,0), (2,-1), LIGHT_BLUE),
        ('BACKGROUND', (4,0), (4,-1), GREEN_BG),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (0,-1), 1, ORANGE),
        ('BOX', (2,0), (2,-1), 1, TEAL),
        ('BOX', (4,0), (4,-1), 1.5, GREEN),
    ]))
    elements.append(pt)
    return elements


# ── Build PDF ─────────────────────────────────────────────────────────────

def main():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="Audit IA des Frameworks QA",
        author="Faicel Ghanem — QA Automation Architect",
    )

    S = make_styles()
    story = []

    story.extend(build_cover(S))
    story.extend(build_overview(S))
    story.extend(build_agents(S))
    story.extend(build_llm(S))
    story.extend(build_prompts(S))
    story.extend(build_gaps(S))
    story.extend(build_action_plan(S))

    doc.build(story)
    print(f"PDF généré : {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    main()
