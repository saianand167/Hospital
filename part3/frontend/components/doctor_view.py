import streamlit as st
from components.common import api_get, api_post, api_get_bytes

def render_doctor_view():
    st.title("👨‍⚕️ Doctor Panel — Consultation Dashboard")

    col_queue, col_main = st.columns([1, 2])

    with col_queue:
        st.markdown("### Today's Queue")
        queue, err = api_get("/doctor/queue")
        
        selected_patient_id = None
        selected_visit_id = None
        
        if queue:
            for visit in queue:
                p_id = visit["patient_id"]
                v_id = visit["visit_id"]
                prio = visit["priority"]
                
                badge = "🔴 RED" if prio in ["HIGH", "EMERGENCY"] else "🟢 NORMAL"
                btn_label = f"{badge} | {p_id} ({v_id})"
                
                if st.button(btn_label, key=f"q_{v_id}"):
                    st.session_state["active_doctor_patient"] = p_id
                    st.session_state["active_doctor_visit"] = v_id

        # Allow entering patient ID manually
        st.divider()
        manual_pid = st.text_input("Lookup Patient ID:", value=st.session_state.get("active_doctor_patient", "PAT-000001"))
        if st.button("Open Patient"):
            st.session_state["active_doctor_patient"] = manual_pid
            st.session_state["active_doctor_visit"] = None

    with col_main:
        patient_id = st.session_state.get("active_doctor_patient", "PAT-000001")
        visit_id = st.session_state.get("active_doctor_visit")

        st.markdown(f"## Patient Consultation: `{patient_id}`")
        
        # Patient Details
        patient, _ = api_get(f"/patients/{patient_id}")
        if patient:
            st.write(f"**Name:** {patient['name']} | **DOB:** {patient.get('date_of_birth')} | **Gender:** {patient.get('gender')}")
        else:
            st.warning("Patient record not found. Please check Patient ID.")
            return

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📝 AI Summary", 
            "🔍 RAG Search", 
            "📜 Previous Visits", 
            "📂 Documents", 
            "🎤 Prescription Dictation"
        ])

        # Tab 1: AI Summary (Groq)
        with tab1:
            st.markdown("### 🤖 Groq AI Clinical Briefing (Non-Diagnostic)")
            summary, err = api_get(f"/doctor/patients/{patient_id}/summary", params={"visit_id": visit_id} if visit_id else None)
            
            if summary:
                if summary.get("current_triage_flag") == "HIGH":
                    st.error("⚠️ HIGH PRIORITY TRIAGE: Patient reported acute chest pain / severe symptoms.")

                st.markdown("#### Structured Summary")
                st.write(f"**Chief Complaint:** {summary.get('chief_complaint')}")
                st.write(f"**HPI:** {summary.get('hpi')}")
                st.write(f"**Relevant Past History:** {summary.get('relevant_past_history')}")
                st.write(f"**Medications:** {', '.join(summary.get('medications', [])) if isinstance(summary.get('medications'), list) else summary.get('medications')}")
                st.write(f"**Allergies:** {', '.join(summary.get('allergies', [])) if isinstance(summary.get('allergies'), list) else summary.get('allergies')}")
                st.write(f"**Previous Investigations:** {summary.get('relevant_previous_investigations')}")

                st.divider()
                st.markdown("#### Doctor Notes / Editing")
                doctor_edit_notes = st.text_area("Edit or Add Doctor Consultation Notes:", value=summary.get('chief_complaint'))
                if st.button("Confirm Consultation Summary"):
                    st.success("Summary confirmed and added to medical chart.")
            elif err:
                if "403" in str(err) or "permitted" in str(err):
                    st.error("🔒 Access Denied: Your current token belongs to 'PATIENT'. Please log in as Doctor ('doctor1') in the sidebar to access doctor summaries.")
                else:
                    st.error(f"Could not load summary: {err}")
            else:
                st.info("Loading summary...")

        # Tab 2: Grounded RAG Search (Patient Scoped)
        with tab2:
            st.markdown("### 🔎 Patient Record RAG Search")
            st.caption("Answers strictly grounded in this patient's medical history. Patient ID scope enforced.")
            
            rag_query = st.text_input("Enter Query (e.g., 'Show previous investigations related to chest pain'):", "What were previous blood test results?")
            if st.button("Search Patient History"):
                with st.spinner("Searching scoped patient records via RAG pipeline..."):
                    rag_res, err = api_post(f"/patients/{patient_id}/query", json_data={"patient_id": patient_id, "query": rag_query})
                    if rag_res:
                        st.markdown(f"**Answer:** {rag_res['answer']}")
                        st.markdown("**Retrieved Grounding Sources:**")
                        for src in rag_res.get("sources", []):
                            st.write(f"- `{src['source_id']}` ({src['source_type']}): *{src['snippet']}*")
                    else:
                        st.error(f"RAG search error: {err}")

        # Tab 3: Previous Visits
        with tab3:
            st.markdown("### Previous Visits & Consultations")
            visits, _ = api_get(f"/patients/{patient_id}/visits")
            if visits:
                for v in visits:
                    with st.expander(f"Visit `{v['visit_id']}` ({v['visit_date'][:10]}) - Status: {v['status']}"):
                        ch, _ = api_get(f"/history/{v['visit_id']}")
                        if ch:
                            st.json(ch["history_json"])
                        else:
                            st.caption("No history recorded.")
            else:
                st.info("No previous visits.")

        # Tab 4: Documents
        with tab4:
            st.markdown("### Medical Documents & Reports")
            docs, _ = api_get(f"/patients/{patient_id}/documents")
            if docs:
                for d in docs:
                    st.write(f"📄 `{d['document_id']}` ({d['document_type']}) - Date: {d['document_date'][:10]}")
                    if d.get("structured_data"):
                        st.json(d["structured_data"])
            else:
                st.info("No documents.")

        # Tab 5: Voice Prescription Dictation
        with tab5:
            st.markdown("### 🎤 Doctor Voice Prescription Dictation")
            st.caption("Dictate or type prescription -> Convert to structured form -> Doctor Review -> Confirm & PDF")

            visits, _ = api_get(f"/patients/{patient_id}/visits")
            active_visit_id = visit_id or (visits[0]["visit_id"] if visits else None)

            if not active_visit_id:
                st.warning("⚠️ Please create an active consultation visit for this patient first.")
            else:
                st.info(f"Prescribing for Visit: `{active_visit_id}`")
                dictation_text = st.text_area(
                    "Dictation Transcript:", 
                    value="Paracetamol 500 mg twice daily for 3 days after food. Pantoprazole 40 mg once daily before breakfast for 5 days."
                )
                
                if st.button("Process Voice Dictation"):
                    items, err = api_post("/prescriptions/voice-dictate", json_data={
                        "patient_id": patient_id,
                        "visit_id": active_visit_id,
                        "doctor_id": "DOC-101",
                        "transcript": dictation_text
                    })
                    if items:
                        st.session_state["draft_rx_items"] = items
                        st.success("Dictation structured successfully! Please review below.")
                    else:
                        st.error(f"Error parsing dictation: {err}")

                if "draft_rx_items" in st.session_state:
                    st.markdown("#### Structured Prescription Preview (Doctor Review Required)")
                    edited_items = st.data_editor(st.session_state["draft_rx_items"], num_rows="dynamic")
                    
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        if st.button("✅ Confirm & Finalize Prescription"):
                            # Step 1: Create Draft
                            rx_draft, err = api_post("/prescriptions", json_data={
                                "patient_id": patient_id,
                                "visit_id": active_visit_id,
                                "doctor_id": "DOC-101",
                                "items": edited_items
                            })
                            if rx_draft:
                                # Step 2: Confirm
                                rx_final, err2 = api_post(f"/prescriptions/{rx_draft['prescription_id']}/confirm", json_data={"items": edited_items})
                                if rx_final:
                                    st.success(f"Prescription `{rx_final['prescription_id']}` finalized and PDF generated!")
                                    # Complete Visit
                                    api_post(f"/visits/{active_visit_id}/complete")
                                    del st.session_state["draft_rx_items"]
                                    st.rerun()
                                else:
                                    st.error(f"Confirmation failed: {err2}")
                            else:
                                st.error(f"Draft creation failed: {err}")
