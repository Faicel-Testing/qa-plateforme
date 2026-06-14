# ============================================================
# LLM — Module partagé Groq / Ollama (Mobile Framework)
# ============================================================
# Identique au module api-pytest-framework.
# Groq = primaire | Ollama = fallback local.
# ============================================================

import os, json, time, re
import requests
from dotenv import load_dotenv

try:
    import circuit_breaker as _cb
except ImportError:
    _cb = None

load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3")

MODEL = GROQ_MODEL if GROQ_API_KEY else OLLAMA_MODEL

MAX_RETRIES = 3
RETRY_DELAY = 2


def chat(messages: list, model: str = None, temperature: float = 0.2) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _resilient_call(messages, model, temperature)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"LLM inaccessible après {MAX_RETRIES} tentatives : {e}")
            time.sleep(RETRY_DELAY * attempt)


def chat_cot(messages: list, model: str = None) -> str:
    cot_instruction = {
        "role": "system",
        "content": (
            "Tu es un expert QA Mobile (Appium/Android). Avant de répondre, raisonne en 3 étapes :\n"
            "Étape 1 — Analyse les données brutes fournies.\n"
            "Étape 2 — Identifie les patterns ou anomalies.\n"
            "Étape 3 — Conclus avec une réponse précise et vérifiable.\n"
            "Ne saute aucune étape. Écris 'ÉTAPE 1:', 'ÉTAPE 2:', 'CONCLUSION:' explicitement."
        )
    }
    return chat([cot_instruction] + messages, model=model, temperature=0.1)


def chat_structured(messages: list, schema: dict, model: str = None) -> dict:
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


def chat_confident(messages: list, model: str = None) -> dict:
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


def chat_adversarial(original_output: str, context: str, domain: str = "QA Mobile") -> dict:
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
            f"Sois strict : une seule erreur = INVALID. Si tout correspond = VALID."
        )
    }]
    return chat_structured(messages, schema)


def chat_self_consistent(messages: list, schema: dict, verdict_key: str = "verdict",
                          n: int = 3, model: str = None) -> dict:
    temperatures = [0.1, 0.4, 0.7, 0.2, 0.5][:n]
    responses = []

    for i, temp in enumerate(temperatures):
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        struct_sys = {
            "role": "system",
            "content": f"Tu dois répondre UNIQUEMENT avec un JSON valide.\nSchema :\n{schema_str}\nPas de markdown, juste le JSON brut."
        }
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = chat([struct_sys] + messages, model=model, temperature=temp)
                parsed = _extract_json(raw)
                if parsed is not None:
                    parsed["_temp"] = temp
                    parsed["_call"] = i + 1
                    responses.append(parsed)
                    break
            except Exception:
                if attempt == MAX_RETRIES:
                    responses.append({verdict_key: "ERROR", "_call": i + 1})
                time.sleep(1)

    votes = {}
    for r in responses:
        v = str(r.get(verdict_key, "UNKNOWN")).upper()
        votes[v] = votes.get(v, 0) + 1

    majority_verdict = max(votes, key=votes.get) if votes else "UNKNOWN"
    majority_count   = votes.get(majority_verdict, 0)
    agreement_rate   = majority_count / len(responses) if responses else 0.0

    minority_reasons = [
        r.get("reasoning", r.get("summary", ""))
        for r in responses
        if str(r.get(verdict_key, "")).upper() != majority_verdict
    ]

    return {
        "majority_verdict": majority_verdict,
        "agreement_rate":   round(agreement_rate, 2),
        "is_unanimous":     agreement_rate == 1.0,
        "votes":            votes,
        "responses":        responses,
        "minority_reasons": minority_reasons,
    }


# ── Helpers internes ───────────────────────────────────────────────────────

def _groq_chat(messages: list, model: str, temperature: float = 0.2) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": temperature}
    resp = requests.post(GROQ_BASE_URL, json=payload, headers=headers, timeout=60, verify=False)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _ollama_chat(messages: list, model: str) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _resilient_call(messages: list, model: str = None,
                    temperature: float = 0.2, fn_name: str = "chat") -> str:
    if GROQ_API_KEY:
        try:
            return _groq_chat(messages, model or GROQ_MODEL, temperature)
        except Exception:
            pass

    try:
        result = _ollama_chat(messages, model or OLLAMA_MODEL)
        print(f"  \033[33m[FALLBACK] Ollama utilisé à la place de Groq\033[0m")
        return result
    except Exception:
        pass

    raise RuntimeError("LLM entièrement indisponible (Groq et Ollama).")


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def assert_running():
    try:
        chat([{"role": "user", "content": "ping"}])
        print(f"  LLM actif : {MODEL}")
    except Exception as e:
        raise RuntimeError(f"LLM inaccessible ({MODEL}): {e}")
