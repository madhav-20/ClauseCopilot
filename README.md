# Clause Copilot — Vendor Risk & Contract Copilot

A local-first, AI-powered contract review tool for small and mid-size businesses. Upload a vendor contract PDF, and Clause Copilot will identify risks, summarize key terms, draft a negotiation email, and let you search across all your past contracts — all running on your own machine with no data sent to the cloud.

![Clause Copilot Demo](assets/demo1.png)

---

## What It Does

Clause Copilot gives you five tools in one Streamlit interface:

**Review** — Upload a contract PDF. The app extracts text (with automatic OCR fallback for scanned documents), splits it into clause-level chunks, embeds them into a local vector store, and runs a structured risk analysis using a local LLM. Risks are ranked by severity (LOW / MED / HIGH / CRITICAL), each with a direct quote from the contract, an explanation of why it's risky, and a suggested fallback clause. Individual flags can be dismissed as false positives and restored at any time — dismissed flags are persisted across sessions.

**Chat with Contract** — Ask plain-English questions about any uploaded contract. Answers are grounded in the actual contract text via retrieval-augmented generation (RAG), so the model won't invent clauses that aren't there. The assistant cites the specific section it's drawing from and maintains context across up to 8 exchanges.

**Negotiation Draft** — Automatically generates a professional negotiation email to the vendor based on the flagged risks, complete with specific change requests and proposed fallback language. The email is addressed to the vendor by name and references the specific contract.

**Clause Library** — Semantic search across every contract you've ever indexed. Filter by vendor and search by concept (e.g. "auto-renewal", "termination for convenience") to find and compare specific clauses across your entire contract history. Results highlight your search terms inline.

