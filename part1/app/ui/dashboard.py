import streamlit as st
from app.services.consultation_service import ConsultationService
from app.services.history_service import HistoryService

def render_dashboard():
    user = st.session_state.get("user", {})
    user_id = user.get("user_id", "USR-000001")
    full_name = user.get("full_name", "Patient")
    preferred_lang = user.get("preferred_language", "en")

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

    if "part1_pref_mode" not in st.session_state:
        st.session_state.part1_pref_mode = "voice"
    if "part1_pref_lang" not in st.session_state:
        st.session_state.part1_pref_lang = preferred_lang or "en"

    cur_mode = st.session_state.part1_pref_mode
    cur_lang = st.session_state.part1_pref_lang

    # Section A: Interaction Mode
    st.markdown("""
        <div style="background: #ffffff; border: 2px solid #0d9488; border-radius: 18px; padding: 20px; margin-bottom: 16px;">
            <div style="font-size: 0.85rem; font-weight: 800; color: #0d9488; text-transform: uppercase;">
                Section A: How would you like to answer? / సమాధాన విధానం
            </div>
            <h3 style="margin: 6px 0 12px 0; color: #0f172a; font-size: 1.25rem; font-weight: 800;">
                Select your interaction method:
            </h3>
        </div>
    """, unsafe_allow_html=True)

    col_vm, col_tm = st.columns(2)
    with col_vm:
        is_vm = cur_mode == "voice"
        if st.button("🎤 **Voice (Voice AI)**\n\nSpeak answers using microphone" + ("  ✓" if is_vm else ""), key="btn_p1_mode_voice", use_container_width=True):
            st.session_state.part1_pref_mode = "voice"
            st.rerun()

    with col_tm:
        is_tm = cur_mode == "text"
        if st.button("⌨️ **Text (Typing / Touch)**\n\nType or touch options on screen" + ("  ✓" if is_tm else ""), key="btn_p1_mode_text", use_container_width=True):
            st.session_state.part1_pref_mode = "text"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Section B: Language Choice
    st.markdown("""
        <div style="background: #ffffff; border: 2px solid #0d9488; border-radius: 18px; padding: 20px; margin-bottom: 16px;">
            <div style="font-size: 0.85rem; font-weight: 800; color: #0d9488; text-transform: uppercase;">
                Section B: Choose Language / భాషను ఎంచుకోండి / ଭାଷା ଚୟନ କରନ୍ତୁ / भाषा चुनें
            </div>
            <h3 style="margin: 6px 0 12px 0; color: #0f172a; font-size: 1.25rem; font-weight: 800;">
                Which language are you comfortable with?
            </h3>
        </div>
    """, unsafe_allow_html=True)

    col_en, col_te, col_or, col_hi = st.columns(4)

    with col_en:
        is_en = cur_lang == "en"
        if st.button("🇬🇧 **English**" + ("\n\n✓ Selected" if is_en else "\n\nEnglish"), key="btn_start_en", use_container_width=True):
            st.session_state.part1_pref_lang = "en"
            st.rerun()

    with col_te:
        is_te = cur_lang == "te"
        if st.button("🇮🇳 **తెలుగు**" + ("\n\n✓ ఎంపికైంది" if is_te else "\n\nTelugu"), key="btn_start_te", use_container_width=True):
            st.session_state.part1_pref_lang = "te"
            st.rerun()

    with col_or:
        is_or = cur_lang == "or"
        if st.button("🇮🇳 **ଓଡ଼ିଆ**" + ("\n\n✓ ଚୟନିତ" if is_or else "\n\nOdia"), key="btn_start_or", use_container_width=True):
            st.session_state.part1_pref_lang = "or"
            st.rerun()

    with col_hi:
        is_hi = cur_lang == "hi"
        if st.button("🇮🇳 **हिन्दी**" + ("\n\n✓ चयनित" if is_hi else "\n\nHindi"), key="btn_start_hi", use_container_width=True):
            st.session_state.part1_pref_lang = "hi"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Continue Button
    if st.button("🚀 Start Health Interview ➔", key="btn_start_health_intake_p1", use_container_width=True, type="primary"):
        _start_consultation(user_id, st.session_state.part1_pref_lang, st.session_state.part1_pref_mode)

    st.markdown("<br>", unsafe_allow_html=True)

    # Navigation Actions
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("📋 View My Consultations History", use_container_width=True):
            st.session_state.current_screen = "consultation_history"
            st.rerun()
    with col_nav2:
        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.current_screen = "login"
            st.rerun()

    st.divider()

    # Recent Consultations Preview
    st.markdown("### 🕒 Recent Consultation Activity")
    consultations = ConsultationService.get_user_consultations(user_id)

    if not consultations:
        st.info("No prior consultations found. Select preferences above to begin your intake.")
    else:
        for c in consultations[:3]:
            flag_color = "#10b981" if c.triage_flag == "GREEN" else "#f59e0b" if c.triage_flag == "YELLOW" else "#e11d48"
            lang_label = "Telugu (తెలుగు)" if c.language == "te" else "Odia (ଓଡ଼ିଆ)" if c.language == "or" else "Hindi (हिन्दी)" if c.language == "hi" else "English"
            st.markdown(f"""
                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-weight: 800; color: #0f172a; font-size: 1.05rem;">{c.visit_id}</span>
                        <span style="color: #64748b; font-size: 0.85rem; margin-left: 8px;">({c.started_at})</span>
                        <div style="color: #334155; font-size: 0.95rem; margin-top: 4px;">
                            Complaint: <b>{(c.current_complaint or 'General Intake').title()}</b> • Language: <b>{lang_label}</b>
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

def _start_consultation(user_id: str, lang: str, mode: str = "voice"):
    history, next_q = HistoryService.start_session(
        user_id=user_id,
        language=lang
    )
    st.session_state.active_visit_id = history.visit_id
    st.session_state.part1_pref_mode = mode
    st.session_state.current_screen = "active_consultation"
    st.session_state.pending_audio_transcript = None
    st.rerun()
