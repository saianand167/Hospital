import streamlit as st
from components.common import api_get, api_post, api_get_bytes

def render_patient_view():
    user_data = st.session_state.get("user_data", {})
    patient_id = user_data.get("patient_id", "PAT-000001")
    full_name = user_data.get("full_name") or user_data.get("username", "Patient")
    
    # ── Header Banner ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hero-banner">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <div style="font-size: 0.85rem; font-weight: 700; color: #38BDF8; text-transform: uppercase; letter-spacing: 0.05em;">
                    MediKiosk • Patient Outpatient Portal
                </div>
                <h1 style="margin: 4px 0 6px 0; font-size: 2rem; font-weight: 800; color: #FFFFFF;">
                    Welcome, {full_name}
                </h1>
                <div style="color: #94A3B8; font-size: 0.95rem;">
                    Patient ID: <span class="badge-normal" style="font-family: monospace; font-size: 0.9rem;">{patient_id}</span>
                </div>
            </div>
            <div style="font-size: 3rem; background: rgba(255,255,255,0.06); padding: 12px 18px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
                🏥
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🩺 Clinical Intake & Symptoms", 
        "📑 Medical Document Upload", 
        "👤 My Profile", 
        "📋 Visit History", 
        "💊 My Prescriptions"
    ])

    # ── Tab 1: Interactive Clinical Intake ────────────────────────────────────
    with tab1:
        st.markdown("### 🩺 Intelligent Multilingual Clinical Intake")
        st.caption("Answer simple guided questions about your symptoms before meeting the doctor.")

        # 1. Fetch visits
        visits, _ = api_get(f"/patients/{patient_id}/visits")
        current_visit = visits[0] if visits and visits[0].get("status") != "COMPLETED" else None

        # 2. If no active visit, provide Quick Start Presets
        if not current_visit:
            st.markdown("""
            <div class="med-card">
                <h3 style="margin: 0 0 8px 0; color: #38BDF8;">Start Today's Consultation Visit</h3>
                <p style="color: #94A3B8; margin: 0 0 16px 0;">Select your primary complaint or symptom to begin your automated case-taking:</p>
            </div>
            """, unsafe_allow_html=True)

            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                if st.button("💔 Chest Pain / Discomfort", use_container_width=True, key="preset_chest"):
                    _create_and_start_visit(patient_id, "Cardiology", "Chest pain for 3 days", "en")
            with col_p2:
                if st.button("🌡️ Fever, Chills & Body Ache", use_container_width=True, key="preset_fever"):
                    _create_and_start_visit(patient_id, "General Medicine", "Fever with chills and body ache", "en")
            with col_p3:
                if st.button("🤢 Stomach / Abdominal Pain", use_container_width=True, key="preset_abd"):
                    _create_and_start_visit(patient_id, "Gastroenterology", "Severe abdominal pain", "en")

            col_p4, col_p5 = st.columns(2)
            with col_p4:
                if st.button("😮‍💨 Shortness of Breath / Cough", use_container_width=True, key="preset_breath"):
                    _create_and_start_visit(patient_id, "Pulmonology", "Difficulty breathing with cough", "en")
            with col_p5:
                if st.button("🩺 General Routine Checkup", use_container_width=True, key="preset_gen"):
                    _create_and_start_visit(patient_id, "General Medicine", "General health checkup and fatigue", "en")

            st.divider()
            with st.expander("➕ Or Enter a Custom Symptom / Specialty Department"):
                col_c1, col_c2 = st.columns([1, 2])
                with col_c1:
                    custom_dept = st.selectbox("Department", ["General Medicine", "Cardiology", "Pulmonology", "Gastroenterology", "Orthopedics"])
                with col_c2:
                    custom_complaint = st.text_input("Describe your symptoms:", placeholder="e.g. Headache and dizziness for 2 days")
                
                custom_lang = st.selectbox("Consultation Language", ["English (en)", "Telugu / తెలుగు (te)", "Hindi / हिन्दी (hi)"])
                l_code = "te" if "Telugu" in custom_lang else ("hi" if "Hindi" in custom_lang else "en")

                if st.button("Start Custom Consultation", use_container_width=True):
                    comp = custom_complaint.strip() if custom_complaint else "General consultation"
                    _create_and_start_visit(patient_id, custom_dept, comp, l_code)

        else:
            visit_id = current_visit["visit_id"]
            dept = current_visit.get("department", "General Medicine")
            v_status = current_visit.get("status", "WAITING")

            st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.1); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 12px; padding: 12px 18px; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-weight: 700; color: #38BDF8;">Active Visit:</span> <code>{visit_id}</code> | Department: <b>{dept}</b>
                </div>
                <span class="badge-normal">{v_status}</span>
            </div>
            """, unsafe_allow_html=True)

            # Session State check
            session_key = f"session_data_{visit_id}"
            if session_key not in st.session_state:
                # Fetch or start session
                res, _ = api_post("/history/session/start", json_data={
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "language": "en",
                    "initial_complaint": "Consultation intake"
                })
                if res:
                    st.session_state[session_key] = res

            sess_data = st.session_state.get(session_key, {})
            history_data = sess_data.get("history", {})
            next_q = sess_data.get("next_question")
            is_completed = sess_data.get("is_completed", False)
            triage = history_data.get("triage", sess_data.get("triage", {}))

            # Red flag alert
            if triage.get("flag") == "RED":
                st.markdown("""
                <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 14px; padding: 16px 20px; margin-bottom: 20px;">
                    <div style="color: #F87171; font-weight: 800; font-size: 1.1rem;">🚨 PRIORITY TRIAGE: Red-Flag Alert</div>
                    <div style="color: #FCA5A5; font-size: 0.95rem; margin-top: 4px;">
                        Severe symptoms detected (e.g. chest pain radiating / autonomic symptoms). Clinical nursing team has been flagged for priority assessment.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            if is_completed or not next_q:
                st.markdown("""
                <div class="med-card" style="text-align: center; border-color: rgba(16, 185, 129, 0.4);">
                    <div style="font-size: 3rem; margin-bottom: 8px;">🎉</div>
                    <h2 style="color: #34D399; margin: 0 0 6px 0;">Clinical Intake Completed!</h2>
                    <p style="color: #94A3B8; margin: 0 0 16px 0;">
                        Your structured clinical history has been compiled and saved to your consultation file.
                        The doctor will review your summary upon call-in.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    if st.button("🔄 Redo / Edit Intake Responses", use_container_width=True):
                        res, _ = api_post("/history/session/start", json_data={
                            "patient_id": patient_id,
                            "visit_id": visit_id,
                            "language": "en",
                            "initial_complaint": history_data.get("chief_complaint", {}).get("text", "Checkup")
                        })
                        if res:
                            st.session_state[session_key] = res
                            st.rerun()
                with col_res2:
                    if st.button("📑 Proceed to Upload Documents ➔", use_container_width=True):
                        st.info("Switch to the 'Medical Document Upload' tab above.")

            else:
                # Active Question Card
                curr_q = next_q.get("progress_current", 1)
                tot_q = max(next_q.get("progress_total", 6), 1)
                progress_pct = min(curr_q / tot_q, 1.0)

                st.markdown(f"""
                <div class="question-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="font-size: 0.85rem; font-weight: 700; color: #38BDF8; text-transform: uppercase;">
                            Question {curr_q} of {tot_q}
                        </span>
                        <span style="font-size: 0.85rem; color: #94A3B8;">Section: {next_q.get('section', 'HPI').upper()}</span>
                    </div>
                    <h2 style="margin: 0; font-size: 1.4rem; font-weight: 700; color: #FFFFFF;">
                        {next_q.get('prompt_text')}
                    </h2>
                </div>
                """, unsafe_allow_html=True)

                st.progress(progress_pct)

                field_name = next_q.get("field_name")
                input_type = next_q.get("input_type")
                options = next_q.get("options", [])

                user_ans = None
                touch_val = None

                # 1. Option Chips (if predefined options exist)
                if options:
                    st.markdown("##### Select an Option:")
                    cols = st.columns(min(len(options), 3))
                    for i, opt in enumerate(options):
                        with cols[i % 3]:
                            if st.button(f"🔘 {opt['label']}", key=f"btn_opt_{field_name}_{opt['value']}", use_container_width=True):
                                user_ans = opt["label"]
                                touch_val = opt["value"]

                # 2. Number / Duration Quick Chips
                elif input_type == "number" or "duration" in str(field_name):
                    st.markdown("##### Quick Duration Chips:")
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1:
                        if st.button("1 Day", key=f"num_1_{field_name}", use_container_width=True):
                            user_ans, touch_val = "1 day", "1"
                    with c2:
                        if st.button("2 Days", key=f"num_2_{field_name}", use_container_width=True):
                            user_ans, touch_val = "2 days", "2"
                    with c3:
                        if st.button("3 Days", key=f"num_3_{field_name}", use_container_width=True):
                            user_ans, touch_val = "3 days", "3"
                    with c4:
                        if st.button("1 Week", key=f"num_7_{field_name}", use_container_width=True):
                            user_ans, touch_val = "7 days", "7"
                    with c5:
                        if st.button("2+ Weeks", key=f"num_14_{field_name}", use_container_width=True):
                            user_ans, touch_val = "14 days", "14"

                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.form(f"num_form_{field_name}"):
                        col_n1, col_n2 = st.columns([3, 1])
                        with col_n1:
                            num_in = st.number_input("Or enter exact number of days:", min_value=0, max_value=365, value=1)
                        with col_n2:
                            st.write("")
                            st.write("")
                            if st.form_submit_button("Submit ➔", use_container_width=True):
                                user_ans, touch_val = f"{num_in} days", str(num_in)

                # 3. Yes/No Prompts
                elif input_type == "yes_no":
                    col_y, col_n = st.columns(2)
                    with col_y:
                        if st.button("✅ YES / అవును / हाँ", key=f"yes_{field_name}", use_container_width=True):
                            user_ans, touch_val = "YES", "true"
                    with col_n:
                        if st.button("❌ NO / లేదు / नहीं", key=f"no_{field_name}", use_container_width=True):
                            user_ans, touch_val = "NO", "false"

                # 4. Severity / Pain Scale
                elif input_type == "scale" or "severity" in str(field_name):
                    st.markdown("##### Rate Pain / Severity (0 = Mild/None, 10 = Severe):")
                    scale_val = st.slider("", 0, 10, 5, key=f"slider_{field_name}")
                    if st.button("Confirm Severity Rating ➔", use_container_width=True):
                        user_ans, touch_val = str(scale_val), str(scale_val)

                # 5. Free-text & Voice fallback input
                st.markdown("<br>", unsafe_allow_html=True)
                with st.form(f"text_form_{field_name}"):
                    text_input = st.text_input("Or type your response in any language:", placeholder="e.g. Yes, it radiates to my left arm", key=f"txt_{field_name}")
                    if st.form_submit_button("Submit Text Response ➔"):
                        if text_input.strip():
                            user_ans = text_input.strip()

                # Process answer submission
                if user_ans:
                    msg_res, err = api_post(f"/history/session/{visit_id}/message", json_data={
                        "patient_message": user_ans,
                        "target_field": field_name,
                        "is_touch_input": touch_val is not None,
                        "touch_value": touch_val,
                        "language": "en"
                    })
                    if msg_res:
                        st.session_state[session_key] = msg_res
                        st.rerun()
                    else:
                        st.error(f"Error recording answer: {err}")

            st.divider()
            with st.expander("🔍 View Live Structured History JSON"):
                st.json(history_data)

    # ── Tab 2: Medical Document Upload (Part 2) ───────────────────────────────
    with tab2:
        st.markdown("### 📑 Medical Document OCR & Parameter Extraction")
        st.caption("Upload blood tests (CBC, LFT, KFT), X-rays, or prescriptions for automated digitization.")

        v_list, _ = api_get(f"/patients/{patient_id}/visits")
        current_v = v_list[0] if v_list else None
        v_id_for_doc = current_v["visit_id"] if current_v else f"VIS-{patient_id[-6:]}"

        col_type, col_file = st.columns([1, 2])
        with col_type:
            doc_type = st.selectbox(
                "Document Type Hint", 
                ["LAB_REPORT", "PRESCRIPTION", "HANDWRITTEN_PRESCRIPTION", "XRAY", "DISCHARGE_SUMMARY"]
            )
        with col_file:
            uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])

        if uploaded_file and st.button("🔬 Extract Document Parameters", use_container_width=True):
            with st.spinner("Running OCR & Parameter Extraction Pipeline..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"patient_id": patient_id, "document_type": doc_type, "visit_id": v_id_for_doc}
                res, err = api_post("/documents/upload", json_data=data, files=files)
                if res:
                    st.success(f"✓ Document Processed: `{res['document_id']}`")
                    st.write(f"**Type:** `{res['document_type']}` | **OCR Confidence:** `{res['ocr_confidence']*100:.1f}%`")

                    s_data = res.get("structured_data", {})
                    if "tests" in s_data and s_data["tests"]:
                        st.table(s_data["tests"])
                    elif "medications" in s_data and s_data["medications"]:
                        st.table(s_data["medications"])
                    else:
                        st.json(s_data)

                    with st.expander("📄 View Raw OCR Text"):
                        st.text(res.get("raw_text", ""))
                else:
                    st.error(f"Upload failed: {err}")

    # ── Tab 3: Profile ────────────────────────────────────────────────────────
    with tab3:
        st.markdown("### 👤 Patient Profile & Demographics")
        patient, _ = api_get(f"/patients/{patient_id}")
        if patient:
            st.markdown(f"""
            <div class="med-card">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
                    <div><span style="color: #94A3B8;">Patient ID</span><br><b style="color: #38BDF8; font-size: 1.1rem;">{patient['patient_id']}</b></div>
                    <div><span style="color: #94A3B8;">Full Name</span><br><b style="color: #F8FAFC; font-size: 1.1rem;">{patient['name']}</b></div>
                    <div><span style="color: #94A3B8;">Gender</span><br><b style="color: #F8FAFC;">{patient.get('gender', 'N/A')}</b></div>
                    <div><span style="color: #94A3B8;">Date of Birth</span><br><b style="color: #F8FAFC;">{patient.get('date_of_birth', 'N/A')}</b></div>
                    <div><span style="color: #94A3B8;">Phone</span><br><b style="color: #F8FAFC;">{patient.get('phone', 'N/A')}</b></div>
                    <div><span style="color: #94A3B8;">Preferred Language</span><br><b style="color: #F8FAFC;">{patient.get('preferred_language', 'English')}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Loading profile details...")

    # ── Tab 4: Visit History ──────────────────────────────────────────────────
    with tab4:
        st.markdown("### 📋 Previous Consultation Encounters")
        all_visits, _ = api_get(f"/patients/{patient_id}/visits")
        if all_visits:
            for v in all_visits:
                v_date = v.get("visit_date", "")[:10]
                with st.expander(f"🗓️ Visit {v['visit_id']} ({v_date}) • {v.get('department')} • Status: {v.get('status')}"):
                    st.write(f"**Priority:** {v.get('priority')}")
                    ch, _ = api_get(f"/history/{v['visit_id']}")
                    if ch:
                        st.json(ch.get("history_json", {}))
                    else:
                        st.caption("No history logged.")
        else:
            st.info("No prior visits recorded.")

    # ── Tab 5: Prescriptions ──────────────────────────────────────────────────
    with tab5:
        st.markdown("### 💊 Digital Prescriptions & Doctor Orders")
        rxs, _ = api_get(f"/patients/{patient_id}/prescriptions")
        if rxs:
            for rx in rxs:
                st.markdown(f"#### Order `{rx['prescription_id']}` (Visit: {rx['visit_id']})")
                st.write(f"**Status:** `{rx['status']}` | Doctor: `{rx['doctor_id']}`")
                if rx.get("items"):
                    st.table(rx["items"])
                
                pdf_bytes, _ = api_get_bytes(f"/prescriptions/{rx['prescription_id']}/pdf")
                if pdf_bytes:
                    st.download_button(
                        "📥 Download Official PDF Prescription",
                        data=pdf_bytes,
                        file_name=f"{rx['prescription_id']}.pdf",
                        mime="application/pdf",
                        key=f"btn_dl_{rx['prescription_id']}"
                    )
                st.divider()
        else:
            st.info("No active prescriptions.")


def _create_and_start_visit(patient_id: str, department: str, complaint: str, language: str):
    """Helper to create a visit and immediately launch the clinical history intake session."""
    new_v, err = api_post("/visits", json_data={
        "patient_id": patient_id,
        "department": department,
        "priority": "NORMAL"
    })
    if new_v:
        visit_id = new_v["visit_id"]
        # Start history session immediately
        res, _ = api_post("/history/session/start", json_data={
            "patient_id": patient_id,
            "visit_id": visit_id,
            "language": language,
            "initial_complaint": complaint
        })
        if res:
            st.session_state[f"session_data_{visit_id}"] = res
        st.rerun()
    else:
        st.error(f"Could not create visit: {err}")
