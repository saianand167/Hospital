import streamlit as st
from app.services.consultation_service import ConsultationService
from app.services.history_service import HistoryService

def render_dashboard():
    user = st.session_state.get("user", {})
    user_id = user.get("user_id", "USR-000001")
    full_name = user.get("full_name", "Patient")
    lang = user.get("preferred_language", "en")

    # Header Card
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); padding: 24px; border-radius: 20px; color: white; margin-bottom: 20px; box-shadow: 0 10px 15px -3px rgba(13, 148, 136, 0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800;">Welcome, {full_name}</h2>
                    <p style="margin: 4px 0 0 0; opacity: 0.9; font-size: 0.95rem;">
                        Patient ID: <span style="background: rgba(255,255,255,0.25); padding: 2px 8px; border-radius: 6px; font-weight: 700;">{user_id}</span>
                    </p>
                </div>
                <div style="font-size: 2.5rem;">🏥</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Action Buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🚀 Start New Consultation", use_container_width=True):
            # Start fresh consultation session
            history, next_q = HistoryService.start_session(
                user_id=user_id,
                language=lang
            )
            st.session_state.active_visit_id = history.visit_id
            st.session_state.current_screen = "active_consultation"
            st.session_state.pending_audio_transcript = None
            st.rerun()

    with col2:
        if st.button("📋 My Consultations", use_container_width=True):
            st.session_state.current_screen = "consultation_history"
            st.rerun()

    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.current_screen = "login"
            st.rerun()

    st.divider()

    # Recent Consultations Preview
    st.markdown("### 🕒 Recent Consultation Activity")
    consultations = ConsultationService.get_user_consultations(user_id)

    if not consultations:
        st.info("No prior consultations found. Click **'Start New Consultation'** above to begin your intake.")
    else:
        for c in consultations[:3]:
            flag_color = "#10b981" if c.triage_flag == "GREEN" else "#f59e0b" if c.triage_flag == "YELLOW" else "#e11d48"
            st.markdown(f"""
                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-weight: 800; color: #0f172a; font-size: 1.05rem;">{c.visit_id}</span>
                        <span style="color: #64748b; font-size: 0.85rem; margin-left: 8px;">({c.started_at})</span>
                        <div style="color: #334155; font-size: 0.95rem; margin-top: 4px;">
                            Complaint: <b>{(c.current_complaint or 'General Intake').title()}</b>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span style="background: {flag_color}15; color: {flag_color}; border: 1px solid {flag_color}40; padding: 4px 10px; border-radius: 9999px; font-weight: 800; font-size: 0.8rem;">
                            TRIAGE: {c.triage_flag}
                        </span>
                        <div style="color: #64748b; font-size: 0.8rem; margin-top: 4px; text-transform: uppercase;">
                            Status: {c.status}
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
