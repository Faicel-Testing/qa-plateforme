# ============================================
# LLM — Module partagé Groq / Ollama
# ============================================
# Détecte automatiquement Groq (si GROQ_API_KEY) ou Ollama (local).
# Tous les agents importent ce module pour appeler le LLM.
#
# Usage:
#   from agents.llm import chat, MODEL
#   response = chat([{"role": "user", "content": "..."}])
# ============================================

import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3")

MODEL = GROQ_MODEL if GROQ_API_KEY else OLLAMA_MODEL


def chat(messages: list[dict], model: str = None) -> str:
    """Envoie les messages au LLM et retourne le texte de la réponse."""
    if GROQ_API_KEY:
        return _groq_chat(messages, model or GROQ_MODEL)
    return _ollama_chat(messages, model or OLLAMA_MODEL)


def _groq_chat(messages: list[dict], model: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    resp = requests.post(GROQ_BASE_URL, json=payload, headers=headers, timeout=60,
                         verify=False)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _ollama_chat(messages: list[dict], model: str) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def assert_running():
    """Vérifie que le LLM est accessible. Lève une exception sinon."""
    try:
        chat([{"role": "user", "content": "ping"}])
        print(f"✅ LLM actif : {MODEL}")
    except Exception as e:
        raise RuntimeError(f"❌ LLM inaccessible ({MODEL}): {e}")
