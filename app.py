import os
import json
import streamlit as st
import re

from core.ingest import extract_text_from_pdf_with_ocr
from core.chunking import chunk_text
from core.embeddings import embed_texts
from core.vectorstore import get_chroma_client, get_collection, upsert_chunks, semantic_search
from core.agents import run_risk_review, run_summary, run_negotiation, run_chat, _extract_json_obj
from core.retrieval import retrieve_evidence_for_risk
from core.storage import init_db, save_contract, save_outputs, load_outputs, list_vendors
from core.config import ensure_dirs, UPLOADS_DIR, MAX_UPLOAD_MB
from core.playbooks import get_playbook_names, get_playbook_instructions

st.set_page_config(page_title="ClauseSense - Contract Copilot", layout="wide")

# Ensure data dirs exist and DB is ready
ensure_dirs()
init_db()

st.title("ClauseSense — Vendor Risk & Contract Copilot")

# Init vector store
client = get_chroma_client()
collection = get_collection(client)

# Sidebar controls
st.sidebar.header("Settings")
vendor = st.sidebar.text_input("Vendor name", value="Demo Vendor")
model_name = st.sidebar.selectbox("LLM Model (Ollama)", ["llama3.1:8b", "mistral", "phi3:latest", "llama3"], index=0)
top_k = st.sidebar.slider("Search results (top_k)", 3, 15, 5)

st.sidebar.subheader("Risk Playbook")
playbook_name = st.sidebar.selectbox("Select Playbook", get_playbook_names())
playbook_instructions = get_playbook_instructions(playbook_name)
with st.sidebar.expander("View Playbook Rules"):
    st.info(playbook_instructions)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Review", "Chat with Contract", "Negotiation Draft", "Clause Library"])

# --- TAB 1: REVIEW ---
with tab1:
    st.subheader("Upload & Review")
    uploaded = st.file_uploader("Upload contract PDF", type=["pdf"])

    if uploaded:
        # Validate: filename and size
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

        contract_id = uploaded.name.replace(".pdf", "")
        # New upload: clear session for this contract and try loading prior analysis
        if st.session_state.get("current_contract_id") != contract_id:
            st.session_state["current_contract_id"] = contract_id
            st.session_state["risk_json"] = None
            st.session_state["summary"] = None
            st.session_state["negotiation_email"] = None
            st.session_state["chat_messages"] = [] # Reset chat
            row = load_outputs(contract_id)
            if row:
                st.session_state["risk_json"], st.session_state["summary"], st.session_state["negotiation_email"] = row[0], row[1], row[2]

        st.success(f"Uploaded: {uploaded.name}")
        
        # Load Text
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

        # Chunking & Indexing
        with st.spinner("Chunking into clauses/sections..."):
            chunks = chunk_text(text)
        
        st.info(f"Created {len(chunks)} chunks")

        col_idx, col_anl = st.columns(2)
        
        with col_idx:
            if st.button("Index Contract", help="Builds the vector search index"):
                try:
                    with st.spinner("Embedding + indexing..."):
                        texts = [c["text"] for c in chunks]
                        embs = embed_texts(texts)
                        cid = uploaded.name.replace(".pdf", "")
                        upsert_chunks(collection, cid, vendor, chunks, embs)
                        save_contract(cid, vendor, uploaded.name)
                    st.success("Indexed successfully.")
                except Exception as e:
                    st.error(f"Indexing failed: {e}")

        with col_anl:
            if st.button("Analyze Risks", type="primary"):
                try:
                    with st.spinner("Retrieving relevant clauses..."):
                        evidence_text = retrieve_evidence_for_risk(chunks, top_k_per_query=top_k)

                    with st.spinner(f"Running risk review ({playbook_name})..."):
                        risk_json = run_risk_review(model_name, evidence_text, playbook_rules=playbook_instructions)

                    with st.spinner("Generating summary..."):
                        summary = run_summary(model_name, evidence_text)

                    st.session_state["risk_json"] = risk_json
                    st.session_state["summary"] = summary
                    cid = st.session_state.get("current_contract_id") or uploaded.name.replace(".pdf", "")
                    save_contract(cid, vendor, uploaded.name)
                    save_outputs(cid, risk_json, summary, st.session_state.get("negotiation_email") or "")
                except Exception as e:
                    st.error("Analysis failed. Check that Ollama is running.")
                    with st.expander("Error details", expanded=True):
                        st.code(str(e), language="text")
                    st.stop()

        # Display Results
        risk_json_val = st.session_state.get("risk_json")
        if risk_json_val and st.session_state.get("current_contract_id") == contract_id:
            st.divider()
            st.subheader("Summary (Plain English)")
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
                flags = sorted(flags, key=lambda x: sev_rank.get(str(x.get("severity","LOW")).upper(), 0), reverse=True)

                for i, f in enumerate(flags, start=1):
                    category = str(f.get("category", "unknown")).title()
                    severity = str(f.get("severity", "LOW")).upper()
                    evidence = f.get("evidence_quote", "").strip()
                    why = f.get("why_risky", "").strip()
                    fallback = f.get("suggested_fallback", "").strip()

                    color = "red" if severity in ["HIGH", "CRITICAL"] else "orange"
                    with st.expander(f"{i}. [{severity}] {category}", expanded=(severity=="CRITICAL")):
                        st.markdown(f"**Why Risky:** {why}")
                        if evidence:
                            st.markdown(f"> *\"{evidence}\"*")
                        if fallback:
                            st.markdown(f"**Suggestion:** `{fallback}`")