**History** — A dashboard of all previously analyzed contracts, showing vendor name, filename, date, and color-coded risk score. Click Load on any past contract to instantly restore the full analysis — summary, risk flags, and negotiation email — without re-uploading or re-analyzing.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)              │
│         5 tabs: Review · Chat · Negotiation         │
│                Clause Library · History             │
├──────────────┬──────────────┬───────────────────────┤
│  core/       │  core/       │  core/                │
│  ingest.py   │  chunking.py │  retrieval.py         │
│  (pdfplumber │  (section +  │  (15 risk-category    │
│  + OCR)      │  sentence    │  semantic queries,    │
│              │  aware,      │  batched embeddings,  │
│              │  overlap)    │  section labels)      │
├──────────────┴──────────────┴───────────────────────┤
│  core/embeddings.py                                 │
│  (SentenceTransformers — all-MiniLM-L6-v2)          │
├──────────────────────────┬──────────────────────────┤
│  core/vectorstore.py     │  core/storage.py         │
│  (ChromaDB — persistent) │  (SQLite — contracts,    │
│                          │   outputs, dismissed     │
│                          │   flags cache)           │
├──────────────────────────┴──────────────────────────┤
│  core/agents.py                                     │
│  (Ollama — dynamic model detection via /api/tags)   │
│  Risk review · Summary · Negotiation · Chat         │
└─────────────────────────────────────────────────────┘
```

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | Ollama (local — dynamic model detection) |
| Embeddings | `all-MiniLM-L6-v2` via SentenceTransformers |
| Vector store | ChromaDB (persistent on disk) |
| PDF extraction | pdfplumber + pytesseract (OCR fallback) |
| OCR system deps | Poppler + Tesseract |
| Persistence | SQLite |
| LLM retry logic | Tenacity |
| Testing | pytest |

---

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- At least one Ollama model pulled (see Recommended Models below)
- *(Optional, for scanned PDFs)* Poppler and Tesseract

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/madhav-20/ClauseCopilot.git
cd ClauseCopilot
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install and start Ollama

Download Ollama from [ollama.com](https://ollama.com), then pull a model. For the best results on contract analysis, use one of the recommended models below:

```bash
ollama pull deepseek-r1:14b    # recommended — best reasoning quality for legal analysis
# or, for higher-spec machines:
ollama pull deepseek-r1:32b
ollama pull qwen2.5:32b
```

Start the Ollama server (if it's not already running):

```bash
ollama serve
```

> The model selector in the sidebar is populated dynamically by querying Ollama's `/api/tags` endpoint — it shows only the models you actually have installed. If Ollama is unreachable at startup, it falls back to a curated default list.

### 4. *(Optional)* Install OCR dependencies for scanned PDFs

**macOS:**
```bash
brew install poppler tesseract
```

**Ubuntu / Debian:**
```bash
sudo apt-get install -y poppler-utils tesseract-ocr
```

**Windows:** Install [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases) and [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki), then add both to your PATH.

> If OCR dependencies are not installed, Clause Copilot will still work for text-based PDFs — it simply won't be able to process scanned/image-only contracts.

### 5. Run the app

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Usage

### Reviewing a Contract

1. Enter a vendor name in the sidebar (used to tag your indexed clauses).
2. Select a **Risk Playbook** to set the review persona and rule set (see Playbooks section below).
3. Go to the **Review** tab and upload a contract PDF (up to 50 MB).
4. Click **Index & Analyze** — this runs both indexing and risk analysis in one step.
5. Review flagged risks — each shows its severity, the exact evidence quote from the contract, why it's risky, and a suggested fallback clause.
6. Use **Dismiss (false positive)** on any flag you want to exclude from the report. Dismissed flags are saved and can be restored with the "Show dismissed flags" toggle.

> **Advanced:** An expandable *Advanced* section provides separate Index and Analyze buttons for power users who want to re-index without re-analyzing or vice versa.

### Chatting with a Contract

After indexing, switch to the **Chat with Contract** tab. Ask questions like:

- *"What is the liability cap?"*
- *"Does this contract auto-renew? What is the notice period?"*
- *"Who owns intellectual property created during the engagement?"*

The assistant answers strictly from the contract text, cites the relevant section, and maintains context across up to 8 back-and-forth exchanges.

### Generating a Negotiation Email

After running an analysis, go to the **Negotiation Draft** tab and click **Generate Negotiation Email**. The model drafts a professional email addressed to the vendor by name, requesting specific changes for each flagged risk with proposed fallback language inline.

### Searching the Clause Library

Go to the **Clause Library** tab. Type any concept or phrase (e.g. *"data retention"*, *"indemnification"*, *"governing law"*) and the app will return semantically similar clauses across all indexed contracts, with your search terms highlighted. Optionally filter by vendor.

### Browsing Contract History

Go to the **History** tab to see all previously analyzed contracts with their vendor, date, and risk score (color-coded green / orange / red). Click **Load** on any row to restore the full analysis into the session — no re-upload needed.

---

## Risk Playbooks

Playbooks control the reviewer's persona and the strictness of the analysis. Select one in the sidebar before running.

| Playbook | Persona | Use When |
|---|---|---|
| **Standard SMB** | Balanced Legal Ops Reviewer | General use — flags meaningful risks without over-lawyering |
| **Strict / Enterprise** | Conservative Enterprise Legal Counsel | High-value contracts — flags anything deviating from strong enterprise terms |
| **Light / Consultant** | Pragmatic Contract Consultant | Quick checks — only true deal-breakers flagged |
| **SaaS / Software** | SaaS Procurement Specialist | Software subscriptions — uptime, data portability, IP ownership of customisations |
| **Healthcare / HIPAA** | Healthcare Compliance Officer | Vendor contracts involving PHI — BAA, breach notification, audit rights |
| **Employment / NDA** | Employment Counsel Reviewer | Employment agreements and NDAs — non-compete scope, IP assignment, confidentiality |

### Risk Categories Checked

The retrieval system targets 15 categories across all playbooks:

- Limitation of liability and liability caps
- Indemnity and indemnification
- Termination for convenience and auto-renewal
- Data privacy, security, and GDPR
- Payment terms, fees, and pricing
- Warranties and service level agreements (SLA)
- Confidentiality and non-disclosure
- Insurance and compliance
- Intellectual property ownership and work-for-hire
- Force majeure and business continuity
- Dispute resolution, arbitration, and governing law
- Assignment and change of control
- Audit rights and record keeping
- Non-solicitation of employees
- Subcontracting and third-party data sharing

---

## Configuration

All paths and limits can be overridden via environment variables.

| Variable | Default | Description |
|---|---|---|
| `CLAUSE_DATA_DIR` | `data/` | Root directory for uploads, ChromaDB, and SQLite |
| `CLAUSE_MAX_UPLOAD_MB` | `50` | Maximum PDF upload size in megabytes |

The data directory layout:

```
data/
├── uploads/      # uploaded PDF files
├── chroma/       # ChromaDB vector store (persistent)
└── app.db        # SQLite database (contracts, outputs, dismissed flags)
```

---

## Project Structure

```
ClauseCopilot/
├── app.py                       # Streamlit app — all 5 tabs
├── requirements.txt
├── generate_sample_contracts.py # Script to generate sample test contracts
├── assets/
│   └── demo1.png
├── sample_contracts/            # 5 sample PDFs for testing
│   ├── smb_managed_it_services.pdf
│   ├── saas_cloudvault_pro.pdf
│   ├── healthcare_medconnect_ehr.pdf
│   ├── enterprise_orbis_software_license.pdf
│   └── employment_nexaflow_engineer.pdf
├── tests/
│   └── test_core.py             # Unit tests (pytest)
└── core/
    ├── config.py                # Paths and env var config
    ├── ingest.py                # PDF extraction (pdfplumber + OCR)
    ├── chunking.py              # Section-aware clause chunking with overlap
    ├── embeddings.py            # SentenceTransformer embeddings
    ├── vectorstore.py           # ChromaDB upsert + semantic search
    ├── retrieval.py             # 15 risk-category retrieval queries (batched)
    ├── agents.py                # LLM prompts + Ollama API calls + model detection
    ├── playbooks.py             # 6 risk playbook definitions
    └── storage.py               # SQLite persistence (contracts, outputs, dismissed flags)
