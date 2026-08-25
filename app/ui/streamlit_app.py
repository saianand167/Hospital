import sys
from pathlib import Path

# Ensure hospital directory is in sys.path
hospital_root = Path(__file__).resolve().parent.parent.parent
if str(hospital_root) not in sys.path:
    sys.path.insert(0, str(hospital_root))

import streamlit as st
from app.ui.components import apply_kiosk_theme
from app.ui.login import render_login_screen
from app.ui.dashboard import render_dashboard
from app.ui.consultation import render_active_consultation
from app.services.consultation_service import ConsultationService

st.set_page_config(
    page_title="MediKiosk - Clinical History Intake",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

apply_kiosk_theme()

# Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "current_screen" not in st.session_state:
    st.session_state.current_screen = "login"
if "active_visit_id" not in st.session_state:
    st.session_state.active_visit_id = None
if "pending_audio_transcript" not in st.session_state:
    st.session_state.pending_audio_transcript = None

# Screen Navigation Router
if not st.session_state.authenticated or st.session_state.current_screen == "login":
    render_login_screen()

elif st.session_state.current_screen == "dashboard":
    render_dashboard()

elif st.session_state.current_screen == "active_consultation":
    render_active_consultation()

elif st.session_state.current_screen == "consultation_history":
    user = st.session_state.get("user", {})
    user_id = user.get("user_id", "USR-000001")
    
    st.markdown("### 📋 My Consultation History")
    if st.button("⬅ Back to Dashboard"):
        st.session_state.current_screen = "dashboard"
        st.rerun()
    st.divider()

    consultations = ConsultationService.get_user_consultations(user_id)
    if not consultations:
        st.info("No prior consultations recorded.")
    else:
        for c in consultations:
            with st.expander(f"📁 {c.visit_id} — {(c.current_complaint or 'General Intake').title()} ({c.started_at})"):
                st.markdown(f"**Status:** `{c.status}` | **Triage Flag:** `{c.triage_flag}` | **Language:** `{c.language}`")
                
                details = ConsultationService.get_consultation_details(c.visit_id)
                if details and details.get("answers"):
                    st.markdown("##### 💬 Questions & Answers:")
                    for a in details["answers"]:
                        st.markdown(f"- **Q:** {a['question_text']}\n  - **A ({a['input_mode']}):** {a['answer_text']}")
                
                if details and details.get("final_history"):
                    st.markdown("##### 📄 Official History JSON:")
                    st.json(details["final_history"])
