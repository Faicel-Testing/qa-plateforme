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

try:
    import tracer as _tracer
except ImportError:
    _tracer = None

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


# ── Appel de base avec retry ───────────────────────────────────────────────

def chat(messages: list[dict], model: str = None, temperature: float = 0.2) -> str:
    """Appel LLM simple — retourne le texte de la réponse."""
    prompt = " ".join(m.get("content", "") for m in messages)
    span = _tracer.Span("chat", prompt, model or MODEL) if _tracer else None
    if span: span.__enter__()
    retries = 0
    try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = _resilient_call(messages, model, temperature, fn_name="chat")
                if span: span.response = result
                return result
            except Exception as e:
                retries = attempt - 1
                if attempt == MAX_RETRIES:
                    if span: span.error = str(e); span.retries = retries
                    raise RuntimeError(f"LLM inaccessible après {MAX_RETRIES} tentatives : {e}")
                time.sleep(RETRY_DELAY * attempt)
    finally:
        if span: span.retries = retries; span.__exit__(None, None, None)


# ── Chain of Thought ───────────────────────────────────────────────────────

def chat_cot(messages: list[dict], model: str = None) -> str:
    """Chain of Thought — force le LLM à raisonner étape par étape.
    Réduit les hallucinations sur les analyses complexes."""
    prompt = " ".join(m.get("content", "") for m in messages)
    span = _tracer.Span("chat_cot", prompt, model or MODEL) if _tracer else None
    if span: span.__enter__()
    try:
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
        result = chat([cot_instruction] + messages, model=model, temperature=0.1)
        if span: span.response = result
        return result
    finally:
        if span: span.__exit__(None, None, None)


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
        # Injecte le score de confiance dans la dernière trace
        if _tracer and os.path.exists(_tracer.TRACE_FILE):
            pass  # la trace est déjà écrite par chat_structured
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


# ── Self-Consistency ──────────────────────────────────────────────────────

def chat_self_consistent(
    messages: list[dict],
    schema: dict,
    verdict_key: str = "verdict",
    n: int = 3,
    model: str = None,
) -> dict:
    """Self-Consistency — pose la même question N fois, retourne le vote majoritaire.
    Réduit les hallucinations sur les décisions critiques (go/no-go, sévérité...).

    Args:
        messages    : prompt à répéter
        schema      : schéma Structured Output pour chaque réponse
        verdict_key : clé JSON dont on vote la valeur majoritaire (ex: "verdict")
        n           : nombre d'appels (3 par défaut)

    Retourne :
        {
          "majority_verdict" : valeur gagnante du vote,
          "agreement_rate"   : 0.0–1.0 (1.0 = unanime),
          "is_unanimous"     : bool,
          "votes"            : {"OUI": 2, "NON": 1},
          "responses"        : [liste des N réponses complètes],
          "minority_reasons" : [raisons des votes minoritaires]
        }
    """
    # Températures variées pour obtenir de la diversité entre appels
    temperatures = [0.1, 0.4, 0.7, 0.2, 0.5][:n]
    responses = []

    span = _tracer.Span("chat_self_consistent",
                        " ".join(m.get("content","") for m in messages),
                        model or MODEL) if _tracer else None
    if span: span.__enter__()

    try:
        for i, temp in enumerate(temperatures):
            schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
            struct_sys = {
                "role": "system",
                "content": (
                    f"Tu dois répondre UNIQUEMENT avec un JSON valide.\n"
                    f"Schema :\n{schema_str}\n"
                    f"Pas de markdown, juste le JSON brut."
                )
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

        # Décompte des votes
        votes = {}
        for r in responses:
            v = str(r.get(verdict_key, "UNKNOWN")).upper()
            votes[v] = votes.get(v, 0) + 1

        majority_verdict = max(votes, key=votes.get) if votes else "UNKNOWN"
        majority_count   = votes.get(majority_verdict, 0)
        agreement_rate   = majority_count / len(responses) if responses else 0.0

        # Raisons des votes minoritaires
        minority_reasons = [
            r.get("reasoning", r.get("summary", ""))
            for r in responses
            if str(r.get(verdict_key,"")).upper() != majority_verdict
               and r.get("reasoning") or r.get("summary")
        ]

        result = {
            "majority_verdict": majority_verdict,
            "agreement_rate":   round(agreement_rate, 2),
            "is_unanimous":     agreement_rate == 1.0,
            "votes":            votes,
            "responses":        responses,
            "minority_reasons": minority_reasons,
        }
        if span: span.response = majority_verdict; span.confidence = agreement_rate
        return result

    finally:
        if span: span.__exit__(None, None, None)


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


def _resilient_call(messages: list[dict], model: str = None,
                    temperature: float = 0.2, fn_name: str = "chat") -> str:
    """
    Appel LLM avec Circuit Breaker + Fallback chain :
      1. Groq  (primaire)
      2. Ollama (fallback local)
      3. Cache  (dernière réponse similaire)
      4. Default (réponse de secours)
    Transparent pour tous les agents — remplace les appels directs à Groq/Ollama.
    """
    cb = _cb.get_circuit_breaker() if _cb else None

    # ── Étape 1 : Groq (primaire) ──────────────────────────────────
    if GROQ_API_KEY:
        if cb and not cb.allow_request():
            pass  # Circuit ouvert → passer directement au fallback
        else:
            try:
                result = _groq_chat(messages, model or GROQ_MODEL, temperature)
                if cb:
                    cb.record_success()
                    s = cb._state["stats"]
                    s["groq_calls"] = s.get("groq_calls", 0) + 1
                    _cb._save_state(cb._state)
                if _cb:
                    _cb.cache_set(messages, result)
                return result
            except Exception as e:
                if cb:
                    cb.record_failure(e)

    # ── Étape 2 : Ollama (fallback local) ─────────────────────────
    try:
        result = _ollama_chat(messages, model or OLLAMA_MODEL)
        if cb:
            s = cb._state["stats"]
            s["ollama_calls"] = s.get("ollama_calls", 0) + 1
            _cb._save_state(cb._state)
        print(f"  {__import__('os').linesep.strip()}"
              f"\033[33m[FALLBACK] Ollama utilisé à la place de Groq\033[0m")
        if _cb:
            _cb.cache_set(messages, result)
        return result
    except Exception:
        pass

    # ── Étape 3 : Cache ───────────────────────────────────────────
    if _cb:
        cached = _cb.cache_get(messages)
        if cached:
            if cb:
                s = cb._state["stats"]
                s["cache_hits"] = s.get("cache_hits", 0) + 1
                _cb._save_state(cb._state)
            print(f"  \033[33m[FALLBACK] Réponse en cache utilisée\033[0m")
            return cached

    # ── Étape 4 : Réponse par défaut ──────────────────────────────
    if cb:
        s = cb._state["stats"]
        s["default_hits"] = s.get("default_hits", 0) + 1
        _cb._save_state(cb._state)
    default = _cb.get_default_response(fn_name) if _cb else "LLM unavailable."
    print(f"  \033[31m[FALLBACK] Réponse par défaut — LLM entièrement indisponible\033[0m")
    return default


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
