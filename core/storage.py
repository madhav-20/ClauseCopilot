import json
import re
import sqlite3
from typing import Optional, List

from core.config import DB_PATH


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contracts (
        contract_id TEXT PRIMARY KEY,
        vendor_name TEXT,
        filename TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS outputs (
        contract_id TEXT PRIMARY KEY,
        risk_json TEXT,
        summary TEXT,
        negotiation_email TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

    # Add dismissed_flags column if it doesn't exist yet (safe for existing DBs)
    try:
        cur.execute("ALTER TABLE outputs ADD COLUMN dismissed_flags TEXT DEFAULT '[]'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.close()


def save_contract(contract_id: str, vendor_name: str, filename: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO contracts (contract_id, vendor_name, filename)
        VALUES (?, ?, ?)
    """, (contract_id, vendor_name, filename))
    conn.commit()
    conn.close()


def save_outputs(
    contract_id: str,
    risk_json: str,
    summary: str,
    negotiation_email: str = "",
    dismissed_flags: str = "[]",
):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO outputs
            (contract_id, risk_json, summary, negotiation_email, dismissed_flags, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (contract_id, risk_json, summary, negotiation_email, dismissed_flags))
    conn.commit()
    conn.close()


def load_outputs(contract_id: str) -> Optional[tuple]:
    """
    Returns (risk_json, summary, negotiation_email, dismissed_flags) or None.
    dismissed_flags is a JSON string (e.g. '[1, 3]').
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT risk_json, summary, negotiation_email, dismissed_flags "
        "FROM outputs WHERE contract_id = ?",
        (contract_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    # Ensure dismissed_flags is always a valid JSON string
    dismissed = row[3] if row[3] else "[]"
    return row[0], row[1], row[2], dismissed


def list_vendors() -> List[str]:
    """Return distinct vendor names from indexed contracts (for Clause Library filter)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT vendor_name FROM contracts "
        "WHERE vendor_name IS NOT NULL AND vendor_name != '' "
        "ORDER BY vendor_name"
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def list_contracts() -> List[dict]:
    """
    Return all contracts joined with their latest risk output, sorted newest first.
    Each dict: contract_id, vendor_name, filename, created_at, risk_score (int|None).
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.contract_id, c.vendor_name, c.filename, c.created_at,
               o.risk_json
        FROM contracts c
        LEFT JOIN outputs o ON c.contract_id = o.contract_id
        ORDER BY c.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        risk_score = None
        raw_json = r[4]
        if raw_json:
            # Try direct parse first, then regex-extract the first JSON object
            for attempt in (raw_json, None):
                try:
                    obj = json.loads(attempt if attempt else "{}")
                    risk_score = obj.get("risk_score")
                    break
                except Exception:
                    pass
            if risk_score is None:
                m = re.search(r"\{.*\}", raw_json, re.DOTALL)
                if m:
                    try:
                        obj = json.loads(m.group(0))
                        risk_score = obj.get("risk_score")
                    except Exception:
                        pass

        result.append({
            "contract_id": r[0],
            "vendor_name": r[1] or "Unknown",
            "filename": r[2] or "",
            "created_at": r[3] or "",
            "risk_score": risk_score,
        })
    return result
