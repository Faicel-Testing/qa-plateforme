# ============================================
# API Generate Agent — Génère les cas de test depuis la spec extraite
# ============================================
# Rôle unique : lire docs/spec-output.json (produit par api-spec-agent)
# et générer les fichiers test_*.py correspondants dans tests/.
#
# Usage:
#   python agents/api-generate-agent.py
#   python agents/api-generate-agent.py --input=docs/spec-output.json
#   python agents/api-generate-agent.py --dry-run
#
# Output:
#   tests/test_<endpoint>.py  ←  un fichier par user story
# ============================================
