# ============================================
# API Spec Agent — Lit la spec et extrait les user stories
# ============================================
# Rôle unique : analyser un fichier de spec (Markdown / OpenAPI / texte)
# et produire un fichier JSON structuré consommable par api-generate-agent.
#
# Usage:
#   python agents/api-spec-agent.py --file=specs/booking-api.md
#   python agents/api-spec-agent.py --file=specs/booking-api.md --dry-run
#
# Output:
#   docs/spec-output.json  ←  liste des endpoints + user stories extraits
# ============================================
