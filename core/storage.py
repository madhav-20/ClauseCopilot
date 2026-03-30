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

def save_outputs(contract_id: str, risk_json: str, summary: str, negotiation_email: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO outputs (contract_id, risk_json, summary, negotiation_email, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (contract_id, risk_json, summary, negotiation_email))
    conn.commit()
    conn.close()

def load_outputs(contract_id: str) -> Optional[tuple]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT risk_json, summary, negotiation_email FROM outputs WHERE contract_id = ?", (contract_id,))
    row = cur.fetchone()
    conn.close()
    return row


def list_vendors() -> List[str]:
    """Return distinct vendor names from indexed contracts (for Clause Library filter)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT vendor_name FROM contracts WHERE vendor_name IS NOT NULL AND vendor_name != '' ORDER BY vendor_name")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]