```

---

## Key Design Decisions

**Fully local by default.** No API keys required. No contract text ever leaves your machine. The LLM, embeddings, and vector store all run locally via Ollama and ChromaDB. This makes the tool appropriate for sensitive, confidential, or legally privileged documents.

**Dynamic model detection.** On startup, the app queries Ollama's `/api/tags` endpoint to populate the model selector with only the models you actually have installed. If Ollama is unreachable, it falls back gracefully to a curated list of recommended models with a visible warning.

**Section-aware chunking with overlap.** The chunker detects contract section headers across multiple formats — numbered sections (`1.2`), `SECTION N`, `Article 5`, `ARTICLE IV`, `§ 12.3`, `Schedule A`, `Exhibit B`, and ALL-CAPS headings. It splits at sentence boundaries rather than mid-sentence. Each chunk carries a ~200-character overlap from the previous chunk to prevent context loss at boundaries, and a `chunk_index` field for document position tracking.

**Multi-query batched retrieval.** Rather than sending the entire contract to the LLM, `retrieval.py` runs 15 targeted semantic queries (one per risk category), all embedded in a single batched `embed_texts()` call for speed. Results are deduplicated and each chunk is prefixed with its section title (e.g. `[SECTION: Limitation of Liability]`) so the model knows exactly where each clause lives.

**Chain-of-thought risk prompting.** The risk review prompt instructs the model to first identify what critical protections are *absent* from the contract before enumerating clause-level risks — since missing terms (no liability cap, no data deletion obligation) are often the most dangerous issues. Risk scores follow a defined 1–10 scale with explicit criteria.

**Dismiss / false positive mechanism.** Each risk flag has a Dismiss button. Dismissed flags are hidden from the report by default, stored as a JSON list in SQLite, and survive page refreshes and session restarts. They can be reviewed or restored at any time via a toggle.

**Persistent analysis caching.** Risk reports, summaries, negotiation emails, and dismissed flag lists are stored in SQLite and reloaded automatically. The History tab surfaces all past contracts with their risk scores so you can return to any analysis without re-uploading.

**Retry logic on JSON parsing.** The risk review output is structured JSON. `agents.py` uses `tenacity` to retry up to 3 times if the model produces malformed JSON, with four fallback parsing strategies (markdown fence stripping, greedy `{...}` extraction, missing-brace recovery, trailing comma cleanup) before giving up.

---

## Recommended Models

The model selector is populated from your locally installed Ollama models. For the best contract analysis quality, these models are recommended:

| Model | RAM Required | Notes |
|---|---|---|
| `deepseek-r1:14b` | ~10 GB | **Best starting point** — explicit reasoning steps, excellent at legal analysis |
| `deepseek-r1:32b` | ~20 GB | Higher quality, slower; great for complex enterprise contracts |
| `qwen2.5:32b` | ~20 GB | Exceptional at structured JSON output and complex instruction-following |
| `llama3.3:70b` | ~40 GB | Most capable general model; for M-series Macs with 48 GB+ unified memory |
| `llama3.1:8b` | ~5 GB | Lightweight fallback; works on any M-series Mac |
| `mistral` | ~4 GB | Fast, decent quality for simpler contracts |

Pull any model with:

```bash
ollama pull deepseek-r1:14b
```

---

## Testing

Unit tests cover the three most critical pure-logic functions — no LLM or Ollama connection required.

```bash
pytest tests/test_core.py -v
```

Tests cover:

- **`chunk_text`** — section header detection (numbered, ALL-CAPS, Article, §, Schedule, Exhibit, Roman numerals), max-chars enforcement, sentence boundary splitting, chunk overlap, and `chunk_index` sequencing.
- **`_extract_json_obj`** — all four parsing paths: clean JSON, markdown-fenced JSON, JSON missing a leading brace, and JSON with trailing commas.
- **`retrieve_evidence_for_risk`** — deduplication of results, `max_chars` cap, `[SECTION: ...]` prefix presence, correct batching (exactly 2 `embed_texts` calls), and empty-input handling.

### Sample Contracts

Five sample contracts are included in `sample_contracts/` for testing and demonstration. Each is a realistic but fictitious agreement with subtly embedded risks:

| File | Type |
|---|---|
| `smb_managed_it_services.pdf` | Managed IT services agreement (SMB) |
| `saas_cloudvault_pro.pdf` | SaaS subscription contract |
| `healthcare_medconnect_ehr.pdf` | Healthcare EHR vendor contract |
| `enterprise_orbis_software_license.pdf` | Enterprise software license |
| `employment_nexaflow_engineer.pdf` | Employment agreement / NDA |

To regenerate the sample contracts:

```bash
pip install fpdf2
python generate_sample_contracts.py
```

---

## In Progress

- [ ] Multi-contract comparison view — side-by-side clause diff across vendor agreements
- [ ] Export flagged risk report as PDF or Word document
- [ ] Streamlit Cloud deployment for browser-based access without local setup

---

## Requirements

```
streamlit>=1.28
pdfplumber>=0.10
sentence-transformers>=2.2
chromadb>=0.4
langchain-community>=0.0.20
pdf2image>=1.16
pytesseract>=0.3.10
tenacity>=8.2
pytest>=7.4
```

---

## Disclaimer

Clause Copilot is a legal research and drafting aid, not a substitute for professional legal advice. Always have contracts reviewed by a qualified attorney before signing.

---

## Acknowledgements

Built as part of SCU MSIS coursework (GenAI for Enterprise)
Core development and architecture by Madhav Mundada.
Sara Malik contributed to development & prototyping.

---

## License

MIT
