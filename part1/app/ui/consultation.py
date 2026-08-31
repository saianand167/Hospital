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

# Multilingual UI labels
UI_STRINGS = {
    "en": {
        "listen_btn": "🔊 Listen",
        "speak_answer": "🎤 Speak Your Answer (Voice AI):",
        "touch_option": "👆 Touch an Option:",
        "pain_scale": "🔢 Select Severity / Pain Rating (0 to 10):",
        "answer_box": "⌨ Answer Box (Voice Transcript / Typed Response):",
        "submit_btn": "Submit Answer ➔",
        "clear_btn": "Clear",
        "recognized": "🎙️ Recognized Voice:",
        "confirm_note": "Click Submit Answer to proceed or edit below.",
        "completed": "✅ Clinical History Intake Completed.",
        "summary": "📋 Final Structured Intake Summary",
        "transcribing": "🎙️ Transcribing voice in real-time...",
        "speaking": "🔊 Generating voice...",
        "lang_name": "English"
    },
    "te": {
        "listen_btn": "🔊 ప్రశ్న వినండి",
        "speak_answer": "🎤 మీ సమాధానం మాట్లాడండి (Voice AI):",
        "touch_option": "👆 ఒక ఎంపికను తాకండి:",
        "pain_scale": "🔢 నొప్పి తీవ్రతను ఎంచుకోండి (0 నుండి 10):",
        "answer_box": "⌨ సమాధానం (వాయిస్ లేదా టైప్ చేయండి):",
        "submit_btn": "సమాధానం సమర్పించండి ➔",
        "clear_btn": "తుడిచివేయండి",
        "recognized": "🎙️ గుర్తించబడిన వాయిస్:",
        "confirm_note": "కొనసాగడానికి 'సమర్పించండి' క్లిక్ చేయండి లేదా కింద సవరించండి.",
        "completed": "✅ క్లినికల్ హిస్టరీ సేకరణ పూర్తయింది.",
        "summary": "📋 తుది రోగ నిర్ధారణ సారాంశం",
        "transcribing": "🎙️ మాటలను రికార్డ్ చేసి గుర్తిస్తోంది...",
        "speaking": "🔊 చదువుతోంది...",
        "lang_name": "తెలుగు"
    },
    "hi": {
        "listen_btn": "🔊 प्रश्न सुनें",
        "speak_answer": "🎤 अपना उत्तर बोलें (Voice AI):",
        "touch_option": "👆 एक विकल्प चुनें:",
        "pain_scale": "🔢 दर्द की तीव्रता चुनें (0 से 10):",
        "answer_box": "⌨ उत्तर (आवाज या टाइप किया गया):",
        "submit_btn": "उत्तर सबमिट करें ➔",
        "clear_btn": "हटाएं",
        "recognized": "🎙️ पहचानी गई आवाज़:",
        "confirm_note": "आगे बढ़ने के लिए 'सबमिट करें' पर क्लिक करें या नीचे संपादित करें।",
        "completed": "✅ नैदानिक इतिहास पूरा हो गया।",
        "summary": "📋 अंतिम सारांश",
        "transcribing": "🎙️ आवाज़ पहचानी जा रही है...",
        "speaking": "🔊 प्रश्न बोला जा रहा है...",
        "lang_name": "हिन्दी"
    },
    "or": {
        "listen_btn": "🔊 ପ୍ରଶ୍ନ ଶୁଣନ୍ତୁ",
        "speak_answer": "🎤 ଆପଣଙ୍କ ଉତ୍ତର କୁହନ୍ତୁ (Voice AI):",
        "touch_option": "👆 ଏକ ବିକଳ୍ପ ଚୟନ କରନ୍ତୁ:",
        "pain_scale": "🔢 ଯନ୍ତ୍ରଣା ତୀବ୍ରତା ବାଛନ୍ତୁ (0 ରୁ 10):",
        "answer_box": "⌨ ଉତ୍ତର ବାକ୍ସ (ଭଏସ୍ କିମ୍ବା ଟାଇପ୍):",
        "submit_btn": "ଉତ୍ତର ଦାଖଲ କରନ୍ତୁ ➔",
        "clear_btn": "ସଫା କରନ୍ତୁ",
        "recognized": "🎙️ ଚିହ୍ନଟ ହୋଇଥିବା ସ୍ୱର:",
        "confirm_note": "ଆଗକୁ ବଢ଼ିବା ପାଇଁ 'ଉତ୍ତର ଦାଖଲ କରନ୍ତୁ' କ୍ଲିକ୍ କରନ୍ତୁ କିମ୍ବା ସମ୍ପାଦନ କରନ୍ତୁ।",
        "completed": "✅ କ୍ଲିନିକାଲ୍ ଇନଟେକ୍ ସମ୍ପୂର୍ଣ୍ଣ ହେଲା।",
        "summary": "📋 ଚୂଡ଼ାନ୍ତ ଇନଟେକ୍ ସାରାଂଶ",
        "transcribing": "🎙️ ସ୍ୱର ରେକର୍ଡ ହେଉଛି...",
        "speaking": "🔊 ପଢ଼ାଯାଉଛି...",
        "lang_name": "ଓଡ଼ିଆ"
    }
}

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

    cur_lang = history.language if history.language in ["en", "te", "hi"] else "en"
    ui = UI_STRINGS.get(cur_lang, UI_STRINGS["en"])

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
        langs = [("en", "🇬🇧 English"), ("te", "🇮🇳 తెలుగు (Telugu)"), ("hi", "🇮🇳 हिन्दी (Hindi)")]
        current_lang_idx = 0
        for idx, (code, _) in enumerate(langs):
            if code == history.language:
                current_lang_idx = idx
                break
        
        selected_lang_tuple = st.selectbox(
            "Change Language / భాష",
            langs,
            index=current_lang_idx,
            format_func=lambda x: x[1],
            key="lang_switcher_consult",
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
        st.markdown("#### 💬 Conversation History")
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
        st.caption(f"📋 Question **{curr} of {total}** • Section: **{next_prompt.section.upper()}** • Language: **{ui['lang_name']}**")

        # Active Question Card with Auto-Voice Narration
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 100%); border: 2px solid #0d9488; border-radius: 20px; padding: 22px; margin-bottom: 14px; box-shadow: 0 10px 20px -5px rgba(13, 148, 136, 0.12);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="color: #0d9488; font-weight: 800; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px;">
                        🗣️ AI Doctor Question / ప్రశ్న
                    </span>
                    <span style="background: rgba(13, 148, 136, 0.12); color: #0d9488; font-weight: 700; font-size: 0.75rem; padding: 2px 10px; border-radius: 9999px;">
                        🔊 Voice Active
                    </span>
                </div>
                <h2 style="margin: 0; color: #0f172a; font-size: 1.5rem; font-weight: 800; line-height: 1.4;">
                    {next_prompt.prompt_text}
                </h2>
            </div>
        """, unsafe_allow_html=True)

        # Automatic Question Voice Synthesis & Audio Playback
        tts_cache_key = f"tts_audio_{curr}_{cur_lang}_{hashlib.md5(next_prompt.prompt_text.encode()).hexdigest()}"
        if tts_cache_key not in st.session_state:
            with st.spinner(f"{ui['speaking']}"):
                try:
                    q_audio_bytes = asyncio.run(TextToSpeechProvider.synthesize(next_prompt.prompt_text, language=history.language))
                    st.session_state[tts_cache_key] = q_audio_bytes
                except Exception as e:
                    logger.warning(f"Auto TTS generation notice: {e}")
                    st.session_state[tts_cache_key] = None

        cached_audio = st.session_state.get(tts_cache_key)

        col_audio_play, col_audio_replay = st.columns([3, 1])
        with col_audio_play:
            if cached_audio:
                # Auto-play audio so the patient hears the kiosk asking the question out loud
                st.audio(cached_audio, format="audio/mp3", autoplay=True)
        with col_audio_replay:
            if st.button(f"{ui['listen_btn']}", key=f"btn_replay_tts_{curr}_{cur_lang}", use_container_width=True, help="Listen to the question again"):
                if cached_audio:
                    st.audio(cached_audio, format="audio/mp3", autoplay=True)

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
            st.markdown(f"##### {ui['touch_option']}")
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
            st.markdown(f"##### {ui['pain_scale']}")
            scale_val = st.slider("Severity Scale", 0, 10, 5, step=1, key="scale_slider")
            if st.button("Confirm Rating ➔", key="btn_submit_scale", use_container_width=True):
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

        # 3. Live Microphone Recording Input (Unified IndicVoice Engine)
        st.markdown(f"##### {ui['speak_answer']}")
        try:
            audio_data = st.audio_input("Record speech with microphone", key=f"mic_{curr}", label_visibility="collapsed")
            if audio_data is not None:
                audio_bytes = audio_data.read()
                if audio_bytes and len(audio_bytes) > 50:
                    curr_hash = hashlib.md5(audio_bytes).hexdigest()
                    if st.session_state.get(audio_hash_key) != curr_hash:
                        with st.spinner(ui["transcribing"]):
                            res_meta = asyncio.run(
                                HistoryService._asr_provider.transcribe_with_meta(
                                    audio_bytes,
                                    language=history.language
                                )
                            )
                        transcribed_text = res_meta.get("text", "")
                        if transcribed_text:
                            st.session_state[input_key] = transcribed_text
                            st.session_state[audio_hash_key] = curr_hash
                            st.session_state[f"asr_meta_{curr}"] = res_meta
                            st.rerun()
        except AttributeError:
            st.info("Browser microphone active.")

        # 4. Answer Input Box (Voice Transcript or Typed)
        st.markdown(f"##### {ui['answer_box']}")
        
        # Display badge if recognized from voice
        if st.session_state.get(input_key):
            meta = st.session_state.get(f"asr_meta_{curr}", {})
            latency = meta.get("latency_sec", 0.0)
            engine_name = meta.get("engine", "Swecha Gonthuka ASR (Telugu)" if history.language == "te" else "Unified Voice AI")
            lang_label = "తెలుగు" if history.language == "te" else ("हिन्दी" if history.language == "hi" else "English")
            st.success(f"🎙️ **\"{st.session_state[input_key]}\"**  \n*(⚡ {engine_name} [{lang_label}] • `{latency}s`)*")

        with st.form(key=f"text_form_{curr}", clear_on_submit=False):
            user_text = st.text_input(
                "Your Answer",
                value=st.session_state.get(input_key, ""),
                placeholder="...",
                label_visibility="collapsed"
            )
            
            c_sub, c_clr = st.columns([3, 1])
            with c_sub:
                submit_btn = st.form_submit_button(ui["submit_btn"], use_container_width=True, type="primary")
            with c_clr:
                clear_btn = st.form_submit_button(ui["clear_btn"], use_container_width=True)

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
        st.success(ui["completed"])
        
        hpi = history.hpi
        cc = history.chief_complaint

        st.markdown(f"### {ui['summary']}")
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
