import os
import json
import streamlit as st
import re

from core.ingest import extract_text_from_pdf_with_ocr
from core.chunking import chunk_text
from core.embeddings import embed_texts
from core.vectorstore import get_chroma_client, get_collection, upsert_chunks, semantic_search
from core.agents import (
    run_risk_review, run_summary, run_negotiation, run_chat,
    _extract_json_obj, get_available_models,
)
from core.retrieval import retrieve_evidence_for_risk
from core.storage import (
    init_db, save_contract, save_outputs, load_outputs,
    list_vendors, list_contracts,
)
from core.config import ensure_dirs, UPLOADS_DIR, MAX_UPLOAD_MB
from core.playbooks import get_playbook_names, get_playbook_instructions, get_playbook_ui

st.set_page_config(page_title="ClauseSense - Contract Copilot", layout="wide")
st.markdown("""
<style>
div[data-testid="stChatInput"] {
    position: sticky;
    bottom: 0;
    background: var(--background-color);
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    z-index: 100;
}
section.main > div {
    padding-bottom: 5rem;
}
</style>
""", unsafe_allow_html=True)

ensure_dirs()
init_db()

st.title("Clause Copilot")

client = get_chroma_client()
collection = get_collection(client)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_contract_id(filename: str) -> str:
    """
    Derive a safe contract_id from a filename.
    Strips the .pdf extension, replaces any character that is not alphanumeric,
    a hyphen, or an underscore with '_', and truncates to 100 characters.
    Prevents path-traversal and SQLite key collisions with unusual filenames.
    """
    name = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return name[:100]


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_models() -> tuple[list[str], str]:
    """Cache the Ollama model list for 5 minutes to avoid repeated API calls on rerun."""
    return get_available_models()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.header("Settings")
vendor = st.sidebar.text_input("Vendor name", value="Demo Vendor")

available_models, model_warning = _fetch_models()
if model_warning:
    st.sidebar.warning(model_warning)
model_name = st.sidebar.selectbox("LLM Model (Ollama)", available_models, index=0)

top_k = st.sidebar.slider("Search results (top_k)", 3, 15, 5)

st.sidebar.subheader("Risk Playbook")
playbook_name = st.sidebar.selectbox("Select Playbook", get_playbook_names())
playbook_instructions = get_playbook_instructions(playbook_name)

pb_ui = get_playbook_ui(playbook_name)
st.sidebar.markdown(f"**Persona:** {pb_ui['persona_title']}")
if pb_ui["stance"]:
    st.sidebar.caption(pb_ui["stance"])

st.sidebar.markdown("**Key checks:**")
for rule in pb_ui["highlights"]:
    st.sidebar.write(f"- {rule}")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Review", "Chat with Contract", "Negotiation Draft", "Clause Library", "History"]
)

