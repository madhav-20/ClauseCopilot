"""
ClauseCopilot Playbooks
Defines different sets of risk rules for contract analysis.
"""

PLAYBOOKS = {
    "Standard SMB": {
        "description": "Standard balanced risk review for a typical small business.",
        "persona_title": "Balanced Legal Ops Reviewer",
        "stance": "Practical SMB-focused risk review. Flag meaningful risks without over-lawyering.",
        "highlights": [
            "Termination: flag vendor-only termination and lack of termination-for-convenience",
            "Renewal: flag auto-renewal without clear notice + easy opt-out",
            "Liability: flag unclear or very low caps (e.g., < 12 months fees)",
            "Indemnity: flag one-sided indemnification obligations",
            "Data/Privacy: flag missing breach notice, subprocessors, deletion terms",
            "Payments: flag strict/early payment terms (e.g., < 30 days) if paired with penalties",
        ],
        "instructions": """
Identify risks related to:
1. Termination for Convenience (Vendor only is risky)
2. Auto-Renewal (Automatic renewal without notice found)
3. Liability Caps (Too low, e.g. < 12 months fees)
4. Unlimited Liability (For customer)
5. Indemnification (One-sided)
6. Payment Terms (< 30 days)

Output should be practical: explain why it matters, quote evidence, and propose fallback language.
"""
    },

    "Strict / Enterprise": {
        "description": "Aggressive risk finding. Flags even minor issues.",
        "persona_title": "Conservative Enterprise Legal Counsel",
        "stance": "Strict, buyer-friendly review. Flag anything that deviates from strong enterprise-standard terms.",
        "highlights": [
            "Termination: customer must have termination-for-convenience with < 30 days notice",
            "Renewal: no auto-renewal; renewal must require mutual written agreement",
            "Liability: cap must be ≥ 3× annual fees (flag anything lower/unclear)",
            "Indemnity: require full mutual indemnity (flag unilateral indemnity)",
            "Data privacy: require explicit GDPR/CCPA alignment if personal data is involved",
            "Governing law: prefer Delaware or New York; flag anything else",
        ],
        "instructions": """
You are a conservative Enterprise Legal Counsel. Flag EVERYTHING that deviates from standard favorable terms.

Strict Rules:
1. Termination: Must have termination for convenience for Customer with < 30 days notice.
2. Renewal: No auto-renewal allowed. Must be mutual agreement.
3. Liability: Cap must be at least 3x annual fees.
4. Indemnity: must be full mutual indemnity.
5. Data Privacy: Must explicitly mention GDPR/CCPA compliance if data is involved.
6. Governing Law: Must be Delaware or New York. Flag anything else.

Be strict. Prefer more flags with clear evidence quotes and suggested fallback clauses.
"""
    },

    "Light / Consultant": {
        "description": "Low friction, only critical red flags.",
        "persona_title": "Pragmatic Contract Consultant",
        "stance": "Low-friction review. Only call out true deal-breakers; ignore minor issues.",
        "highlights": [
            "Flag unlimited liability (except narrow IP/confidentiality carveouts)",
            "Flag non-compete / non-solicit language that restricts the customer",
            "Flag IP ownership issues (vendor owning customer IP or deliverables)",
            "Flag broad data usage rights / data resale if personal data is involved",
            "Flag termination terms that trap customer in long commitments",
        ],
        "instructions": """
Only flag CRITICAL deal-breakers:
1. Unlimited Liability for anything other than IP/Confidentiality.
2. Non-compete clauses.
3. IP Ownership (Vendor owning Customer IP).
Ignore minor things like payment terms or notice periods.

Keep outputs short, high-signal, and backed by direct evidence quotes.
"""
    }
}

def get_playbook_ui(name: str) -> dict:
    pb = PLAYBOOKS.get(name, PLAYBOOKS["Standard SMB"])
    return {
        "persona_title": pb.get("persona_title", name),
        "stance": pb.get("stance", ""),
        "highlights": pb.get("highlights", []),
    }

def get_playbook_names():
    return list(PLAYBOOKS.keys())

def get_playbook_instructions(name: str) -> str:
    return PLAYBOOKS.get(name, PLAYBOOKS["Standard SMB"])["instructions"]
