import streamlit as st
import asyncio
import json
import hashlib
from typing import Optional
from app.services.history_service import HistoryService
from app.clinical.question_engine import ClinicalQuestionEngine
from app.models.history import ClinicalHistoryJSON
from app.llm.client import LLMClient
from app.asr.tts import TextToSpeechProvider

def render_active_consultation():
    visit_id = st.session_state.get("active_visit_id")
    user = st.session_state.get("user", {})
    user_id = user.get("user_id", "USR-000001")

    if not visit_id:
        st.warning("No active consultation found.")
        if st.button("⬅ Return to Dashboard"):
            st.session_state.current_screen = "dashboard"
            st.rerun()
        return

    history = HistoryService.get_session(visit_id)
    if not history:
        history, _ = HistoryService.start_session(user_id=user_id, visit_id=visit_id)

    # Model status badge
    model_status = LLMClient.get_model_status()

    # Top Header & Language Bar
    top_col1, top_col2 = st.columns([3, 2])
    with top_col1:
        st.markdown(f"""
            <div style="display:flex; flex-direction:column; gap:4px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <h3 style="margin:0; color:#0f172a; font-weight:800;">Consultation: {visit_id}</h3>
                    <span style="background:{model_status.get('badge_color', '#10b981')}15; color:{model_status.get('badge_color', '#10b981')}; border:1px solid {model_status.get('badge_color', '#10b981')}40; padding:2px 8px; border-radius:9999px; font-weight:800; font-size:0.75rem;">
                        🤖 {model_status.get('provider')} ({model_status.get('status')})
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)
    with top_col2:
        # Language Switcher
        langs = [("en", "English"), ("te", "తెలుగు"), ("hi", "हिन्दी")]
        current_lang_idx = 0
        for idx, (code, _) in enumerate(langs):
            if code == history.language:
                current_lang_idx = idx
                break
        
        selected_lang_tuple = st.selectbox(
            "Language / భాష",
            langs,
            index=current_lang_idx,
            format_func=lambda x: x[1],
            key="lang_switcher",
            label_visibility="collapsed"
        )
        if selected_lang_tuple[0] != history.language:
            history.language = selected_lang_tuple[0]
            st.rerun()

    st.divider()

    # Triage Flag Alert Check
    triage = history.triage
    is_red_flag = triage.flag == "RED" and triage.priority

    if is_red_flag:
        st.markdown(f"""
            <div style="background: #fff1f2; border: 3px solid #e11d48; border-radius: 20px; padding: 24px; color: #9f1239; margin-bottom: 24px; box-shadow: 0 10px 25px -5px rgba(225, 29, 72, 0.2);">
                <div style="display:flex; align-items:center; gap:12px;">
                    <div style="font-size:2.5rem;">🚨</div>
                    <div>
                        <h2 style="margin:0; color:#9f1239; font-size:1.5rem; font-weight:900;">Priority Clinical Attention Required</h2>
                        <p style="margin:4px 0 0 0; font-size:1rem; opacity:0.95;">
                            <b>Trigger Reasons:</b> {', '.join(triage.reason_codes)}
                        </p>
                    </div>
                </div>
                <div style="margin-top:14px; font-size:0.95rem; background:rgba(255,255,255,0.8); padding:12px 16px; border-radius:12px;">
                    Nursing and emergency clinical staff have been notified. Routine history collection has been paused for patient safety.
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Display Conversation History Waterfall
    answers = HistoryService.get_conversation_history(visit_id)
    if answers:
        st.markdown("#### 💬 Consultation Conversation History")
        for ans in answers:
            mode_icon = "🎤" if ans.input_mode == "voice" else "👆" if ans.input_mode == "touch" else "⌨"
            st.markdown(f"""
                <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 14px 18px; margin-bottom: 10px;">
                    <div style="color: #0d9488; font-size: 0.85rem; font-weight: 800; text-transform: uppercase;">
                        MediKiosk: {ans.question_text}
                    </div>
                    <div style="color: #1e293b; font-size: 1.05rem; font-weight: 600; margin-top: 4px; display:flex; justify-content:space-between; align-items:center;">
                        <span>{ans.answer_text}</span>
                        <span style="font-size:0.75rem; color:#64748b; background:#f1f5f9; padding:2px 8px; border-radius:9999px;">
                            {mode_icon} {ans.input_mode.upper()}
                        </span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.divider()

    # Active Question Asking
    if not history.metadata.completed and not is_red_flag:
        next_prompt, is_completed = ClinicalQuestionEngine.get_next_question(history)
        
        if is_completed or not next_prompt:
            history.metadata.completed = True
            HistoryService._finalize_session(history)
            st.rerun()
            return

        # Progress Indicator
        curr = next_prompt.progress_current
        total = next_prompt.progress_total
        st.progress(curr / max(1, total))
        st.caption(f"📋 Question **{curr} of {total}** • Section: **{next_prompt.section.upper()}**")

        # Question Card
        col_q, col_audio_btn = st.columns([5, 1])
        with col_q:
            st.markdown(f"""
                <div style="background: #ffffff; border: 2px solid #0d9488; border-radius: 20px; padding: 22px; margin-bottom: 16px; box-shadow: 0 10px 15px -3px rgba(13, 148, 136, 0.08);">
                    <span style="color: #0d9488; font-weight: 800; font-size: 0.85rem; text-transform: uppercase;">Current Question</span>
                    <h2 style="margin: 6px 0 0 0; color: #0f172a; font-size: 1.45rem; font-weight: 800;">
                        {next_prompt.prompt_text}
                    </h2>
                </div>
            """, unsafe_allow_html=True)
        
        with col_audio_btn:
            # Question TTS Speaker Button
            if st.button("🔊 Listen", key=f"btn_tts_{curr}", use_container_width=True, help="Listen to the question"):
                with st.spinner("Speaking..."):
                    audio_bytes = asyncio.run(TextToSpeechProvider.synthesize(next_prompt.prompt_text, language=history.language))
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3", autoplay=True)

        target_field = next_prompt.field_name
        question_text = next_prompt.prompt_text
        options = next_prompt.options
        input_type = next_prompt.input_type

        input_key = f"ans_text_val_{curr}"
        audio_hash_key = f"audio_processed_hash_{curr}"
        if input_key not in st.session_state:
            st.session_state[input_key] = ""

        # ---------------- INPUT MODES ----------------

        # 1. Touchscreen Options (Direct selection)
        if options:
            st.markdown("##### 👆 Touch an Option:")
            cols = st.columns(min(len(options), 4))
            for idx, opt in enumerate(options):
                with cols[idx % len(cols)]:
                    if st.button(opt["label"], key=f"btn_opt_{opt['value']}_{idx}", use_container_width=True):
                        asyncio.run(HistoryService.process_message(
                            visit_id=visit_id,
                            patient_message=opt["label"],
                            target_field=target_field,
                            is_touch_input=True,
                            touch_value=opt["value"],
                            question_text=question_text,
                            input_mode="touch"
                        ))
                        st.session_state[input_key] = ""
                        st.rerun()

        # 2. Pain Scale Slider
        if input_type == "scale":
            st.markdown("##### 🔢 Select Pain Scale Rating (0 to 10):")
            scale_val = st.slider("Severity Scale", 0, 10, 5, step=1, key="scale_slider")
            if st.button("Confirm Severity Rating ➔", key="btn_submit_scale", use_container_width=True):
                asyncio.run(HistoryService.process_message(
                    visit_id=visit_id,
                    patient_message=str(scale_val),
                    target_field=target_field,
                    is_touch_input=True,
                    touch_value=str(scale_val),
                    question_text=question_text,
                    input_mode="touch"
                ))
                st.session_state[input_key] = ""
                st.rerun()

        # 3. Live Microphone Recording Input (Local faster-whisper)
        st.markdown("##### 🎤 Speak Your Answer (Voice AI):")
        try:
            audio_data = st.audio_input("Record speech with microphone", key=f"mic_{curr}")
            if audio_data is not None:
                audio_bytes = audio_data.read()
                if audio_bytes and len(audio_bytes) > 50:
                    curr_hash = hashlib.md5(audio_bytes).hexdigest()
                    if st.session_state.get(audio_hash_key) != curr_hash:
                        with st.spinner("🎙️ Transcribing voice in real-time..."):
                            transcribed_text = asyncio.run(HistoryService._asr_provider.transcribe(audio_bytes, language=history.language))
                        if transcribed_text:
                            st.session_state[input_key] = transcribed_text
                            st.session_state[audio_hash_key] = curr_hash
                            st.rerun()
        except AttributeError:
            st.info("Browser microphone active.")

        # 4. Answer Input Box (Voice Transcript or Typed)
        st.markdown("##### ⌨ Answer (Voice Transcript / Typed Response):")
        
        # Display badge if recognized from voice
        if st.session_state.get(input_key):
            st.info(f"🎙️ Recognized Voice: **\"{st.session_state[input_key]}\"** — Click *Submit Answer* to proceed or edit below.")

        with st.form(key=f"text_form_{curr}", clear_on_submit=False):
            user_text = st.text_input(
                "Your Answer",
                value=st.session_state.get(input_key, ""),
                placeholder="Transcribed voice will appear here, or type your answer...",
                label_visibility="collapsed"
            )
            
            c_sub, c_clr = st.columns([3, 1])
            with c_sub:
                submit_btn = st.form_submit_button("Submit Answer ➔", use_container_width=True, type="primary")
            with c_clr:
                clear_btn = st.form_submit_button("Clear", use_container_width=True)

            if clear_btn:
                st.session_state[input_key] = ""
                st.rerun()

            if submit_btn and user_text.strip():
                with st.spinner("Processing clinical response..."):
                    asyncio.run(HistoryService.process_message(
                        visit_id=visit_id,
                        patient_message=user_text.strip(),
                        target_field=target_field,
                        question_text=question_text,
                        input_mode="voice" if st.session_state.get(audio_hash_key) else "text"
                    ))
                st.session_state[input_key] = ""
                st.rerun()

    # ---------------- COMPLETED STATE ----------------
    if history.metadata.completed or is_red_flag:
        st.success("✅ Clinical History Intake Completed.")
        
        hpi = history.hpi
        cc = history.chief_complaint

        st.markdown("### 📋 Final Structured Intake Summary")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Chief Complaint", (cc.text or "General").title())
        with c2:
            st.metric("Duration", f"{hpi.duration_days or 'N/A'} Days" if hpi.duration_days else "N/A")
        with c3:
            st.metric("Severity", f"{hpi.severity}/10" if hpi.severity is not None else "N/A")
        with c4:
            t_color = "red" if triage.flag == "RED" else "orange" if triage.flag == "YELLOW" else "green"
            st.markdown(f"**Triage Flag**<br><span style='color:{t_color}; font-weight:800; font-size:1.4rem;'>● {triage.flag}</span>", unsafe_allow_html=True)

        st.divider()
        
        # Display Clinical JSON Payload
        with st.expander("🔍 View Complete Clinical History JSON (SIH26047 Standard)", expanded=True):
            st.json(history.model_dump())

        # Action Buttons
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            if st.button("🔄 Start Another Consultation", use_container_width=True):
                st.session_state.active_visit_id = None
                st.session_state.current_screen = "dashboard"
                st.rerun()
        with col_a2:
            if st.button("📊 Return to Patient Dashboard", use_container_width=True):
                st.session_state.current_screen = "dashboard"
                st.rerun()