# ===========================================================================
# TAB 1 — REVIEW
# ===========================================================================
with tab1:
    st.subheader("Upload & Review")
    uploaded = st.file_uploader("Upload contract PDF", type=["pdf"])

    if uploaded:
        # Validate filename and size
        if not (uploaded.name and uploaded.name.lower().endswith(".pdf")):
            st.error("Please upload a PDF file.")
            st.stop()
        max_bytes = MAX_UPLOAD_MB * 1024 * 1024
        if uploaded.size > max_bytes:
            st.error(f"File too large. Maximum size is {MAX_UPLOAD_MB} MB.")
            st.stop()

        pdf_path = os.path.join(UPLOADS_DIR, uploaded.name)
        try:
            with open(pdf_path, "wb") as f:
                f.write(uploaded.getbuffer())
        except OSError as e:
            st.error(f"Could not save upload: {e}")
            st.stop()

        contract_id = sanitize_contract_id(uploaded.name)

        # New upload: reset session state for this contract and load any cached analysis
        if st.session_state.get("current_contract_id") != contract_id:
            st.session_state["current_contract_id"] = contract_id
            st.session_state["risk_json"] = None
            st.session_state["summary"] = None
            st.session_state["negotiation_email"] = None
            st.session_state["chat_messages"] = []
            st.session_state["dismissed_flags"] = set()

            row = load_outputs(contract_id)
            if row:
                st.session_state["risk_json"] = row[0]
                st.session_state["summary"] = row[1]
                st.session_state["negotiation_email"] = row[2]
                try:
                    dismissed = json.loads(row[3] or "[]")
                    st.session_state["dismissed_flags"] = set(dismissed)
                except Exception:
                    st.session_state["dismissed_flags"] = set()

        # Ensure dismissed_flags always exists in session state
        if "dismissed_flags" not in st.session_state:
            st.session_state["dismissed_flags"] = set()

        st.success(f"Uploaded: {uploaded.name}")

        @st.cache_data
        def get_pdf_text(path):
            return extract_text_from_pdf_with_ocr(path)

        with st.spinner("Extracting text..."):
            try:
                text, used_ocr = get_pdf_text(pdf_path)
            except Exception as e:
                st.error(f"Could not extract text from PDF: {e}")
                st.stop()

        if not text:
            st.error("No text extracted. PDF might be empty or unreadable.")
            st.stop()

        if used_ocr:
            st.caption("OCR was used for this PDF (scanned/image).")

        with st.expander("Preview extracted text"):
            st.write(text[:4000] + ("..." if len(text) > 4000 else ""))

        with st.spinner("Chunking into clauses/sections..."):
            chunks = chunk_text(text)

        st.info(f"Created {len(chunks)} chunks")

        # -------------------------------------------------------------------
        # Primary action: Index & Analyze (single button, sequential steps)
        # -------------------------------------------------------------------
        if st.button("Index & Analyze", type="primary", help="Index contract into vector store then run full risk analysis"):
            _index_ok = False
            try:
                with st.spinner("Embedding + indexing..."):
                    texts = [c["text"] for c in chunks]
                    embs = embed_texts(texts)
                    upsert_chunks(collection, contract_id, vendor, chunks, embs)
                    save_contract(contract_id, vendor, uploaded.name)
                _index_ok = True
                st.success("Indexed successfully.")
            except Exception as e:
                st.error(f"Indexing failed: {e}")

            if _index_ok:
                try:
                    with st.spinner("Retrieving relevant clauses..."):
                        evidence_text = retrieve_evidence_for_risk(chunks, top_k_per_query=top_k)

                    with st.spinner(f"Running risk review ({playbook_name})..."):
                        risk_json = run_risk_review(
                            model_name, evidence_text, playbook_rules=playbook_instructions
                        )

                    with st.spinner("Generating summary..."):
                        summary = run_summary(model_name, evidence_text)

                    st.session_state["risk_json"] = risk_json
                    st.session_state["summary"] = summary
                    st.session_state["dismissed_flags"] = set()

                    dismissed_json = json.dumps(
                        sorted(st.session_state["dismissed_flags"])
                    )
                    save_outputs(
                        contract_id, risk_json, summary,
                        st.session_state.get("negotiation_email") or "",
                        dismissed_json,
                    )
                    st.success("Analysis complete.")
                except Exception as e:
                    st.error("Analysis failed. Check that Ollama is running.")
                    with st.expander("Error details", expanded=True):
                        st.code(str(e), language="text")
                    st.stop()

        # -------------------------------------------------------------------
        # Advanced: individual Index / Analyze buttons
        # -------------------------------------------------------------------
        with st.expander("Advanced", expanded=False):
            st.caption("Use these to re-index without re-analyzing, or vice versa.")
            col_idx, col_anl = st.columns(2)

            with col_idx:
                if st.button("Index Contract", key="adv_index",
                             help="Rebuild the vector search index only"):
                    try:
                        with st.spinner("Embedding + indexing..."):
                            texts = [c["text"] for c in chunks]
                            embs = embed_texts(texts)
                            upsert_chunks(collection, contract_id, vendor, chunks, embs)
                            save_contract(contract_id, vendor, uploaded.name)
                        st.success("Indexed successfully.")
                    except Exception as e:
                        st.error(f"Indexing failed: {e}")

            with col_anl:
                if st.button("Analyze Risks", key="adv_analyze",
                             help="Run risk analysis using current index"):
                    try:
                        with st.spinner("Retrieving relevant clauses..."):
                            evidence_text = retrieve_evidence_for_risk(
                                chunks, top_k_per_query=top_k
                            )

                        with st.spinner(f"Running risk review ({playbook_name})..."):
                            risk_json = run_risk_review(
                                model_name, evidence_text,
                                playbook_rules=playbook_instructions,
                            )

                        with st.spinner("Generating summary..."):
                            summary = run_summary(model_name, evidence_text)

                        st.session_state["risk_json"] = risk_json
                        st.session_state["summary"] = summary
                        st.session_state["dismissed_flags"] = set()

                        dismissed_json = json.dumps(
                            sorted(st.session_state["dismissed_flags"])
                        )
                        save_outputs(
                            contract_id, risk_json, summary,
                            st.session_state.get("negotiation_email") or "",
                            dismissed_json,
                        )
                    except Exception as e:
                        st.error("Analysis failed. Check that Ollama is running.")
                        with st.expander("Error details", expanded=True):
                            st.code(str(e), language="text")
                        st.stop()

        # -------------------------------------------------------------------
        # Display Results
        # -------------------------------------------------------------------
        risk_json_val = st.session_state.get("risk_json")
        if risk_json_val and st.session_state.get("current_contract_id") == contract_id:
            st.divider()
            st.subheader("Summary")
            st.write(st.session_state.get("summary", ""))

            st.subheader("Risk Report")
            try:
                risk_obj = _extract_json_obj(risk_json_val)
            except ValueError:
                st.error("Risk output was invalid JSON. Try running analysis again.")
                with st.expander("Show raw model output"):
                    st.code(risk_json_val)
            else:
                risk_score = risk_obj.get("risk_score", "?")
                flags = risk_obj.get("red_flags", [])

                col1, col2 = st.columns([1, 3])
                with col1:
                    st.metric("Overall Risk Score", risk_score)
                with col2:
                    st.caption(f"Based on Playbook: **{playbook_name}**")

                sev_rank = {"CRITICAL": 4, "HIGH": 3, "MED": 2, "LOW": 1}
                flags = sorted(
                    flags,
                    key=lambda x: sev_rank.get(str(x.get("severity", "LOW")).upper(), 0),
                    reverse=True,
                )

                # Dismiss controls
                show_dismissed = st.checkbox(
                    "Show dismissed flags",
                    value=False,
                    key="show_dismissed_toggle",
                )

                dismissed_set = st.session_state.get("dismissed_flags", set())
                active_count = sum(
                    1 for i in range(1, len(flags) + 1) if i not in dismissed_set
                )
                dismissed_count = len(flags) - active_count
                if dismissed_count:
                    st.caption(
                        f"{dismissed_count} flag(s) dismissed. "
                        "Toggle 'Show dismissed flags' to review them."
                    )

                for i, f in enumerate(flags, start=1):
                    is_dismissed = i in dismissed_set
                    if is_dismissed and not show_dismissed:
                        continue

                    category = str(f.get("category", "unknown")).title()
                    severity = str(f.get("severity", "LOW")).upper()
                    evidence = f.get("evidence_quote", "").strip()
                    why = f.get("why_risky", "").strip()
                    fallback = f.get("suggested_fallback", "").strip()

                    label_prefix = "~~" if is_dismissed else ""
                    label_suffix = "~~ *(dismissed)*" if is_dismissed else ""
                    expander_label = (
                        f"{label_prefix}{i}. [{severity}] {category}{label_suffix}"
                    )

                    with st.expander(
                        expander_label,
                        expanded=(severity == "CRITICAL" and not is_dismissed),
                    ):
                        if is_dismissed:
                            st.caption("This flag has been dismissed as a false positive.")

                        st.markdown(f"**Why Risky:** {why}")
                        if evidence:
                            st.markdown(f"> *\"{evidence}\"*")
                        if fallback:
                            st.markdown(f"**Suggestion:** `{fallback}`")

                        # Dismiss / Restore button
                        btn_label = "Restore" if is_dismissed else "Dismiss (false positive)"
                        btn_key = f"dismiss_btn_{i}"
                        if st.button(btn_label, key=btn_key):
                            if is_dismissed:
                                st.session_state["dismissed_flags"].discard(i)
                            else:
                                st.session_state["dismissed_flags"].add(i)
                            # Persist to DB immediately
                            dismissed_json = json.dumps(
                                sorted(st.session_state["dismissed_flags"])
                            )
                            save_outputs(
                                contract_id,
                                risk_json_val,
                                st.session_state.get("summary") or "",
                                st.session_state.get("negotiation_email") or "",
                                dismissed_json,
                            )
                            st.rerun()

