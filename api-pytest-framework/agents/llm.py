# ============================================================
# LLM — Module partagé Groq / Ollama
# ============================================================
# Norme : OpenAI-compatible API (Groq = /openai/v1/)
# Capacités :
#   chat()             → appel simple
#   chat_cot()         → Chain of Thought (raisonnement avant réponse)
#   chat_structured()  → Structured Output (JSON garanti)
#   chat_confident()   → retourne réponse + score de confiance
# ============================================================

import os, json, time, re
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3")

MODEL = GROQ_MODEL if GROQ_API_KEY else OLLAMA_MODEL

MAX_RETRIES = 3
RETRY_DELAY = 2


# ── Appel de base avec retry ───────────────────────────────────────────────

def chat(messages: list[dict], model: str = None, temperature: float = 0.2) -> str:
    """Appel LLM simple — retourne le texte de la réponse."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if GROQ_API_KEY:
                return _groq_chat(messages, model or GROQ_MODEL, temperature)
            return _ollama_chat(messages, model or OLLAMA_MODEL)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"LLM inaccessible après {MAX_RETRIES} tentatives : {e}")
            time.sleep(RETRY_DELAY * attempt)


# ── Chain of Thought ───────────────────────────────────────────────────────

def chat_cot(messages: list[dict], model: str = None) -> str:
    """Chain of Thought — force le LLM à raisonner étape par étape.
    Réduit les hallucinations sur les analyses complexes."""
    cot_instruction = {
        "role": "system",
        "content": (
            "Tu es un expert QA. Avant de répondre, raisonne en 3 étapes :\n"
            "Étape 1 — Analyse les données brutes fournies.\n"
            "Étape 2 — Identifie les patterns ou anomalies.\n"
            "Étape 3 — Conclus avec une réponse précise et vérifiable.\n"
            "Ne saute aucune étape. Écris 'ÉTAPE 1:', 'ÉTAPE 2:', 'CONCLUSION:' explicitement."
        )
    }
    return chat([cot_instruction] + messages, model=model, temperature=0.1)


# ── Structured Output ──────────────────────────────────────────────────────

def chat_structured(messages: list[dict], schema: dict, model: str = None) -> dict:
    """Structured Output — force le LLM à retourner un JSON conforme au schema.
    Évite le parsing fragile du texte libre."""
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    struct_instruction = {
        "role": "system",
        "content": (
            f"Tu dois répondre UNIQUEMENT avec un JSON valide, sans texte avant ni après.\n"
            f"Le JSON doit respecter exactement ce schema :\n{schema_str}\n"
            f"Pas de markdown, pas de ```json, juste le JSON brut."
        )
    }
    for attempt in range(1, MAX_RETRIES + 1):
        raw = chat([struct_instruction] + messages, model=model, temperature=0.0)
        parsed = _extract_json(raw)
        if parsed is not None:
            return parsed
        if attempt < MAX_RETRIES:
            time.sleep(1)
    raise ValueError(f"LLM n'a pas retourné un JSON valide après {MAX_RETRIES} tentatives.\nRéponse : {raw[:200]}")


# ── Confidence Scoring ─────────────────────────────────────────────────────

def chat_confident(messages: list[dict], model: str = None) -> dict:
    """Retourne la réponse avec un score de confiance (0.0 à 1.0).
    Si confidence < 0.7 → signale une révision humaine nécessaire."""
    schema = {
        "response":           "string — ta réponse principale",
        "confidence":         "float entre 0.0 et 1.0",
        "reasoning":          "string — pourquoi tu es confiant ou non",
        "needs_human_review": "boolean — true si confidence < 0.7"
    }
    result = chat_structured(messages, schema, model=model)
    if isinstance(result.get("confidence"), (int, float)):
        result["needs_human_review"] = result["confidence"] < 0.7
    return result


# ── Adversarial (pour vérification) ───────────────────────────────────────

def chat_adversarial(original_output: str, context: str, domain: str = "QA") -> dict:
    """Prompt adversarial — cherche à RÉFUTER le résultat d'un autre agent.
    Utilisé par verifier-agent pour détecter les hallucinations."""
    schema = {
        "verdict":    "VALID | INVALID | WARNING",
        "confidence": "float entre 0.0 et 1.0",
        "issues":     ["liste des problèmes trouvés (vide si VALID)"],
        "summary":    "string — explication courte du verdict"
    }
    messages = [{
        "role": "user",
        "content": (
            f"Tu es un expert {domain} adversarial. Ton rôle est de RÉFUTER le résultat suivant.\n\n"
            f"RÉSULTAT À VÉRIFIER :\n{original_output}\n\n"
            f"DONNÉES BRUTES DE RÉFÉRENCE :\n{context}\n\n"
            f"Instructions :\n"
            f"- Compare le résultat avec les données brutes\n"
            f"- Cherche les incohérences, erreurs, ou informations inventées\n"
            f"- Sois strict : une seule erreur = INVALID\n"
            f"- Si tout correspond aux données brutes = VALID\n"
            f"- Si mineur = WARNING\n"
        )
    }]
    return chat_structured(messages, schema)


# ── Helpers internes ───────────────────────────────────────────────────────

def _groq_chat(messages: list[dict], model: str, temperature: float = 0.2) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}
    resp = requests.post(GROQ_BASE_URL, json=payload, headers=headers,
                         timeout=60, verify=False)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _ollama_chat(messages: list[dict], model: str) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _extract_json(text: str):
    """Extrait un JSON depuis une réponse LLM (tolère le markdown)."""
    text = text.strip()
    # Enlève ```json ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Tente d'extraire le premier objet JSON du texte
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def assert_running():
    """Vérifie que le LLM est accessible."""
    try:
        chat([{"role": "user", "content": "ping"}])
        print(f"  LLM actif : {MODEL}")
    except Exception as e:
        raise RuntimeError(f"LLM inaccessible ({MODEL}): {e}")
