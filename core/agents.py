import json
import re
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OLLAMA_BASE_URL = "http://localhost:11434"

def _extract_json_obj(text: str):
    """
    Extract first JSON object from a string.
    Works even if model adds extra text before/after or omits the opening brace.
    """
    if not (text and text.strip()):
        raise ValueError("No JSON object found in model output.")
    text = text.strip()
    
    # 1) Try finding a markdown block
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2) Normal: find {...}
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
            
    # 3) Model output sometimes starts with newline + "risk_score": ... (missing leading {)
    if text.lstrip().startswith('"'):
        try:
            return json.loads("{" + text.lstrip())
        except json.JSONDecodeError:
            pass
            
    # 4) Try cleanup of common issues (trailing commas)
    try:
        # Very simple cleanup: remove trailing commas before closing braces
        cleaned = re.sub(r",\s*\}", "}", text)
        cleaned = re.sub(r",\s*\]", "]", cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"Could not parse JSON from: {text[:100]}...")

def _parse_ollama_response_body(text: str) -> str:
    """
    Parse Ollama response body into model output text.
    Handles: single JSON, NDJSON (streamed lines), or raw model output.
    """
    text = (text or "").strip()
    if not text:
        return ""

    # 1) Single JSON object: {"response": "...", "done": true, ...}
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "response" in data:
            return (data.get("response") or "").strip()
    except (json.JSONDecodeError, TypeError):
        pass

    # 2) NDJSON: one JSON object per line
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict) and "response" in data:
                out.append(data.get("response") or "")
        except (json.JSONDecodeError, TypeError):
            continue
    if out:
        return "\n".join(out).strip()

    # 3) Raw model output (no API envelope)
    return text


def _ollama_generate(prompt: str, model: str, temperature: float = 0.2, json_mode: bool = False) -> str:
    """Call Ollama /api/generate with stream=False. Parses response robustly."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    # Newer Ollama versions support "format": "json"
    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            "Cannot reach Ollama. Is it running? Start it with: ollama serve"
        ) from e
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 404:
            raise RuntimeError(
                f"Model '{model}' not found. Pull it with: ollama pull {model}"
            ) from e
        raise RuntimeError(
            f"Ollama returned {resp.status_code}. {getattr(resp, 'text', '')}"
        ) from e

    return _parse_ollama_response_body(resp.text)


RISK_PROMPT = """
You are a contract risk reviewer for an SMB.
{playbook_instructions}

Use ONLY the provided clauses as evidence. If evidence is not present, do NOT invent it.

Return ONLY a valid JSON object (no markdown fences, no commentary).
Schema:
{{
  "risk_score": number,
  "red_flags": [
    {{
      "category": string,
      "severity": "LOW"|"MED"|"HIGH"|"CRITICAL",
      "evidence_quote": string,
      "why_risky": string,
      "suggested_fallback": string
    }}
  ]
}}

CLAUSES:
{clauses}
"""

SUMMARY_PROMPT = """
Summarize key contract terms in plain English for an SMB buyer. Use only provided clauses.
Include: term/renewal, termination, liability cap, indemnity, data/privacy, payment, SLA.
CLAUSES:
{clauses}
Return bullet points.
"""

NEGOTIATION_PROMPT = """
Write a professional negotiation email to the vendor requesting changes based on the risks found.
Use the risks below. Include:
- Short intro
- Requested changes (bullets)
- Proposed fallback language suggestions (bullets)
RISKS JSON:
{risks_json}
"""

CHAT_PROMPT = """
You are ClauseCopilot, a helpful legal AI assistant.
Answer the user's question based ONLY on the provided contract context.
If the answer is not in the context, say "I cannot find that information in the contract."
Do not provide general legal advice.

Context from Contract:
{context}

Chat History:
{history}

User Question: {question}
"""

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(ValueError))
def run_risk_review(model: str, clauses_text: str, temperature: float = 0.2, playbook_rules: str = None) -> str:
    """
    Run risk review with retries for JSON parsing failures.
    """
    instructions = playbook_rules if playbook_rules else "Identify risks related to: Termination, Liability, Indemnity, Auto-renewal."
    prompt = RISK_PROMPT.format(playbook_instructions=instructions, clauses=clauses_text)
    
    # Try to use JSON mode if possible, but regular mode with extraction logic is often safer for diverse models
    raw_output = _ollama_generate(prompt, model, temperature=temperature, json_mode=True)
    
    # Validate it parses
    try:
        _extract_json_obj(raw_output)
        return raw_output # Return the raw string, but we know it's valid JSON
    except ValueError:
        # If strict JSON mode failed to produce parsable JSON, try without JSON mode (sometimes models hallucinate in JSON mode)
        raw_output = _ollama_generate(prompt, model, temperature=temperature, json_mode=False)
        _extract_json_obj(raw_output) # Will raise ValueError to trigger retry if still bad
        return raw_output


def run_summary(model: str, clauses_text: str, temperature: float = 0.2) -> str:
    prompt = SUMMARY_PROMPT.format(clauses=clauses_text)
    return _ollama_generate(prompt, model, temperature=temperature)


def run_negotiation(model: str, risks_json: str, temperature: float = 0.2) -> str:
    prompt = NEGOTIATION_PROMPT.format(risks_json=risks_json)
    return _ollama_generate(prompt, model, temperature=temperature)

def run_chat(model: str, context: str, history: str, question: str, temperature: float = 0.1) -> str:
    prompt = CHAT_PROMPT.format(context=context, history=history, question=question)
    return _ollama_generate(prompt, model, temperature=temperature)