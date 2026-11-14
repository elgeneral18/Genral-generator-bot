# ==========================================================
#  DARK ELGENERAL — Gemini client
#  Retries • thinking-safe parsing • forced JSON output
#  © 2026 Dark Elgeneral • Developed by Adam Elgeneral
# ==========================================================

import time

import requests

import config
from utils import log

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"
URL = f"{BASE_URL}{config.GEMINI_MODEL}:generateContent"

RETRY_STATUS = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 3
TOKEN_STEPS = (config.GEMINI_MAX_OUTPUT_TOKENS, 32768, 16384)


def _headers():
    return {"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY}


def _request(prompt, max_tokens):
    return requests.post(
        URL,
        headers=_headers(),
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        },
        timeout=300,
    )


def _json(response):
    try:
        return response.json()
    except ValueError:
        return {}


def check_model():
    """Cheap start-up check (no tokens used). Returns (ok, message)."""
    try:
        response = requests.get(
            f"{BASE_URL}{config.GEMINI_MODEL}", headers=_headers(), timeout=20
        )
        if response.status_code == 200:
            return True, f"Gemini OK ({config.GEMINI_MODEL})"
        message = _json(response).get("error", {}).get("message", response.text[:200])
        return False, f"Gemini check failed ({response.status_code}): {message}"
    except requests.exceptions.RequestException as error:
        return False, f"Gemini unreachable: {error}"


def generate(prompt):
    """Send a prompt to Gemini. Returns {'success': bool, 'text'|'error': str}."""
    try:
        response = None
        data = {}

        for max_tokens in TOKEN_STEPS:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                response = _request(prompt, max_tokens)
                data = _json(response)

                if response.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS:
                    log.warning("Gemini %s — retry %s/%s", response.status_code, attempt, MAX_ATTEMPTS)
                    time.sleep(3 * attempt)
                    continue
                break

            # Model does not accept this output limit -> try a smaller one
            message = data.get("error", {}).get("message", "")
            if response.status_code == 400 and "maxoutputtokens" in message.lower().replace(" ", ""):
                log.warning("maxOutputTokens=%s rejected, trying a lower value", max_tokens)
                continue
            break

        if response.status_code != 200:
            message = data.get("error", {}).get("message", response.text[:300])
            return {"success": False, "error": f"API Error ({response.status_code}): {message}"}

        candidates = data.get("candidates")
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
            return {"success": False, "error": f"No candidates returned. Block reason: {reason}"}

        candidate = candidates[0]
        finish = candidate.get("finishReason", "")
        if finish and finish not in ("STOP", "MAX_TOKENS"):
            return {"success": False, "error": f"Generation stopped: {finish}"}

        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and not part.get("thought")
        )
        if not text.strip():
            return {"success": False, "error": "Empty text content from model."}

        if finish == "MAX_TOKENS":
            log.warning("Gemini hit MAX_TOKENS — output may be truncated")

        return {"success": True, "text": text, "truncated": finish == "MAX_TOKENS"}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out."}
    except requests.exceptions.RequestException as error:
        return {"success": False, "error": f"Network error: {error}"}
    except Exception as error:  # pragma: no cover
        return {"success": False, "error": str(error)}