# ===========================================================================
# TAB 2 — CHAT
# ===========================================================================
with tab2:
    st.subheader("Chat with Contract")

    if not st.session_state.get("current_contract_id"):
        st.info("Please upload a contract in the Review tab first.")
        st.stop()

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    messages_placeholder = st.empty()

    def render_messages():
        with messages_placeholder.container():
            for msg in st.session_state["chat_messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "assistant" and msg.get("context"):
                        with st.expander("View Context"):
                            st.text(msg["context"])

    render_messages()

    prompt = st.chat_input("Ask a question about this contract...")

    if prompt:
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        render_messages()

        try:
            with st.spinner("Thinking..."):
                q_emb = embed_texts([prompt])[0]
                res = semantic_search(
                    collection,
                    q_emb,
                    top_k=top_k,
                    contract_filter=st.session_state.get("current_contract_id"),
                )
                docs = res.get("documents", [[]])[0]
                context_text = "\n\n".join(docs)

                # Last 16 items = 8 full back-and-forth exchanges
                history_str = "\n".join(
                    f"{m['role']}: {m['content']}"
                    for m in st.session_state["chat_messages"][-16:]
                )

                response = run_chat(model_name, context_text, history_str, prompt)

                st.session_state["chat_messages"].append(
                    {"role": "assistant", "content": response, "context": context_text}
                )

            render_messages()

        except Exception as e:
            st.error(f"Chat error: {e}")

        st.stop()

# ===========================================================================
# TAB 3 — NEGOTIATION
# ===========================================================================
with tab3:
    st.subheader("Negotiation Draft")
    risk_json = st.session_state.get("risk_json")
    if not risk_json:
        st.warning("Run Analyze Risk in the Review tab first.")
    else:
        if st.button("Generate Negotiation Email"):
            try:
                with st.spinner("Drafting email..."):
                    email = run_negotiation(
                        model_name,
                        risk_json,
                        vendor_name=vendor,
                        contract_name=st.session_state.get("current_contract_id", "the contract"),
                    )
                st.session_state["negotiation_email"] = email
                cid = st.session_state.get("current_contract_id")
                if cid:
                    dismissed_json = json.dumps(
                        sorted(st.session_state.get("dismissed_flags", set()))
                    )
                    save_outputs(
                        cid, risk_json,
                        st.session_state.get("summary") or "",
                        email,
                        dismissed_json,
                    )
            except Exception as e:
                st.error(f"Draft failed: {e}")

    email = st.session_state.get("negotiation_email")
    if email:
        st.text_area("Email Draft", value=email, height=400)

# ===========================================================================
# TAB 4 — CLAUSE LIBRARY
# ===========================================================================
with tab4:
    st.subheader("Clause Library Search")
    vendors = list_vendors()
    vendor_filter = st.selectbox(
        "Filter by vendor (optional)",
        options=[""] + vendors,
        index=0,
    ) or None
    query = st.text_input("Search clauses (e.g., auto-renewal, termination for convenience)")

    def highlight_query(text: str, q: str) -> str:
        if not q or not text:
            return text
        pattern = re.compile(re.escape(q), re.IGNORECASE)
        return pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text)

    if query:
        try:
            q_emb = embed_texts([query])[0]
            res = semantic_search(collection, q_emb, top_k=top_k, vendor_filter=vendor_filter)

            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]

            if not docs:
                st.warning("No matching clauses found. Try another query.")
                st.stop()

            seen = set()
            for idx, (doc, meta) in enumerate(zip(docs, metas), start=1):
                doc_key = (meta.get("vendor", ""), meta.get("section", ""), doc[:200])
                if doc_key in seen:
                    continue
                seen.add(doc_key)

                v = meta.get("vendor", "Unknown Vendor")
                section = meta.get("section", "Clause")
                title_left = section if vendor_filter else f"{v} • {section}"

                preview = doc.strip()
                preview_short = preview[:450] + ("…" if len(preview) > 450 else "")
                preview_short = highlight_query(preview_short, query)

                with st.container(border=True):
                    st.markdown(f"**{title_left}**")
                    st.caption(
                        f"Result #{idx}"
                        + (f" • Distance: {dists[idx-1]:.3f}" if dists and idx - 1 < len(dists) else "")
                    )
                    st.markdown(preview_short, unsafe_allow_html=True)
                    with st.expander("View full clause"):
                        st.write(doc)

        except Exception as e:
            st.error(f"Search failed: {e}")

