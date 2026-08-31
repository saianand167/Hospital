"""
MediKiosk — Part 2 Streamlit Frontend
Medical Document Digitization & Structured Extraction
"""
import streamlit as st
import requests
import json

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="MediKiosk — Document Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.section-header {
    font-size: 14px; font-weight: 700; color: #94a3b8;
    text-transform: uppercase; letter-spacing: .08em; margin: 18px 0 8px;
}
.badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 12px; font-weight: 600; margin-right: 6px;
}
.badge-lab  { background:#0ea5e9; color:white; }
.badge-rx   { background:#8b5cf6; color:white; }
.badge-dc   { background:#f59e0b; color:#000;  }
.badge-img  { background:#10b981; color:white; }
.badge-path { background:#ef4444; color:white; }
.badge-opd  { background:#6366f1; color:white; }
.badge-unkn { background:#6b7280; color:white; }
.badge-ok   { background:#22c55e; color:white; }
.badge-warn { background:#f59e0b; color:#000;  }
.badge-fail { background:#ef4444; color:white; }
.badge-vrfy { background:#f97316; color:white; }
.abnormal   { color:#ef4444; font-weight:600; }
.normal-val { color:#22c55e; }
.metric-box { background:#1e293b; border-radius:8px; padding:12px 16px; text-align:center; }
.metric-val { font-size:24px; font-weight:700; color:#38bdf8; }
.metric-lbl { font-size:12px; color:#64748b; margin-top:2px; }
.warn-box   { background:#7c2d12; border:1px solid #ea580c; border-radius:8px;
              padding:12px 16px; color:#fed7aa; font-size:13px; margin:8px 0; }
.info-box   { background:#0c4a6e; border:1px solid #0284c7; border-radius:8px;
              padding:12px 16px; color:#bae6fd; font-size:13px; margin:8px 0; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER / RENDER FUNCTIONS  (must be defined BEFORE any page logic calls them)
# ═══════════════════════════════════════════════════════════════════════════════

def _badge(label: str, kind: str = "ok") -> str:
    return f'<span class="badge badge-{kind}">{label}</span>'


def _doc_type_badge(doc_type: str) -> str:
    mapping = {
        "LAB_REPORT":            ("🔬 LAB REPORT",        "lab"),
        "PRESCRIPTION":          ("💊 PRESCRIPTION",       "rx"),
        "DISCHARGE_SUMMARY":     ("🏥 DISCHARGE SUMMARY",  "dc"),
        "IMAGING_REPORT":        ("🩻 IMAGING REPORT",     "img"),
        "PATHOLOGY_REPORT":      ("🧫 PATHOLOGY",          "path"),
        "OPD_NOTE":              ("📋 OPD NOTE",           "opd"),
        "UNKNOWN":               ("❓ UNKNOWN",            "unkn"),
        "OTHER_MEDICAL_DOCUMENT":("📄 OTHER",              "unkn"),
    }
    label, kind = mapping.get(doc_type, (doc_type, "unkn"))
    return _badge(label, kind)


def _status_badge(status: str) -> str:
    mapping = {
        "success":              ("✅ Extracted",           "ok"),
        "partial":              ("⚠️ Partial",             "warn"),
        "failed":               ("❌ Failed",              "fail"),
        "verification_required":("🔍 Needs Verification",  "vrfy"),
        "verified":             ("✔️ Verified",            "ok"),
    }
    label, kind = mapping.get(status, (status, "warn"))
    return _badge(label, kind)


def _render_lab_report(data: dict):
    sections = data.get("sections", [])
    if not sections:
        st.warning("No lab sections extracted. Document may require manual review.")
        return
    total = sum(len(s.get("tests", [])) for s in sections)
    abn   = sum(1 for s in sections for t in s.get("tests", []) if t.get("abnormal") is True)
    c1, c2 = st.columns(2)
    c1.metric("Total Tests", total)
    c2.metric("Abnormal Values", abn)
    st.info("ℹ️ Values outside the reference range are flagged for physician review. This is NOT a diagnosis.")
    for sec in sections:
        sname    = sec.get("section_name", "Unknown")
        specimen = sec.get("specimen", "")
        tests    = sec.get("tests", [])
        st.markdown(f'<div class="section-header">🔬 {sname}{"  •  " + specimen if specimen else ""}</div>',
                    unsafe_allow_html=True)
        if not tests:
            st.caption("No tests in this section.")
            continue
        hdr = st.columns([3, 2, 2, 3, 1])
        hdr[0].markdown("**Test Name**"); hdr[1].markdown("**Value**")
        hdr[2].markdown("**Unit**");      hdr[3].markdown("**Reference Range**")
        hdr[4].markdown("**Flag**")
        for t in tests:
            row = st.columns([3, 2, 2, 3, 1])
            row[0].markdown(t.get("name", "—"))
            val = t.get("value"); abn_flag = t.get("abnormal")
            vs  = str(val) if val is not None else "—"
            if abn_flag is True:
                row[1].markdown(f'<span class="abnormal">⚠️ {vs}</span>', unsafe_allow_html=True)
            else:
                row[1].markdown(f'<span class="normal-val">{vs}</span>', unsafe_allow_html=True)
            row[2].markdown(t.get("unit") or "—")
            row[3].markdown(t.get("reference_range") or "—")
            row[4].markdown("🔴" if abn_flag is True else ("🟢" if abn_flag is False else "—"))


def _render_prescription(data: dict, doc_id: str):
    meds = data.get("medications", [])
    if not meds:
        st.warning("No medications extracted. Verification required.")
        return
    st.markdown(f'<div class="section-header">💊 Medications ({len(meds)})</div>', unsafe_allow_html=True)
    for i, m in enumerate(meds, 1):
        with st.expander(f"#{i} — {m.get('name','Unknown')} {m.get('strength','')}"):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Dose:** {m.get('dose') or '—'}")
            c1.markdown(f"**Route:** {m.get('route') or '—'}")
            c1.markdown(f"**Frequency:** {m.get('frequency') or '—'}")
            c2.markdown(f"**Duration:** {m.get('duration') or '—'}")
            c2.markdown(f"**Instructions:** {m.get('instructions') or '—'}")
            c2.markdown(f"**Confidence:** {m.get('confidence', 0):.0%}")
            if m.get("needs_verification"):
                st.warning("⚠️ Low confidence — pharmacist verification required")


def _render_discharge(data: dict):
    st.markdown('<div class="section-header">🏥 Discharge Summary</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(f"**Admission:** {data.get('admission_date') or '—'}")
    c2.markdown(f"**Discharge:** {data.get('discharge_date') or '—'}")
    if data.get("diagnoses"):
        st.markdown("**Diagnoses:**")
        for d in data["diagnoses"]: st.markdown(f"- {d}")
    if data.get("hospital_course"):
        st.markdown(f"**Hospital Course:** {data['hospital_course']}")
    if data.get("medications_on_discharge"):
        st.markdown("**Discharge Medications:**")
        for m in data["medications_on_discharge"]: st.markdown(f"- {m}")
    if data.get("follow_up_instructions"):
        st.info(f"**Follow-up:** {data['follow_up_instructions']}")


def _render_imaging(data: dict):
    st.markdown('<div class="section-header">🩻 Imaging Report</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(f"**Modality:** {data.get('modality') or '—'}")
    c2.markdown(f"**Body Part:** {data.get('body_part') or '—'}")
    if data.get("clinical_indication"):
        st.markdown(f"**Indication:** {data['clinical_indication']}")
    if data.get("findings"):
        st.markdown("**Findings:**"); st.info(data["findings"])
    if data.get("impression"):
        st.markdown("**Impression:**"); st.success(data["impression"])


def _render_pathology(data: dict):
    st.markdown('<div class="section-header">🧫 Pathology Report</div>', unsafe_allow_html=True)
    if data.get("specimen_site"):
        st.markdown(f"**Specimen:** {data['specimen_site']}")
    if data.get("gross_examination"):
        with st.expander("Gross Examination"): st.write(data["gross_examination"])
    if data.get("microscopic_findings"):
        with st.expander("Microscopic Findings"): st.write(data["microscopic_findings"])
    if data.get("pathological_diagnosis"):
        st.markdown("**Pathological Diagnosis:**"); st.info(data["pathological_diagnosis"])


def _render_opd(data: dict):
    st.markdown('<div class="section-header">📋 OPD / Consultation Note</div>', unsafe_allow_html=True)
    if data.get("chief_complaint"):
        st.markdown(f"**Chief Complaint:** {data['chief_complaint']}")
    if data.get("history_of_present_illness"):
        with st.expander("History"): st.write(data["history_of_present_illness"])
    if data.get("examination_findings"):
        with st.expander("Examination"): st.write(data["examination_findings"])
    if data.get("assessment"):  st.markdown(f"**Assessment:** {data['assessment']}")
    if data.get("plan"):        st.markdown(f"**Plan:** {data['plan']}")
    if data.get("follow_up"):   st.info(f"**Follow-up:** {data['follow_up']}")


def _render_document(doc: dict):
    """Main document renderer — calls type-specific sub-renderers."""
    doc_type = doc.get("document_type", "UNKNOWN")
    doc_id   = doc.get("document_id", "")
    conf     = doc.get("confidence", {})
    extr     = doc.get("extraction", {})
    verf     = doc.get("verification", {})
    data     = doc.get("data", {})
    meta     = doc.get("metadata", {})

    # Header
    st.markdown(f"### {doc_id}")
    flags = _doc_type_badge(doc_type) + _status_badge(extr.get("status", "unknown"))
    if verf.get("required") and not verf.get("verified"):
        flags += _badge("⚠️ NEEDS VERIFICATION", "vrfy")
    if verf.get("verified"):
        flags += _badge("✔️ VERIFIED", "ok")
    st.markdown(flags, unsafe_allow_html=True)
    st.caption(f"Uploaded: {doc.get('upload_timestamp','')[:19]}  |  File: {doc.get('file_name','')}")

    # Confidence row
    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="metric-box"><div class="metric-val">{conf.get("ocr",0):.0%}</div>'
                f'<div class="metric-lbl">OCR Confidence</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-box"><div class="metric-val">{conf.get("classification",0):.0%}</div>'
                f'<div class="metric-lbl">Classification</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-box"><div class="metric-val">{conf.get("extraction",0):.0%}</div>'
                f'<div class="metric-lbl">Extraction</div></div>', unsafe_allow_html=True)
    st.divider()

    # Alerts
    if verf.get("required") and not verf.get("verified"):
        st.markdown('<div class="warn-box">⚠️ <b>Human verification required</b> — '
                    'Confidence below threshold. Please review and confirm.</div>', unsafe_allow_html=True)
    if extr.get("message"):
        st.markdown(f'<div class="info-box">ℹ️ {extr["message"]}</div>', unsafe_allow_html=True)

    # Metadata
    with st.expander("📋 Document Metadata", expanded=False):
        mc = st.columns(3)
        mc[0].markdown(f"**Date:** {meta.get('document_date') or 'N/A'}")
        mc[1].markdown(f"**Hospital:** {meta.get('hospital_name') or 'N/A'}")
        mc[2].markdown(f"**Doctor:** {meta.get('doctor_name') or 'N/A'}")
        if meta.get("laboratory_name"):
            st.markdown(f"**Lab:** {meta['laboratory_name']}")

    # Type-specific body
    if doc_type == "LAB_REPORT":
        _render_lab_report(data)
    elif doc_type == "PRESCRIPTION":
        _render_prescription(data, doc_id)
    elif doc_type == "DISCHARGE_SUMMARY":
        _render_discharge(data)
    elif doc_type == "IMAGING_REPORT":
        _render_imaging(data)
    elif doc_type == "PATHOLOGY_REPORT":
        _render_pathology(data)
    elif doc_type == "OPD_NOTE":
        _render_opd(data)
    else:
        st.markdown("**Extracted Data:**")
        if data:
            st.json(data)
        else:
            st.warning("No structured data extracted. Upload the document again after the pipeline fix.")

    # Tabs: OCR text | raw JSON | original file
    tab1, tab2, tab3 = st.tabs(["📝 OCR Text", "🔧 Raw JSON", "📄 Original Document"])
    with tab1:
        raw = doc.get("ocr", {}).get("raw_text", "")
        st.text_area("OCR Text", value=raw or "(no text extracted)", height=250, disabled=True)
    with tab2:
        st.json(doc)
    with tab3:
        st.markdown(f"[⬇️ Download Original Document](http://localhost:8000/documents/{doc_id}/original)")
        st.caption("The original file is preserved on the server unchanged.")

    # Verification panel
    if verf.get("required") and not verf.get("verified"):
        with st.expander("✏️ Staff Verification / Correction", expanded=False):
            corrected = st.text_area("Corrected data (JSON)",
                                     value=json.dumps(data, indent=2), height=280)
            verifier = st.text_input("Verified by", value="Staff")
            if st.button("✅ Confirm Verification", key=f"vrfy_{doc_id}"):
                try:
                    cd = json.loads(corrected)
                    r  = requests.post(f"{API_BASE}/documents/{doc_id}/verify",
                                       json={"corrected_data": cd, "verified_by": verifier}, timeout=10)
                    if r.ok:
                        st.success("Verification saved ✅")
                        st.rerun()
                    else:
                        st.error(f"Error: {r.text}")
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏥 MediKiosk")
    st.markdown("**Part 2 — Document Intelligence**")
    st.divider()
    page       = st.radio("Navigate", ["📤 Upload Document", "📋 View Documents", "👤 Patient Timeline"])
    st.divider()
    patient_id = st.text_input("Patient ID", value="P001")
    visit_id   = st.text_input("Visit ID (optional)", value="")
    language   = st.selectbox("OCR Language", ["eng", "hin", "tel"])
    st.divider()
    try:
        h = requests.get(f"{API_BASE}/health", timeout=2).json()
        st.success(f"Backend ✅  \nOCR: `{h['ocr_provider']}`  \nLLM: `{h['llm_provider']}`")
    except Exception:
        st.error("Backend ❌ — start the server on port 8000")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════════════════════════════

# ── Upload ───────────────────────────────────────────────────────────────────
if page == "📤 Upload Document":
    st.title("📤 Upload Medical Document")
    st.caption("Supported: JPG, PNG, PDF — Lab Reports, Prescriptions, Discharge Summaries, "
               "Imaging Reports, Pathology Reports, OPD Notes")

    uploaded = st.file_uploader(
        "Choose a medical document",
        type=["jpg", "jpeg", "png", "pdf"],
        label_visibility="collapsed",
    )

    if uploaded:
        col1, col2 = st.columns([3, 1])
        col1.info(f"📄 **{uploaded.name}**  ({uploaded.size / 1024:.1f} KB)")
        process_btn = col2.button("🚀 Process", type="primary", use_container_width=True)

        if process_btn:
            params = {"language": language}
            if patient_id: params["patient_id"] = patient_id
            if visit_id:   params["visit_id"]   = visit_id

            with st.spinner("⚙️ Running pipeline: OCR → Classify → Extract → Validate…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/documents/upload",
                        files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                        params=params,
                        timeout=180,
                    )
                    if resp.status_code == 200:
                        doc = resp.json()
                        st.session_state["last_doc"] = doc
                        st.success(f"✅ Processed — **{doc['document_id']}**")
                        _render_document(doc)
                    else:
                        st.error(f"Server error {resp.status_code}: {resp.text}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to backend on port 8000. Is it running?")
                except Exception as e:
                    st.error(f"Error: {e}")

    elif "last_doc" in st.session_state:
        st.subheader("Last Processed Document")
        if st.button("🗑️ Clear"):
            del st.session_state["last_doc"]
            st.rerun()
        else:
            _render_document(st.session_state["last_doc"])


# ── View Documents ────────────────────────────────────────────────────────────
elif page == "📋 View Documents":
    st.title("📋 Document Lookup")
    doc_id = st.text_input("Enter Document ID", placeholder="DOC-XXXXXXXX")
    if doc_id:
        try:
            resp = requests.get(f"{API_BASE}/documents/{doc_id}", timeout=10)
            if resp.status_code == 200:
                _render_document(resp.json())
            else:
                st.error(f"Document not found: {doc_id}")
        except Exception as e:
            st.error(str(e))


# ── Patient Timeline ──────────────────────────────────────────────────────────
elif page == "👤 Patient Timeline":
    st.title(f"👤 Patient Timeline — {patient_id}")
    try:
        resp = requests.get(f"{API_BASE}/patients/{patient_id}/timeline", timeout=10)
        if resp.status_code == 200:
            timeline = resp.json().get("timeline", [])
            if not timeline:
                st.info("No documents found for this patient. Upload a document first.")
            else:
                st.caption(f"{len(timeline)} document(s) on file")
                for item in reversed(timeline):
                    icon = "🔴" if item.get("has_abnormal") else "🟢"
                    label = f"{icon}  {item['date']}  —  {item['document_type']}  —  {item['file_name']}"
                    with st.expander(label):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**Type:** {item['document_type']}")
                        c2.markdown(f"**Status:** {item['extraction_status']}")
                        c3.markdown(f"**Abnormal:** {'🔴 Yes' if item['has_abnormal'] else '🟢 No'}")
                        st.markdown(f"_{item['summary']}_")
                        if st.button("📂 View Full Document", key=f"tl_{item['document_id']}"):
                            r = requests.get(f"{API_BASE}/documents/{item['document_id']}", timeout=10)
                            if r.ok:
                                _render_document(r.json())
        else:
            st.error(f"Timeline fetch failed: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Is it running on port 8000?")
    except Exception as e:
        st.error(str(e))
