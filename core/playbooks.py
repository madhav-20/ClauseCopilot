"""
ClauseCopilot Playbooks
Defines different sets of risk rules for contract analysis.
"""

PLAYBOOKS = {
    "Standard SMB": {
        "description": "Standard balanced risk review for a typical small business.",
        "instructions": """
Identify risks related to:
1. Termination for Convenience (Vendor only is risky)
2. Auto-Renewal (Automatic renewal without notice found)
3. Liability Caps (Too low, e.g. < 12 months fees)
4. Unlimited Liability (For customer)
5. Indemnification (One-sided)
6. Payment Terms (< 30 days)
        """
    },
    "Strict / Enterprise": {
        "description": "Aggressive risk finding. Flags even minor issues.",
        "instructions": """
You are a conservative Enterprise Legal Counsel. Flag EVERYTHING that deviates from standard favorable terms.
Strict Rules:
1. Termination: Must have termination for convenience for Customer with < 30 days notice.
2. Renewal: No auto-renewal allowed. Must be mutual agreement.
3. Liability: Cap must be at least 3x annual fees.
4. Indemnity: must be full mutual indemnity. 
5. Data Privacy: Must explicitly mention GDPR/CCPA compliance if data is involved.
6. Governing Law: Must be Delaware or New York. Flag anything else.
        """
    },
    "Light / Consultant": {
        "description": "Low friction, only critical red flags.",
        "instructions": """
Only flag CRITICAL deal-breakers:
1. Unlimited Liability for anything other than IP/Confidentiality.
2. Non-compete clauses.
3. IP Ownership (Vendor owning Customer IP).
Ignore minor things like payment terms or notice periods.
        """
    }
}

def get_playbook_names():
    return list(PLAYBOOKS.keys())

def get_playbook_instructions(name: str) -> str:
    return PLAYBOOKS.get(name, PLAYBOOKS["Standard SMB"])["instructions"]