# ===========================================================================
# TAB 5 — HISTORY
# ===========================================================================
with tab5:
    st.subheader("Contract History")
    st.caption("All previously analyzed contracts, sorted by most recent. Click Load to restore an analysis.")

    if st.button("Refresh", key="history_refresh"):
        st.rerun()

    contracts = list_contracts()

    if not contracts:
        st.info("No contracts analyzed yet. Upload and analyze a contract in the Review tab.")
    else:
        for row in contracts:
            cid = row["contract_id"]
            score = row["risk_score"]
            score_display = str(score) if score is not None else "—"

            with st.container(border=True):
                col_info, col_score, col_load = st.columns([4, 1, 1])

                with col_info:
                    st.markdown(f"**{row['filename'] or cid}**")
                    st.caption(
                        f"Vendor: {row['vendor_name']}  •  Analyzed: {row['created_at'][:16] if row['created_at'] else '—'}"
                    )

                with col_score:
                    if score is not None:
                        color = "red" if score >= 7 else ("orange" if score >= 4 else "green")
                        st.markdown(
                            f"<span style='font-size:1.4rem;font-weight:bold;color:{color}'>"
                            f"{score_display}/10</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.write("—")

                with col_load:
                    if st.button("Load", key=f"load_{cid}"):
                        # Restore full analysis into session state
                        output_row = load_outputs(cid)
                        if output_row:
                            st.session_state["current_contract_id"] = cid
                            st.session_state["risk_json"] = output_row[0]
                            st.session_state["summary"] = output_row[1]
                            st.session_state["negotiation_email"] = output_row[2]
                            try:
                                dismissed = json.loads(output_row[3] or "[]")
                                st.session_state["dismissed_flags"] = set(dismissed)
                            except Exception:
                                st.session_state["dismissed_flags"] = set()
                            st.success(
                                f"Loaded **{row['filename'] or cid}**. "
                                "Switch to the Review tab to see the analysis."
                            )
                        else:
                            st.warning("No saved analysis found for this contract.")
