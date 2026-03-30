import json
import re
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OLLAMA_BASE_URL = "http://localhost:11434"

# Recommended / fallback model list — shown when Ollama is unreachable
FALLBACK_MODELS = [
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "qwen2.5:32b",
    "llama3.3:70b",
    "llama3.1:70b",
    "llama3.1:8b",
    "mistral",
    "phi3:latest",
    "llama3",
]


def get_available_models() -> tuple[list[str], str]:
    """
    Fetch locally installed models from Ollama's GET /api/tags endpoint.
    Returns (model_list, warning_message).
    warning_message is an empty string on success.
    Falls back to FALLBACK_MODELS if Ollama is unreachable or returns no models.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        if models:
            return models, ""
        return FALLBACK_MODELS, "Ollama returned no installed models. Showing recommended defaults."
    except requests.exceptions.ConnectionError:
        return FALLBACK_MODELS, (
            "Could not reach Ollama. Showing default model list. "
            "Start Ollama with: ollama serve"
        )
    except Exception:
        return FALLBACK_MODELS, (
            "Could not fetch models from Ollama. Showing default model list."
        )


def _extract_json_obj(text: str):
    """
    Extract first JSON object from a string.
    Handles four cases:
    1. Clean JSON string
    2. JSON wrapped in a markdown ```json fence
    3. JSON missing the leading { (model omitted it)
    4. JSON with trailing commas before } or ]
    """
    if not (text and text.strip()):
        raise ValueError("No JSON object found in model output.")
    text = text.strip()

    # 1) Try finding a markdown ```json block
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 2) Normal: find first {...}
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 3) Model output sometimes starts with "risk_score": ... (missing leading {)
    if text.lstrip().startswith('"'):
        try:
            return json.loads("{" + text.lstrip())
        except json.JSONDecodeError:
            pass

    # 4) Try cleanup of common issues (trailing commas before } or ])
    try:
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
    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(url, json=payload, timeout=600)
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


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

RISK_PROMPT = """
You are a contract risk reviewer acting on behalf of an SMB buyer.
{playbook_instructions}

STEP 1 — MISSING PROTECTIONS (think first):
Before flagging clause-level risks, identify which critical protections are ABSENT from the
provided clauses. Look for missing: liability cap, buyer termination-for-convenience,
data deletion on termination, breach notification obligations, mutual indemnity,
warranty disclaimers, SLA with credits. For each missing protection, create a flag
with evidence_quote set to "NOT FOUND IN CONTRACT".

STEP 2 — CLAUSE-LEVEL RISKS:
Enumerate specific clauses that are present but risky. Quote the EXACT contract language
as evidence_quote — do NOT paraphrase or summarize the quote.

RISK SCORE GUIDANCE (integer 1–10):
  1–2  Minor issues, mostly standard language, low practical impact
  3–4  Some buyer-unfriendly terms, limited financial exposure
  5–6  Multiple significant risks, negotiation strongly recommended
  7–8  Serious risks, high financial or operational exposure
  9–10 Extreme risk — deal-breaker level (e.g., unlimited liability, vendor owns customer deliverables)

EXAMPLE of a well-formed flag:
{{
  "category": "Limitation of Liability",
  "severity": "CRITICAL",
  "evidence_quote": "In no event shall Vendor's aggregate liability exceed one hundred dollars ($100).",
  "why_risky": "A $100 cap is far below any realistic contract value, leaving buyer fully exposed to loss from vendor failure.",
  "suggested_fallback": "Vendor's aggregate liability shall not exceed fees paid in the twelve (12) months preceding the claim."
}}

Use ONLY the provided clauses as evidence. Do not invent clauses not present.
Return ONLY a valid JSON object (no markdown fences, no commentary).

Schema:
{{
  "risk_score": <integer 1-10>,
  "red_flags": [
    {{
      "category": <string>,
      "severity": "LOW" | "MED" | "HIGH" | "CRITICAL",
      "evidence_quote": <exact quote from contract, or "NOT FOUND IN CONTRACT">,
      "why_risky": <clear explanation>,
      "suggested_fallback": <specific replacement language>
    }}
  ]
}}

CLAUSES:
{clauses}
"""

SUMMARY_PROMPT = """
Summarize the following contract clauses for a non-lawyer business owner.
Use plain, direct language — no jargon.

For each topic below, write exactly ONE sentence. If the topic is not addressed anywhere
in the clauses, write: "No [topic] found."

Topics:
- Contract term and renewal (length, auto-renewal conditions)
- Termination (who can terminate, required notice, conditions)
- Liability cap (maximum financial exposure for either party)
- Indemnification (who must defend/pay for the other party's losses)
- Data and privacy obligations (handling, breach notice, deletion)
- Payment terms (schedule, late fees, price change rights)
- Service levels / SLA (uptime targets, support response, remedies/credits)

Use ONLY the provided clauses as your source. Do not add assumptions.

CLAUSES:
{clauses}

Return as a bullet list, one bullet per topic.
"""

NEGOTIATION_PROMPT = """
You are drafting a negotiation email on behalf of the buyer (the company reviewing this
contract) to the vendor's legal or procurement team.

Vendor: {vendor_name}
Contract: {contract_name}

Tone: Professional but firm. This is a business negotiation, not a complaint.

Based on the risk analysis below, write an email that:
1. Opens with a short professional introduction (2 sentences max) referencing the contract name
2. Numbers each requested change, citing the specific clause or section involved
3. For every requested change, provides a concrete proposed redline — exact replacement
   language — not a vague request like "please revise"
4. Closes with a collaborative call to action inviting a discussion

RISKS JSON:
{risks_json}

Write the complete email. Use "our legal team" or "our procurement team" instead of
placeholders like [Your Name].
"""

CHAT_PROMPT = """
You are ClauseCopilot, a helpful AI assistant specializing in contract review.
Answer the user's question based ONLY on the provided contract context.

Rules:
- If the answer is not in the context, say "I cannot find that information in the contract."
- If the question is ambiguous or could have multiple interpretations, ask for clarification
  before answering.
- When referencing contract text, always cite the specific section name, e.g.:
  "In Section 4.2 (Limitation of Liability), the contract states..."
- Do not provide general legal advice outside the scope of this contract.

Contract Context:
{context}

Conversation History (last 8 exchanges):
{history}

User Question: {question}

Answer:
"""


# ---------------------------------------------------------------------------
# Agent functions
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type(ValueError))
def run_risk_review(model: str, clauses_text: str, temperature: float = 0.2,
                    playbook_rules: str = None) -> str:
    """Run risk review with retries on JSON parse failures."""
    instructions = (
        playbook_rules
        if playbook_rules
        else "Identify risks related to: Termination, Liability, Indemnity, Auto-renewal."
    )
    prompt = RISK_PROMPT.format(playbook_instructions=instructions, clauses=clauses_text)

    # Try JSON mode first (supported in newer Ollama); fall back to plain if needed
    raw_output = _ollama_generate(prompt, model, temperature=temperature, json_mode=True)
    try:
        _extract_json_obj(raw_output)
        return raw_output
    except ValueError:
        raw_output = _ollama_generate(prompt, model, temperature=temperature, json_mode=False)
        _extract_json_obj(raw_output)  # Raises ValueError → triggers retry if still bad
        return raw_output


def run_summary(model: str, clauses_text: str, temperature: float = 0.2) -> str:
    prompt = SUMMARY_PROMPT.format(clauses=clauses_text)
    return _ollama_generate(prompt, model, temperature=temperature)


def run_negotiation(model: str, risks_json: str, vendor_name: str = "the vendor",
                    contract_name: str = "the contract", temperature: float = 0.2) -> str:
    prompt = NEGOTIATION_PROMPT.format(
        risks_json=risks_json,
        vendor_name=vendor_name,
        contract_name=contract_name,
    )
    return _ollama_generate(prompt, model, temperature=temperature)


def run_chat(model: str, context: str, history: str, question: str,
             temperature: float = 0.1) -> str:
    prompt = CHAT_PROMPT.format(context=context, history=history, question=question)
    return _ollama_generate(prompt, model, temperature=temperature)
