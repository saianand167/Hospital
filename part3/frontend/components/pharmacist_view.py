import streamlit as st
from components.common import api_get, api_post

def render_pharmacist_view():
    st.title("💊 Pharmacist Verification Panel")
    st.caption("Review & Verify Handwritten / OCR Extracted Medical Prescriptions")

    docs, err = api_get("/documents/unverified")

    if docs:
        st.info(f"📋 **{len(docs)}** Prescription Document(s) Awaiting Verification")
        for doc in docs:
            st.markdown(f"### Document `{doc['document_id']}` (Patient: `{doc['patient_id']}`)")
            st.write(f"**OCR Confidence:** `{doc.get('ocr_confidence', 0)*100:.1f}%` | **Extraction Confidence:** `{doc.get('extraction_confidence', 0)*100:.1f}%`")
            st.text_area("Extracted Raw Text:", value=doc.get("raw_text", ""), disabled=True, key=f"raw_{doc['document_id']}")

            st.markdown("#### Verify & Edit Extracted Medication Details")
            med_data = doc.get("structured_data", {}).get("medications", [])
            edited_meds = st.data_editor(med_data, num_rows="dynamic", key=f"edit_{doc['document_id']}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirm & Verify Record", key=f"v_conf_{doc['document_id']}"):
                    new_struct = {"medications": edited_meds}
                    v_res, err = api_post(f"/documents/{doc['document_id']}/verify", json_data={
                        "verified": True,
                        "structured_data": new_struct
                    })
                    if v_res:
                        st.success("Document verified successfully!")
                        st.rerun()
                    else:
                        st.error(f"Verification error: {err}")
            with col2:
                if st.button("❌ Reject Record", key=f"v_rej_{doc['document_id']}"):
                    v_res, err = api_post(f"/documents/{doc['document_id']}/verify", json_data={
                        "verified": False,
                        "structured_data": {}
                    })
                    if v_res:
                        st.warning("Document marked as rejected.")
                        st.rerun()
            st.divider()
    else:
        st.success("✨ All handwritten/OCR document extractions have been verified! No pending items in queue.")