# --- TAB 2: CHAT ---
with tab2:
    st.subheader("Chat with Contract")
    
    if not st.session_state.get("current_contract_id"):
        st.info("Please upload a contract in the Review tab first.")
    else:
        # Chat History
        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = []
            
        for msg in st.session_state["chat_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        if prompt := st.chat_input("Ask a question about this contract..."):
            # Add user message
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # RAG Retrieval
            with st.spinner("Thinking..."):
                try:
                    # Embed and search
                    q_emb = embed_texts([prompt])[0]
                    # Search specifically within THIS contract
                    res = semantic_search(
                        collection, 
                        q_emb, 
                        top_k=top_k, 
                        contract_filter=st.session_state.get("current_contract_id")
                    )
                    
                    # Filter by current document if possible, but metadata structure might need checking.
                    # Assuming basic search for now.
                    docs = res.get("documents", [[]])[0]
                    context_text = "\n\n".join(docs)
                    
                    # Generate Answer
                    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state["chat_messages"][-4:]])
                    response = run_chat(model_name, context_text, history_str, prompt)
                    
                    st.session_state["chat_messages"].append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"):
                        st.markdown(response)
                        with st.expander("View Context"):
                            st.text(context_text)
                            
                except Exception as e:
                    st.error(f"Chat error: {e}")

# --- TAB 3: NEGOTIATION ---
with tab3:
    st.subheader("Negotiation Draft")
    risk_json = st.session_state.get("risk_json")
    if not risk_json:
        st.warning("Run Analyze Risk in the Review tab first.")
    else:
        if st.button("Generate Negotiation Email"):
            try:
                with st.spinner("Drafting email..."):
                    email = run_negotiation(model_name, risk_json)
                st.session_state["negotiation_email"] = email
                cid = st.session_state.get("current_contract_id")
                if cid:
                    save_outputs(cid, risk_json, st.session_state.get("summary") or "", email)
            except Exception as e:
                st.error(f"Draft failed: {e}")

    email = st.session_state.get("negotiation_email")
    if email:
        st.text_area("Email Draft", value=email, height=400)

# --- TAB 4: LIBRARY ---
with tab4:
    st.subheader("Clause Library Search")
    vendors = list_vendors()
    vendor_filter = st.selectbox(
        "Filter by vendor (optional)",
        options=[""] + vendors,
        index=0,
    ) or None
    query = st.text_input("Search clauses (e.g., auto-renewal, termination for convenience)")

    if query:
        try:
            q_emb = embed_texts([query])[0]
            res = semantic_search(collection, q_emb, top_k=top_k, vendor_filter=vendor_filter)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            
            for i, (doc, meta) in enumerate(zip(docs, metas), start=1):
                st.markdown(f"#### {meta.get('vendor', 'Unknown')} | {meta.get('section', 'Clause')}")
                st.info(doc)
        except Exception as e:
            st.error(f"Search failed: {e}")