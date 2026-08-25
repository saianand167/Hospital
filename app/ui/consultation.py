import streamlit as st
import asyncio
import json
from typing import Optional
from app.services.history_service import HistoryService
from app.clinical.question_engine import ClinicalQuestionEngine
from app.models.history import ClinicalHistoryJSON
from app.llm.client import LLMClient

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

        # Question Prompt Card
        st.markdown(f"""
            <div style="background: #ffffff; border: 2px solid #0d9488; border-radius: 20px; padding: 24px; margin-bottom: 20px; box-shadow: 0 10px 15px -3px rgba(13, 148, 136, 0.08);">
                <span style="color: #0d9488; font-weight: 800; font-size: 0.85rem; text-transform: uppercase;">Current Question</span>
                <h2 style="margin: 6px 0 0 0; color: #0f172a; font-size: 1.5rem; font-weight: 800;">
                    {next_prompt.prompt_text}
                </h2>
            </div>
        """, unsafe_allow_html=True)

        target_field = next_prompt.field_name
        question_text = next_prompt.prompt_text
        options = next_prompt.options
        input_type = next_prompt.input_type

        # ---------------- INPUT MODES ----------------
        
        # 1. Pending Voice Confirmation Sub-Flow
        if st.session_state.get("pending_audio_transcript"):
            trans = st.session_state.pending_audio_transcript
            st.markdown(f"""
                <div style="background:#f0fdfa; border:2px dashed #0d9488; border-radius:16px; padding:18px; margin-bottom:16px;">
                    <span style="font-size:0.85rem; font-weight:800; color:#0f766e; text-transform:uppercase;">Recognized Voice Transcript:</span>
                    <h3 style="margin:6px 0 0 0; color:#134e4a; font-size:1.3rem;">"{trans}"</h3>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Use This Answer", key="confirm_transcript", use_container_width=True):
                    asyncio.run(HistoryService.process_message(
                        visit_id=visit_id,
                        patient_message=trans,
                        target_field=target_field,
                        question_text=question_text,
                        input_mode="voice"
                    ))
                    st.session_state.pending_audio_transcript = None
                    st.rerun()
            with c2:
                if st.button("🔄 Record Again", key="re_record", use_container_width=True):
                    st.session_state.pending_audio_transcript = None
                    st.rerun()
            return

        # 2. Touchscreen Options (Direct selection)
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
                        st.rerun()

        # 3. Pain Scale Slider
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
                st.rerun()

        # 4. Live Microphone Recording Input
        st.markdown("##### 🎤 Speak Your Answer (Live Microphone):")
        try:
            audio_data = st.audio_input("Click microphone to record live speech", key=f"mic_{curr}")
            if audio_data is not None:
                audio_bytes = audio_data.read()
                transcribed_text = asyncio.run(HistoryService._asr_provider.transcribe(audio_bytes, language=history.language))
                if transcribed_text:
                    st.session_state.pending_audio_transcript = transcribed_text
                    st.rerun()
        except AttributeError:
            st.info("Browser microphone active. You can also type or use touch options.")

        # 5. Text Input Form
        st.markdown("##### ⌨ Type Your Answer:")
        with st.form(key=f"text_form_{curr}", clear_on_submit=True):
            user_text = st.text_input(
                "Answer",
                placeholder="e.g. I am getting loose motions since yesterday / నాకు రెండు రోజులుగా మోషన్స్ అవుతున్నాయి",
                label_visibility="collapsed"
            )
            submit_btn = st.form_submit_button("Submit Answer ➔", use_container_width=True)
            if submit_btn and user_text.strip():
                asyncio.run(HistoryService.process_message(
                    visit_id=visit_id,
                    patient_message=user_text.strip(),
                    target_field=target_field,
                    question_text=question_text,
                    input_mode="text"
                ))
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
            st.metric("Triage Priority", triage.flag)

        with st.expander("🔍 View Official Part 1 Clinical History JSON Contract (For Part 3 Integration)", expanded=True):
            st.json(history.model_dump())

        b1, b2 = st.columns(2)
        with b1:
            st.download_button(
                "📥 Download Official History JSON",
                data=json.dumps(history.model_dump(), indent=2, ensure_ascii=False),
                file_name=f"clinical_history_{visit_id}.json",
                mime="application/json",
                use_container_width=True
            )
        with b2:
            if st.button("⬅ Return to Patient Dashboard", use_container_width=True):
                st.session_state.current_screen = "dashboard"
                st.rerun()
