"""
SIH26047 — MediKiosk Unified Web and Kiosk Application
Multi-role: Patient Intake, Document OCR, Doctor Panel, Pharmacist Verification & Staff Queue
"""

import sys
import os
import re
import traceback
from pathlib import Path
import streamlit as st
import requests
import pandas as pd

# ── 1. Page Configuration & Error Boundary ───────────────────────────────────
st.set_page_config(
    page_title="MediKiosk — Patient Case-Taking (SIH26047)",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_BASE = os.getenv("BACKEND_API_BASE", "http://localhost:8000/api/v1")

# ── 2. Helper API Functions with Full Error Capture ──────────────────────────
def get_headers():
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}

def api_login(username, password):
    try:
        res = requests.post(
            f"{API_BASE}/auth/login",
            json={"username": username.strip(), "password": password.strip()},
            timeout=10
        )
        if res.status_code == 200:
            return res.json(), None
        data = res.json() if res.content else {}
        return None, data.get("detail", f"Login failed (HTTP {res.status_code})")
    except Exception as e:
        return None, f"Could not connect to backend server at {API_BASE}: {str(e)}"

def api_get(endpoint, params=None, timeout=30):
    try:
        res = requests.get(
            f"{API_BASE}{endpoint}",
            headers=get_headers(),
            params=params,
            timeout=timeout
        )
        if res.status_code == 200:
            return res.json(), None
        data = res.json() if res.content else {}
        return None, data.get("detail", f"Error {res.status_code}")
    except Exception as e:
        return None, f"Connection error on GET {endpoint}: {str(e)}"

def api_get_bytes(endpoint):
    try:
        res = requests.get(f"{API_BASE}{endpoint}", headers=get_headers(), timeout=15)
        if res.status_code == 200:
            return res.content, None
        return None, f"Error {res.status_code}"
    except Exception as e:
        return None, str(e)

def api_post(endpoint, json_data=None, files=None, timeout=None):
    try:
        # OCR document uploads need longer timeout (EasyOCR + Groq AI)
        default_timeout = 120 if files else 25
        _timeout = timeout or default_timeout
        if files:
            res = requests.post(f"{API_BASE}{endpoint}", headers=get_headers(), data=json_data, files=files, timeout=_timeout)
        else:
            res = requests.post(f"{API_BASE}{endpoint}", headers=get_headers(), json=json_data, timeout=_timeout)
        if res.status_code in [200, 201]:
            return res.json(), None
        data = res.json() if res.content else {}
        return None, data.get("detail", f"Request failed (HTTP {res.status_code})")
    except Exception as e:
        return None, f"Connection error on POST {endpoint}: {str(e)}"


# ── 2.1 Neural Multi-Lingual Text-to-Speech Engine (Telugu, Hindi, Odia, English) ──
VOICE_MAP = {
    "en": "en-IN-NeerjaNeural",
    "te": "te-IN-ShrutiNeural",     # High-clarity Telugu Neural Voice
    "hi": "hi-IN-SwaraNeural",      # High-clarity Hindi Neural Voice
    "or": "hi-IN-SwaraNeural",      # Hindi neural voice fallback for Odia
    "ta": "ta-IN-PallaviNeural",    # Tamil Neural Voice
    "mr": "mr-IN-AarohiNeural",     # Marathi Neural Voice
    "bn": "bn-IN-TanishaaNeural"    # Bengali Neural Voice
}

def get_neural_tts_audio_bytes(text: str, language: str = "en"):
    """
    Synthesizes natural Indian neural voice audio (Telugu, Hindi, English, etc.)
    using Microsoft Edge Neural TTS. Caches generated audio bytes in Streamlit session state.
    """
    if not text or not text.strip():
        return None
    cache_key = f"tts_bytes_{language}_{hash(text.strip())}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    
    voice = VOICE_MAP.get(language, VOICE_MAP["en"])
    try:
        import asyncio
        import concurrent.futures
        import edge_tts
        
        async def _synth():
            communicate = edge_tts.Communicate(text.strip(), voice=voice)
            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
            return bytes(audio_buffer)
        
        with concurrent.futures.ThreadPoolExecutor() as pool:
            audio_bytes = pool.submit(asyncio.run, _synth()).result(timeout=12)
            
        st.session_state[cache_key] = audio_bytes
        return audio_bytes
    except Exception:
        return None


# ── 3. Premium CSS Styling ───────────────────────────────────────────────────
def apply_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, .stApp {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background: linear-gradient(180deg, #0B1120 0%, #0F172A 100%) !important;
        color: #F8FAFC !important;
    }

    /* Cards */
    .med-card {
        background: rgba(30, 41, 59, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
        backdrop-filter: blur(12px) !important;
        margin-bottom: 16px !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3) !important;
    }

    .hero-banner {
        background: linear-gradient(135deg, rgba(14, 165, 233, 0.2) 0%, rgba(13, 148, 136, 0.15) 100%) !important;
        border: 1px solid rgba(14, 165, 233, 0.3) !important;
        border-radius: 18px !important;
        padding: 22px 26px !important;
        margin-bottom: 22px !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.2rem !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        background: #1E293B !important;
        color: #F8FAFC !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        border-color: #0EA5E9 !important;
        background: #0284C7 !important;
        color: #FFFFFF !important;
    }

    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #0D9488 0%, #0284C7 100%) !important;
        border: none !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: rgba(15, 23, 42, 0.8) !important;
        padding: 6px 8px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        margin-bottom: 20px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
        border: none !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(14, 165, 233, 0.25) !important;
        color: #38BDF8 !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
    }

    /* Badges */
    .badge-normal {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 3px 10px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-red {
        background-color: rgba(239, 68, 68, 0.2);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 3px 10px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ── 4. Main App Controller ───────────────────────────────────────────────────
def main():
    apply_theme()

    # Session State
    if "token" not in st.session_state:
        st.session_state["token"] = None
    if "role" not in st.session_state:
        st.session_state["role"] = None
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = {}

    # Sidebar Navigation & Login
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/hospital-2.png", width=56)
        st.title("MediKiosk")
        st.caption("AI-Powered Clinical History, Document OCR & Outpatient Management (SIH26047)")
        st.divider()

        if not st.session_state["token"]:
            st.subheader("🔑 Demo Accounts")
            quick_role = st.selectbox(
                "Quick Login As:",
                ["Patient (patient1)", "Doctor (doctor1)", "Pharmacist (pharm1)", "Staff (staff1)"]
            )
            if quick_role.startswith("Doctor"):
                def_u, def_p = "doctor1", "doctor123"
            elif quick_role.startswith("Patient"):
                def_u, def_p = "patient1", "patient123"
            elif quick_role.startswith("Pharmacist"):
                def_u, def_p = "pharm1", "pharm123"
            else:
                def_u, def_p = "staff1", "staff123"

            u_sb = st.text_input("Username:", value=def_u, key="sb_u")
            p_sb = st.text_input("Password:", value=def_p, type="password", key="sb_p")

            if st.button("🚀 Sign In", use_container_width=True, key="btn_sb_login"):
                res, err = api_login(u_sb, p_sb)
                if res:
                    st.session_state["token"] = res["access_token"]
                    st.session_state["role"] = res["role"]
                    st.session_state["username"] = res["username"]
                    st.session_state["user_data"] = res
                    st.success(f"Logged in as {res['role']}!")
                    st.rerun()
                else:
                    st.error(f"❌ {err}")
        else:
            u_data = st.session_state.get("user_data", {})
            full_n = u_data.get("full_name") or st.session_state["username"]
            st.markdown(f"👤 **User:** `{full_n}`")
            st.markdown(f"🛡️ **Role:** `{st.session_state['role']}`")
            if u_data.get("patient_id"):
                st.markdown(f"🆔 **Patient ID:** `{u_data['patient_id']}`")

            # Quick Role Switcher for Demo
            role_map = {"PATIENT": ("patient1", "patient123"), "DOCTOR": ("doctor1", "doctor123"), "PHARMACIST": ("pharm1", "pharm123"), "STAFF": ("staff1", "staff123")}
            cur_role = st.session_state.get("role", "PATIENT")
            cur_idx = ["PATIENT", "DOCTOR", "PHARMACIST", "STAFF"].index(cur_role) if cur_role in ["PATIENT", "DOCTOR", "PHARMACIST", "STAFF"] else 0

            new_role = st.selectbox("Switch Role View:", ["PATIENT", "DOCTOR", "PHARMACIST", "STAFF"], index=cur_idx, key="sb_role_switch")
            if new_role != cur_role:
                demo_u, demo_p = role_map[new_role]
                res, _ = api_login(demo_u, demo_p)
                if res:
                    st.session_state["token"] = res["access_token"]
                    st.session_state["role"] = res["role"]
                    st.session_state["username"] = res["username"]
                    st.session_state["user_data"] = res
                    st.rerun()

            st.divider()
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state["token"] = None
                st.session_state["role"] = None
                st.session_state["username"] = None
                st.session_state["user_data"] = {}
                st.rerun()

    # Main Body
    if not st.session_state["token"]:
        render_auth_screen()
    else:
        role = st.session_state.get("role", "PATIENT")
        if role == "PATIENT":
            render_patient_portal()
        elif role == "DOCTOR":
            render_doctor_portal()
        elif role == "PHARMACIST":
            render_pharmacist_portal()
        elif role == "STAFF":
            render_staff_portal()
        else:
            st.warning(f"Unknown role: {role}")


# ── 5. Authentication & Registration Screen ──────────────────────────────────
# ── 5. Supported Languages & UI Localization ─────────────────────────────────
SUPPORTED_LANGUAGES = [
    {"code": "en", "label": "🇬🇧 English", "native": "English", "bcp47": "en-IN"},
    {"code": "te", "label": "🇮🇳 తెలుగు", "native": "Telugu", "bcp47": "te-IN"},
    {"code": "or", "label": "🇮🇳 ଓଡ଼ିଆ", "native": "Odia", "bcp47": "or-IN"},
    {"code": "hi", "label": "🇮🇳 हिन्दी", "native": "Hindi", "bcp47": "hi-IN"}
]

PATIENT_UI_STRINGS = {
    "en": {
        "title": "Clinical History Intake",
        "subtitle": "Please answer the questions below to prepare your consultation for the doctor.",
        "pref_title": "Patient Consultation Preferences",
        "pref_sub": "Please choose your preferred interaction mode and language before beginning your health interview.",
        "sec_mode": "Section A — How would you like to answer?",
        "sec_mode_sub": "Select how you want to provide your responses:",
        "mode_voice": "Voice",
        "mode_voice_desc": "Speak your answers naturally using your microphone",
        "mode_text": "Text",
        "mode_text_desc": "Type answers or select choices using keyboard and touch screen",
        "sec_lang": "Section B — Which language are you comfortable with?",
        "sec_lang_sub": "Select your preferred consultation language:",
        "start_interview_btn": "Start Health Interview ➔",
        "ai_assistant": "AI Clinical Assistant",
        "listen_btn": "🔊 Listen to Question",
        "speak_voice": "VOICE INTERACTION",
        "voice_sub": "Tap microphone below to start speaking. Transcribed text appears live on screen.",
        "tap_to_speak": "🎙️ Tap to Speak",
        "stop_finish": "⏹️ Finish Speaking & Submit",
        "rec_idle": "Status: Ready (Click to Speak)",
        "rec_listening": "🟢 Listening Live... Speak your answer.",
        "rec_processing": "⚡ Understanding your response...",
        "rec_done": "✓ Speech recognized & submitted.",
        "touch_options": "🔘 Quick Touch Options:",
        "rate_scale": "📊 Rate Severity Scale (0 = None, 10 = Severe):",
        "quick_duration": "⏱️ Select Quick Duration:",
        "yes_no": "🔘 Choose Yes / No:",
        "type_box": "⌨️ Type Response (Alternative):",
        "submit_btn": "Submit Answer ➔",
        "clear_btn": "Clear",
        "intake_completed": "Clinical Intake Completed! Your structured case-taking report is ready for the doctor.",
        "change_prefs": "Change Mode / Language",
        "active_visit": "Active Visit",
        "question": "Question",
        "of": "of",
        "redo_intake": "Redo Intake",
        "start_new": "Start Another Consultation",
        "lang_name": "English",
        "dialogue_title": "Conversation Transcript",
        "fallback_expander": "⌨️ Touch Options & Keyboard Entry (Optional Fallback)"
    },
    "te": {
        "title": "క్లినికల్ హిస్టరీ సేకరణ",
        "subtitle": "డాక్టర్‌ను కలవడానికి ముందు దయచేసి క్రింది ప్రశ్నలకు సమాధానం ఇవ్వండి.",
        "pref_title": "రోగి ప్రాధాన్యతలు (Patient Preferences)",
        "pref_sub": "మీ ఆరోగ్య ఇంటర్వ్యూ ప్రారంభించడానికి ముందు సమాధాన విధానం మరియు భాషను ఎంచుకోండి.",
        "sec_mode": "విభాగం A — మీరు ఎలా సమాధానం చెప్పాలనుకుంటున్నారు?",
        "sec_mode_sub": "సమాధానం ఇవ్వడానికి ఒక విధానాన్ని ఎంచుకోండి:",
        "mode_voice": "వాయిస్ (Voice)",
        "mode_voice_desc": "మైక్రోఫోన్ ద్వారా మాట్లాడి సహజంగా సమాధానం చెప్పండి",
        "mode_text": "టెక్స్ట్ (Text)",
        "mode_text_desc": "కీబోర్డ్ లేదా స్క్రీన్ టచ్ ద్వారా సమాధానం ఇవ్వండి",
        "sec_lang": "విభాగం B — మీకు ఏ భాష సౌకర్యంగా ఉంది?",
        "sec_lang_sub": "మీ సంప్రదింపు భాషను ఎంచుకోండి:",
        "start_interview_btn": "ఆరోగ్య ఇంటర్వ్యూ ప్రారంభించండి ➔",
        "ai_assistant": "AI క్లినికల్ అసిస్టెంట్",
        "listen_btn": "🔊 ప్రశ్న వినండి",
        "speak_voice": "వాయిస్ ఇంటరాక్షన్ (Voice AI)",
        "voice_sub": "మాట్లాడటానికి క్రింది మైక్రోఫోన్‌ను తాకండి. మీ మాటలు స్క్రీన్‌పై ప్రత్యక్షంగా కనిపిస్తాయి.",
        "tap_to_speak": "🎙️ మాట్లాడటానికి తాకండి",
        "stop_finish": "⏹️ మాట్లాడటం పూర్తయింది (సమర్పించండి)",
        "rec_idle": "స్థితి: సిద్ధంగా ఉంది (మాట్లాడటానికి క్లిక్ చేయండి)",
        "rec_listening": "🟢 మీ మాటలను వింటోంది... మాట్లాడండి.",
        "rec_processing": "⚡ మీ సమాధానాన్ని పరిశీలిస్తోంది...",
        "rec_done": "✓ వాయిస్ గుర్తించబడింది!",
        "touch_options": "🔘 ఒక ఎంపికను తాకండి:",
        "rate_scale": "📊 తీవ్రతను ఎంచుకోండి (0 = అసలు లేదు, 10 = తీవ్రం):",
        "quick_duration": "⏱️ వ్యవధిని ఎంచుకోండి:",
        "yes_no": "🔘 అవును / కాదు ఎంచుకోండి:",
        "type_box": "⌨️ సమాధానం టైప్ చేయండి:",
        "submit_btn": "సమాధానం సమర్పించండి ➔",
        "clear_btn": "తుడిచివేయండి",
        "intake_completed": "క్లినికల్ కేస్-టేకింగ్ పూర్తయింది! మీ వివరాలు డాక్టర్‌కు చేరాయి.",
        "change_prefs": "భాష / మోడ్ మార్చండి",
        "active_visit": "ప్రస్తుత విజిట్",
        "question": "ప్రశ్న",
        "of": "మొత్తంలో",
        "redo_intake": "మళ్లీ ప్రారంభించండి",
        "start_new": "మరొక సంప్రదింపు ప్రారంభించండి",
        "lang_name": "తెలుగు",
        "dialogue_title": "సంభాషణ వివరాలు (Transcript)",
        "fallback_expander": "⌨️ టచ్ ఆప్షన్లు & కీబోర్డ్ ఎంట్రీ (ఆప్షనల్)"
    },
    "or": {
        "title": "କ୍ଲିନିକାଲ୍ ହିଷ୍ଟ୍ରି ଇନଟେକ୍",
        "subtitle": "ଡାକ୍ତରଙ୍କୁ ଭେଟିବା ପୂର୍ବରୁ ଦୟାକରି ତଳେ ଥିବା ପ୍ରଶ୍ନଗୁଡ଼ିକର ଉତ୍ତର ଦିଅନ୍ତୁ।",
        "pref_title": "ରୋଗୀ ପସନ୍ଦ ସ୍କ୍ରିନ୍ (Patient Preferences)",
        "pref_sub": "ସ୍ୱାସ୍ଥ୍ୟ ସାକ୍ଷାତକାର ଆରମ୍ଭ କରିବା ପୂର୍ବରୁ ଆପଣଙ୍କ ପସନ୍ଦର ମୋଡ୍ ଏବଂ ଭାଷା ବାଛନ୍ତୁ।",
        "sec_mode": "ବିଭାଗ A — ଆପଣ କିପରି ଉତ୍ତର ଦେବାକୁ ଚାହାଁନ୍ତି?",
        "sec_mode_sub": "ଉତ୍ତର ଦେବା ପାଇଁ ଏକ ମାଧ୍ୟମ ଚୟନ କରନ୍ତୁ:",
        "mode_voice": "ଭଏସ୍ (Voice)",
        "mode_voice_desc": "ମାଇକ୍ରୋଫୋନ୍ ସାହାଯ୍ୟରେ କହି ସହଜରେ ଉତ୍ତର ଦିଅନ୍ତୁ",
        "mode_text": "ଟେକ୍ସଟ୍ (Text)",
        "mode_text_desc": "କୀବୋର୍ଡ୍ କିମ୍ବା ସ୍କ୍ରିନ୍ ଟଚ୍ ସାହାଯ୍ୟରେ ଟାଇପ୍ କରନ୍ତୁ",
        "sec_lang": "ବିଭାଗ B — ଆପଣ କେଉଁ ଭାଷାରେ ସହଜ ଅନୁଭବ କରନ୍ତି?",
        "sec_lang_sub": "ଆପଣଙ୍କ ପରାମର୍ଶ ଭାଷା ବାଛନ୍ତୁ:",
        "start_interview_btn": "ସ୍ୱାସ୍ଥ୍ୟ ସାକ୍ଷାତକାର ଆରମ୍ଭ କରନ୍ତୁ ➔",
        "ai_assistant": "AI କ୍ଲିନିକାଲ୍ ଆସିଷ୍ଟାଣ୍ଟ",
        "listen_btn": "🔊 ପ୍ରଶ୍ନ ଶୁଣନ୍ତୁ",
        "speak_voice": "ଭଏସ୍ ଇଣ୍ଟରାକ୍ସନ୍ (Voice AI)",
        "voice_sub": "କହିବା ପାଇଁ ତଳେ ଥିବା ମାଇକ୍ରୋଫୋନ୍ କ୍ଲିକ୍ କରନ୍ତୁ। ଆପଣଙ୍କ ସ୍ୱର ସିଧାସଳଖ ରେକର୍ଡ ହେବ।",
        "tap_to_speak": "🎙️ କହିବା ପାଇଁ ଟ୍ୟାପ୍ କରନ୍ତୁ",
        "stop_finish": "⏹️ କହିବା ସମାପ୍ତ (ଦାଖଲ କରନ୍ତୁ)",
        "rec_idle": "ସ୍ଥିତି: ପ୍ରସ୍ତୁତ ('ଟ୍ୟାପ୍' କରନ୍ତୁ)",
        "rec_listening": "🟢 ଆପଣଙ୍କ ସ୍ୱର ଶୁଣାଯାଉଛି...",
        "rec_processing": "⚡ ଆପଣଙ୍କ ଉତ୍ତର ବିଶ୍ଳେଷଣ ହେଉଛି...",
        "rec_done": "✓ ସ୍ୱର ସଫଳତାର ସହ ଗୃହୀତ ହେଲା!",
        "touch_options": "🔘 ଏକ ବିକଳ୍ପ ଚୟନ କରନ୍ତୁ:",
        "rate_scale": "📊 ତୀବ୍ରତା ମାପ (0 = ଶୂନ, 10 = ଅତ୍ୟଧିକ):",
        "quick_duration": "⏱️ ଦିନ ବାଛନ୍ତୁ:",
        "yes_no": "🔘 ହଁ / ନା ବାଛନ୍ତୁ:",
        "type_box": "⌨️ ଆପଣଙ୍କ ଉତ୍ତର ଟାଇପ୍ କରନ୍ତୁ:",
        "submit_btn": "ଉତ୍ତର ଦାଖଲ କରନ୍ତୁ ➔",
        "clear_btn": "ସଫା କରନ୍ତୁ",
        "intake_completed": "କ୍ଲିନିକାଲ୍ ଇନଟେକ୍ ସମ୍ପୂର୍ଣ୍ଣ ହେଲା! ଆପଣଙ୍କ ରିପୋର୍ଟ ଡାକ୍ତରଙ୍କ ପାଇଁ ପ୍ରସ୍ତୁତ।",
        "change_prefs": "ଭାଷା / ମୋଡ୍ ବଦଳାନ୍ତୁ",
        "active_visit": "ସକ୍ରିୟ ଭିଜିଟ୍",
        "question": "ପ୍ରଶ୍ନ",
        "of": "ରୁ",
        "redo_intake": "ପୁନର୍ବାର କରନ୍ତୁ",
        "start_new": "ଅନ୍ୟ ଏକ ପରାମର୍ଶ ଆରମ୍ଭ କରନ୍ତୁ",
        "lang_name": "ଓଡ଼ିଆ",
        "dialogue_title": "ସାକ୍ଷାତକାର ଟ୍ରାନ୍ସକ୍ରିପ୍ଟ (Transcript)",
        "fallback_expander": "⌨️ ଟଚ୍ ବିକଳ୍ପ ଏବଂ କୀବୋର୍ଡ୍ ଏଣ୍ଟ୍ରି (ବିକଳ୍ପ)"
    },
    "hi": {
        "title": "क्लिनिकल इतिहास संग्रह",
        "subtitle": "डॉक्टर से परामर्श से पहले कृपया नीचे दिए गए प्रश्नों के उत्तर दें।",
        "pref_title": "मरीज़ की प्राथमिकताएं (Patient Preferences)",
        "pref_sub": "स्वास्थ्य साक्षात्कार शुरू करने से पहले अपनी पसंद का माध्यम और भाषा चुनें।",
        "sec_mode": "खंड A — आप किस प्रकार उत्तर देना चाहते हैं?",
        "sec_mode_sub": "उत्तर देने के लिए एक माध्यम चुनें:",
        "mode_voice": "आवाज़ (Voice)",
        "mode_voice_desc": "माइक्रोफ़ोन में बोलकर स्वाभाविक रूप से उत्तर दें",
        "mode_text": "टेक्स्ट (Text)",
        "mode_text_desc": "कीबोर्ड या टच स्क्रीन द्वारा टाइप करके उत्तर दें",
        "sec_lang": "खंड B — आप किस भाषा में सहज महसूस करते हैं?",
        "sec_lang_sub": "परामर्श की भाषा चुनें:",
        "start_interview_btn": "स्वास्थ्य साक्षात्कार शुरू करें ➔",
        "ai_assistant": "AI क्लिनिकल सहायक",
        "listen_btn": "🔊 प्रश्न सुनें",
        "speak_voice": "ध्वनि संपर्क (Voice AI)",
        "voice_sub": "बोलने के लिए नीचे माइक्रोफ़ोन छुएं। आपकी आवाज़ तुरंत स्क्रीन पर दर्ज होगी।",
        "tap_to_speak": "🎙️ बोलने के लिए छुएं",
        "stop_finish": "⏹️ बोलना समाप्त (सबमिट करें)",
        "rec_idle": "स्थिति: तैयार (बोलने के लिए क्लिक करें)",
        "rec_listening": "🟢 आपकी आवाज़ सुनी जा रही है...",
        "rec_processing": "⚡ आपके उत्तर का विश्लेषण हो रहा है...",
        "rec_done": "✓ आवाज़ सफलतापूर्वक दर्ज हुई!",
        "touch_options": "🔘 एक विकल्प चुनें:",
        "rate_scale": "📊 तीव्रता दर चुनें (0 = शून्य, 10 = अत्यधिक):",
        "quick_duration": "⏱️ अवधि चुनें:",
        "yes_no": "🔘 हाँ / नहीं चुनें:",
        "type_box": "⌨️ अपना उत्तर टाइप करें:",
        "submit_btn": "उत्तर सबमिट करें ➔",
        "clear_btn": "हटाएं",
        "intake_completed": "नैदानिक इतिहास पूरा हुआ! आपकी रिपोर्ट डॉक्टर के लिए तैयार है।",
        "change_prefs": "भाषा / मोड बदलें",
        "active_visit": "सक्रिय विज़िट",
        "question": "प्रश्न",
        "of": "में से",
        "redo_intake": "फिर से शुरू करें",
        "start_new": "नया परामर्श शुरू करें",
        "lang_name": "हिन्दी",
        "dialogue_title": "संवाद प्रतिलेख (Transcript)",
        "fallback_expander": "⌨️ टच विकल्प और कीबोर्ड इनपुट (वैकल्पिक)"
    }
}


# ── 6. Page 1: Authentication & Registration Screen ──────────────────────────
def render_auth_screen():
    st.markdown("""
        <div style="text-align:center; padding: 24px 0 16px 0;">
            <div style="font-size: 3.2rem;">🏥</div>
            <h1 style="color:#0EA5E9; margin:0; font-size:2.4rem; font-weight:800;">MediKiosk</h1>
            <p style="color:#94A3B8; font-size:1.05rem; margin-top:4px;">
                Intelligent Outpatient Case-Taking & Clinical Intake Platform (SIH26047)
            </p>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_reg = st.tabs(["🔑 Sign In", "📝 Register New Patient"])

    with tab_login:
        st.markdown("### Sign In to Your Account")
        with st.form("main_login_form"):
            col1, col2 = st.columns(2)
            with col1:
                u_in = st.text_input("Patient ID or Username", placeholder="e.g. PAT-000001, patient1, or doctor1")
            with col2:
                p_in = st.text_input("Password", type="password", placeholder="••••••••")
            
            sub = st.form_submit_button("Sign In ➔", use_container_width=True)
            if sub:
                if not u_in or not p_in:
                    st.error("Please enter both Patient ID / Username and Password.")
                else:
                    res, err = api_login(u_in, p_in)
                    if res:
                        st.session_state["token"] = res["access_token"]
                        st.session_state["role"] = res["role"]
                        st.session_state["username"] = res["username"]
                        st.session_state["user_data"] = res
                        if res.get("role") == "PATIENT":
                            st.session_state["patient_stage"] = "preferences"
                        st.success("Signed in successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")

    with tab_reg:
        st.markdown("### 📝 Register New Patient Account")
        st.caption("A unique sequential Patient ID (`PAT-XXXXXX`) will be generated automatically.")
        with st.form("patient_reg_form"):
            c_name, c_user = st.columns(2)
            with c_name:
                reg_name = st.text_input("Full Name *", placeholder="e.g. Sai Anand")
            with c_user:
                reg_user = st.text_input("Choose Username *", placeholder="e.g. saianand")

            c_pwd, c_email = st.columns(2)
            with c_pwd:
                reg_pwd = st.text_input("Password *", type="password", placeholder="••••••••")
            with c_email:
                reg_email = st.text_input("Email (Optional)", placeholder="e.g. sai@example.com")

            c_ph, c_gen, c_lang = st.columns(3)
            with c_ph:
                reg_ph = st.text_input("Phone Number", placeholder="e.g. 9876543210")
            with c_gen:
                reg_gen = st.selectbox("Gender", ["Male", "Female", "Other"])
            with c_lang:
                reg_lang = st.selectbox("Initial Language", ["English", "Telugu / తెలుగు", "Odia / ଓଡ଼ିଆ", "Hindi / हिन्दी"])

            sub_reg = st.form_submit_button("Create Patient Account ➔", use_container_width=True)
            if sub_reg:
                if not reg_name or not reg_user or not reg_pwd:
                    st.error("Full Name, Username, and Password are required.")
                else:
                    mapped_lang = "te" if "Telugu" in reg_lang else ("or" if "Odia" in reg_lang else ("hi" if "Hindi" in reg_lang else "en"))
                    payload = {
                        "full_name": reg_name.strip(),
                        "username": reg_user.strip(),
                        "password": reg_pwd.strip(),
                        "email": reg_email.strip() if reg_email else None,
                        "phone": reg_ph.strip() if reg_ph else None,
                        "gender": reg_gen,
                        "preferred_language": reg_lang
                    }
                    res, err = api_post("/patients/register", json_data=payload)
                    if res:
                        st.session_state["token"] = res["access_token"]
                        st.session_state["role"] = res["role"]
                        st.session_state["username"] = res["username"]
                        st.session_state["user_data"] = res
                        st.session_state["patient_stage"] = "preferences"
                        st.session_state["pref_lang"] = mapped_lang
                        st.session_state["pref_mode"] = "voice"
                        st.success(f"🎉 Registered successfully! Assigned Patient ID: **{res['patient_id']}**")
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")


# ── 7. Page 2: Patient Preference Screen ─────────────────────────────────────
def render_patient_preference_screen(patient_id, full_name):
    """
    PAGE 2 — Dedicated Patient Preference Screen
    Designed with high accessibility for elderly and low-digital-literacy users.
    Allows explicit selection of Interaction Mode (Voice / Text) and Language.
    Zero microphone access on hover or page load.
    """
    if "pref_mode" not in st.session_state or st.session_state["pref_mode"] not in ["voice", "text"]:
        st.session_state["pref_mode"] = "voice"
    if "pref_lang" not in st.session_state or st.session_state["pref_lang"] not in ["en", "te", "or", "hi"]:
        st.session_state["pref_lang"] = "en"

    cur_mode = st.session_state["pref_mode"]
    cur_lang = st.session_state["pref_lang"]
    ui = PATIENT_UI_STRINGS.get(cur_lang, PATIENT_UI_STRINGS["en"])

    # ── SECTION A: Interaction Mode ──
    st.markdown(f"""
    <div style="margin-bottom: 8px;">
        <h3 style="color: #38BDF8; font-size: 1.25rem; font-weight: 800; margin: 0 0 4px 0;">
            {ui['sec_mode']}
        </h3>
        <p style="color: #94A3B8; font-size: 0.9rem; margin: 0 0 12px 0;">
            {ui['sec_mode_sub']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_voice, col_text = st.columns(2)
    with col_voice:
        is_v = cur_mode == "voice"
        card_cls = "border: 2px solid #38BDF8; background: rgba(14, 165, 233, 0.18); box-shadow: 0 0 20px rgba(14, 165, 233, 0.25);" if is_v else "border: 2px solid rgba(255,255,255,0.1); background: rgba(30, 41, 59, 0.5);"
        st.markdown(f"""
        <div style="{card_cls} border-radius: 16px; padding: 22px; text-align: center; margin-bottom: 10px;">
            <div style="font-size: 2.8rem; margin-bottom: 6px;">🎤</div>
            <div style="font-size: 1.35rem; font-weight: 800; color: {'#38BDF8' if is_v else '#FFFFFF'};">
                {ui['mode_voice']} {'✓' if is_v else ''}
            </div>
            <p style="color: #94A3B8; font-size: 0.95rem; margin: 6px 0 0 0;">
                {ui['mode_voice_desc']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Select 🎤 Voice Mode" if not is_v else "✓ 🎤 Voice Mode Selected", key="btn_mode_voice", use_container_width=True):
            st.session_state["pref_mode"] = "voice"
            st.rerun()

    with col_text:
        is_t = cur_mode == "text"
        card_cls = "border: 2px solid #38BDF8; background: rgba(14, 165, 233, 0.18); box-shadow: 0 0 20px rgba(14, 165, 233, 0.25);" if is_t else "border: 2px solid rgba(255,255,255,0.1); background: rgba(30, 41, 59, 0.5);"
        st.markdown(f"""
        <div style="{card_cls} border-radius: 16px; padding: 22px; text-align: center; margin-bottom: 10px;">
            <div style="font-size: 2.8rem; margin-bottom: 6px;">⌨️</div>
            <div style="font-size: 1.35rem; font-weight: 800; color: {'#38BDF8' if is_t else '#FFFFFF'};">
                {ui['mode_text']} {'✓' if is_t else ''}
            </div>
            <p style="color: #94A3B8; font-size: 0.95rem; margin: 6px 0 0 0;">
                {ui['mode_text_desc']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Select ⌨️ Text Mode" if not is_t else "✓ ⌨️ Text Mode Selected", key="btn_mode_text", use_container_width=True):
            st.session_state["pref_mode"] = "text"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION B: Preferred Language ──
    st.markdown(f"""
    <div style="margin-bottom: 8px;">
        <h3 style="color: #38BDF8; font-size: 1.25rem; font-weight: 800; margin: 0 0 4px 0;">
            {ui['sec_lang']}
        </h3>
        <p style="color: #94A3B8; font-size: 0.9rem; margin: 0 0 12px 0;">
            {ui['sec_lang_sub']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    cols_l = st.columns(4)
    for idx, lang_opt in enumerate(SUPPORTED_LANGUAGES):
        l_code = lang_opt["code"]
        is_sel = cur_lang == l_code
        with cols_l[idx]:
            l_border = "border: 2px solid #38BDF8; background: rgba(14, 165, 233, 0.2);" if is_sel else "border: 1px solid rgba(255,255,255,0.1); background: rgba(30, 41, 59, 0.5);"
            st.markdown(f"""
            <div style="{l_border} border-radius: 14px; padding: 16px 12px; text-align: center; margin-bottom: 8px;">
                <div style="font-size: 1.5rem; margin-bottom: 4px;">{'✓' if is_sel else '🌐'}</div>
                <div style="font-size: 1.15rem; font-weight: 800; color: {'#38BDF8' if is_sel else '#FFFFFF'};">
                    {lang_opt['label']}
                </div>
                <div style="font-size: 0.8rem; color: #94A3B8; margin-top: 2px;">
                    {lang_opt['native']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Choose {lang_opt['native']}" if not is_sel else f"✓ Selected", key=f"btn_lang_{l_code}", use_container_width=True):
                st.session_state["pref_lang"] = l_code
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── CONTINUE BUTTON ──
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 20px; text-align: center;">
    """, unsafe_allow_html=True)

    if st.button(f"🚀 {ui['start_interview_btn']}", key="btn_start_health_interview", use_container_width=True, type="primary"):
        # Check active visit or create new one
        visits, _ = api_get(f"/patients/{patient_id}/visits")
        active_v = visits[0] if visits and visits[0].get("status") != "COMPLETED" else None
        
        if not active_v:
            vid = _start_visit_intake(patient_id, department="General Medicine", complaint=None, language=st.session_state["pref_lang"])
        else:
            vid = active_v["visit_id"]
            # Start or ensure session exists with selected language
            res, _ = api_post("/history/session/start", json_data={
                "patient_id": patient_id,
                "visit_id": vid,
                "language": st.session_state["pref_lang"],
                "initial_complaint": None
            })
            if res:
                st.session_state[f"session_data_{vid}"] = res

        st.session_state["patient_stage"] = "interview"
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ── 8. Page 3: Clinical History Interview (Conversational Voice & Text Experience) ──
def render_patient_interview(patient_id, full_name):
    """
    PAGE 3 — Conversational Clinical History Interview
    Delivers a clean, single-turn conversational assistant experience.
    Features:
      • Current AI Question displayed clearly as text + Web Speech/TTS Bot audio
      • Central Voice Visual Status Indicator (Ready / Listening / Processing / Speaking / Next)
      • Single explicit Click-to-Speak microphone control
      • Real-time interim live speech transcript
      • Turn-by-turn conversational dialogue transcript
      • Rule-based deterministic red-flag triage alert
      • Multimodal fallback (keyboard & touch chips) in collapsible drawer
    """
    cur_mode = st.session_state.get("pref_mode", "voice")
    cur_lang = st.session_state.get("pref_lang", "en")
    ui = PATIENT_UI_STRINGS.get(cur_lang, PATIENT_UI_STRINGS["en"])

    visits, _ = api_get(f"/patients/{patient_id}/visits")
    active_v = visits[0] if visits and visits[0].get("status") != "COMPLETED" else None

    if not active_v:
        # Create a new visit if none active
        vid = _start_visit_intake(patient_id, department="General Medicine", complaint=None, language=cur_lang)
        if vid:
            visits, _ = api_get(f"/patients/{patient_id}/visits")
            active_v = visits[0] if visits else None

    if not active_v:
        st.warning("Could not initialize a consultation visit. Please retry.")
        if st.button("⬅ Return to Preferences"):
            st.session_state["patient_stage"] = "preferences"
            st.rerun()
        return

    vid = active_v["visit_id"]
    s_key = f"session_data_{vid}"
    dlg_key = f"voice_dlg_{vid}"

    if s_key not in st.session_state:
        res, _ = api_post("/history/session/start", json_data={
            "patient_id": patient_id,
            "visit_id": vid,
            "language": cur_lang,
            "initial_complaint": None
        })
        if res:
            st.session_state[s_key] = res

    if dlg_key not in st.session_state:
        st.session_state[dlg_key] = []

    sess = st.session_state.get(s_key, {})
    h_data = sess.get("history", {})
    next_q = sess.get("next_question")
    is_done = sess.get("is_completed", False)
    triage = h_data.get("triage", {})

    # Top Status & Preference Switcher Bar
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1:
        mode_icon = "🎤 Voice Assistant" if cur_mode == "voice" else "⌨️ Text & Touch"
        lang_label = ui.get("lang_name", "English")
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:14px;">
            <span style="font-weight:700; color:#38BDF8;">{ui['active_visit']}:</span>
            <code style="background:rgba(255,255,255,0.08); padding:2px 8px; border-radius:6px; font-weight:700;">{vid}</code>
            <span class="badge-normal">🌐 {lang_label} ({cur_lang})</span>
            <span class="badge-normal">{mode_icon}</span>
        </div>
        """, unsafe_allow_html=True)
    with top_c2:
        if st.button(f"⚙️ {ui['change_prefs']}", key="btn_switch_prefs", use_container_width=True):
            st.session_state["patient_stage"] = "preferences"
            st.rerun()

    # Deterministic Medical Safety / Red Flag Alert
    if triage.get("flag") == "RED":
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.18); border: 2px solid #EF4444; border-radius: 14px; padding: 16px 20px; margin-bottom: 18px;">
            <div style="display: flex; gap: 12px; align-items: center;">
                <span style="font-size: 2rem;">🚨</span>
                <div>
                    <h4 style="color: #F87171; margin: 0 0 4px 0; font-weight: 800;">PRIORITY CLINICAL ATTENTION ADVISORY</h4>
                    <p style="color: #FEE2E2; margin: 0; font-size: 0.95rem; line-height: 1.4;">
                        Your responses indicate symptoms that require immediate clinical evaluation. Hospital staff and nursing triage have been flagged. Please proceed to the nearest nurse station or emergency desk.
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── CASE 1: CONSULTATION INTAKE COMPLETED ──
    if is_done or not next_q:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(14, 165, 233, 0.15) 100%); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 18px; padding: 24px; text-align: center; margin-bottom: 20px;">
            <div style="font-size: 3.2rem; margin-bottom: 8px;">🎉</div>
            <h2 style="color: #34D399; margin: 0 0 6px 0; font-weight: 800;">{ui['intake_completed']}</h2>
            <p style="color: #94A3B8; margin: 0; font-size: 1rem;">
                Your case-taking session has been structured and securely transferred to the doctor's consultation panel.
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Summary Metrics
        hpi = h_data.get("hpi", {})
        cc = h_data.get("chief_complaint", {})
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Chief Complaint", (cc.get("text") or "General Outpatient").title())
        with c2:
            st.metric("Duration", f"{hpi.get('duration_days')} Days" if hpi.get('duration_days') is not None else "Reported")
        with c3:
            st.metric("Severity", f"{hpi.get('severity')}/10" if hpi.get('severity') is not None else "Recorded")
        with c4:
            flg = triage.get("flag", "GREEN")
            t_color = "#EF4444" if flg == "RED" else "#F59E0B" if flg == "YELLOW" else "#10B981"
            st.markdown(f"**Triage Flag**<br><span style='color:{t_color}; font-weight:800; font-size:1.3rem;'>● {flg}</span>", unsafe_allow_html=True)

        st.divider()

        # Transcript History View
        dlg = st.session_state.get(dlg_key, [])
        if dlg:
            with st.expander(f"💬 {ui['dialogue_title']} ({len(dlg)} turns)", expanded=False):
                for turn in dlg:
                    if turn.get("role") == "assistant":
                        st.markdown(f"**🤖 AI Assistant:** {turn.get('content')}")
                    else:
                        st.markdown(f"**🗣️ You:** *{turn.get('content')}*")

        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button(f"🔄 {ui['start_new']}", use_container_width=True, type="primary"):
                st.session_state["patient_stage"] = "preferences"
                st.rerun()
        with col_act2:
            if st.button(f"🔄 {ui['redo_intake']}", use_container_width=True):
                res, _ = api_post("/history/session/start", json_data={
                    "patient_id": patient_id,
                    "visit_id": vid,
                    "language": cur_lang,
                    "initial_complaint": None
                })
                if res:
                    st.session_state[s_key] = res
                    st.session_state[dlg_key] = []
                    st.rerun()

    # ── CASE 2: ACTIVE QUESTION TURN ──
    else:
        curr_n = next_q.get("progress_current", 1)
        tot_n = max(next_q.get("progress_total", 6), 1)
        prompt_text = next_q.get('prompt_text', '')
        f_name = next_q.get("field_name")
        i_type = next_q.get("input_type")
        options = next_q.get("options", [])
        lang_bcp = next((l["bcp47"] for l in SUPPORTED_LANGUAGES if l["code"] == cur_lang), "en-IN")

        # Sync Current Question into Dialogue History
        dlg = st.session_state.get(dlg_key, [])
        if not dlg or dlg[-1].get("content") != prompt_text:
            if not dlg or dlg[-1].get("role") != "assistant":
                st.session_state[dlg_key].append({"role": "assistant", "content": prompt_text, "q_num": curr_n})
                dlg = st.session_state[dlg_key]

        # Progress Bar
        st.progress(min(curr_n / tot_n, 1.0))
        # ── 1. PROMINENT CURRENT AI QUESTION CARD ──
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(14, 165, 233, 0.16) 0%, rgba(99, 102, 241, 0.1) 100%); border: 1.5px solid rgba(56, 189, 248, 0.35); border-radius: 18px; padding: 22px 24px; margin: 12px 0 14px 0; box-shadow: 0 10px 25px -5px rgba(14, 165, 233, 0.15);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                <span style="font-size: 0.85rem; font-weight: 800; color: #38BDF8; letter-spacing: 0.05em; text-transform: uppercase;">
                    🤖 {ui['ai_assistant']} • {ui['question']} {curr_n} {ui['of']} {tot_n}
                </span>
                <span class="badge-normal" style="font-size: 0.75rem;">🌐 {ui.get('lang_name')} ({cur_lang})</span>
            </div>
            <h2 style="margin: 4px 0 0 0; color: #FFFFFF; font-size: 1.45rem; font-weight: 700; line-height: 1.45;">
                {prompt_text}
            </h2>
        </div>
        """, unsafe_allow_html=True)

        # Multi-lingual Neural Audio Question Speaker (ONLY in Voice Mode)
        if cur_mode == "voice":
            q_audio_bytes = get_neural_tts_audio_bytes(prompt_text, language=cur_lang)
            col_q_audio, col_q_info = st.columns([2, 3])
            with col_q_audio:
                if q_audio_bytes:
                    st.audio(q_audio_bytes, format="audio/mp3", autoplay=False)
                else:
                    clean_prompt_tts = prompt_text.replace('"', '').replace("'", "").replace('\n', ' ')
                    st.components.v1.html(f"""
                    <button onclick="speakQ()" style="background: #0284C7; color: white; border: none; border-radius: 8px; padding: 6px 14px; font-weight: 700; cursor: pointer; font-size: 0.85rem;">
                        {ui['listen_btn']}
                    </button>
                    <script>
                    function speakQ() {{
                        if ('speechSynthesis' in window) {{
                            var msg = new SpeechSynthesisUtterance("{clean_prompt_tts}");
                            msg.lang = "{lang_bcp}";
                            window.speechSynthesis.speak(msg);
                        }}
                    }}
                    </script>
                    """, height=40)
            with col_q_info:
                st.caption(f"🔊 **{ui['listen_btn']}** — Neural AI Voice ({ui.get('lang_name', 'Telugu')})")

        # ── 2. CONVERSATIONAL TRANSCRIPT HISTORY AREA ──
        if len(dlg) > 1:
            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 14px 18px; max-height: 220px; overflow-y: auto; margin-bottom: 18px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.05em;">
                    💬 {ui['dialogue_title']}
                </div>
            """, unsafe_allow_html=True)
            
            # Show up to 4 recent dialogue turns
            for item in dlg[-4:-1]:
                if item.get("role") == "assistant":
                    st.markdown(f"""
                    <div style="display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px;">
                        <span style="background: #0284C7; border-radius: 50%; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; flex-shrink: 0;">🤖</span>
                        <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(14,165,233,0.25); border-radius: 10px; padding: 6px 12px; color: #E2E8F0; font-size: 0.88rem;">
                            {item.get('content')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="display: flex; gap: 8px; align-items: flex-start; justify-content: flex-end; margin-bottom: 8px;">
                        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16,185,129,0.35); border-radius: 10px; padding: 6px 12px; color: #F0FDF4; font-size: 0.88rem; text-align: right;">
                            {item.get('content')}
                        </div>
                        <span style="background: #059669; border-radius: 50%; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; flex-shrink: 0;">🗣️</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

        ans = None
        touch = None

        # ── 3. VOICE MODE: SINGLE UNIFIED GROQ WHISPER CONTROLLER ──
        if cur_mode == "voice":
            st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1.5px solid rgba(14, 165, 233, 0.3); border-radius: 16px; padding: 18px 22px; text-align: center; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                    <span class="badge-normal" style="font-size: 0.8rem;">
                        🟢 AI Voice Model • Groq Whisper Large V3 Turbo
                    </span>
                    <span style="font-size: 0.82rem; color: #94A3B8;">
                        Language: <b>{ui.get('lang_name')} ({cur_lang})</b>
                    </span>
                </div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #F8FAFC; margin-bottom: 4px;">
                    🎙️ {ui['tap_to_speak']}
                </div>
                <p style="color: #94A3B8; font-size: 0.88rem; margin: 0 0 12px 0;">
                    {ui['voice_sub']}
                </p>
            </div>
            """, unsafe_allow_html=True)

            try:
                from audio_recorder_streamlit import audio_recorder
                c_sp_left, c_mic_center, c_sp_right = st.columns([1, 2, 1])
                with c_mic_center:
                    rec_audio = audio_recorder(
                        text="Click to Speak / Click to Stop:",
                        recording_color="#EF4444",
                        neutral_color="#0284C7",
                        icon_size="3x",
                        key=f"voice_input_{f_name}_{curr_n}"
                    )
                if rec_audio:
                    with st.spinner("⚡ Transcribing audio via Groq Whisper Large V3 Turbo..."):
                        files = {"audio": ("response.wav", rec_audio, "audio/wav")}
                        res_asr, err_asr = api_post("/voice/transcribe", files=files, json_data={"model_quality": "fast", "language": cur_lang})
                        if res_asr and res_asr.get("transcript"):
                            transcribed_text = res_asr["transcript"].strip()
                            if transcribed_text:
                                st.markdown(f"""
                                <div style="background: rgba(16, 185, 129, 0.2); border: 1.5px solid #10B981; border-radius: 12px; padding: 12px 16px; margin: 12px 0;">
                                    <div style="font-size: 0.75rem; color: #34D399; font-weight: 700; text-transform: uppercase;">🗣️ Whisper Transcribed:</div>
                                    <div style="font-size: 1.05rem; color: #FFFFFF; font-weight: 700;">"{transcribed_text}"</div>
                                </div>
                                """, unsafe_allow_html=True)
                                ans = transcribed_text
                        else:
                            st.error(f"⚠️ Voice transcription error: {err_asr or 'Could not process audio'}")
            except Exception as e:
                st.warning(f"Voice recorder loading: {e}. Please use text fallback below.")

            # Collapsible text fallback in voice mode
            touch_ctx = st.expander(ui['fallback_expander'], expanded=False)
        else:
            # ── 3. TEXT & TOUCH MODE: CLEAN DEDICATED INPUT INTERFACE ──
            st.markdown(f"""
            <div style="background: rgba(14, 165, 233, 0.08); border: 1.5px solid rgba(14, 165, 233, 0.25); border-radius: 14px; padding: 14px 18px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <span class="badge-normal" style="font-size: 0.8rem;">
                        ⌨️ Text & Touch Intake Mode
                    </span>
                    <span style="font-size: 0.82rem; color: #94A3B8;">
                        Language: <b>{ui.get('lang_name')} ({cur_lang})</b>
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            touch_ctx = st.container()

        with touch_ctx:
            if options:
                st.markdown(f"##### {ui['touch_options']}")
                cols = st.columns(min(len(options), 3))
                for i, opt in enumerate(options):
                    with cols[i % 3]:
                        if st.button(f"🔘 {opt['label']}", key=f"opt_{f_name}_{opt['value']}", use_container_width=True):
                            ans, touch = opt["label"], opt["value"]

            elif i_type == "number" or "duration" in str(f_name):
                st.markdown(f"##### {ui['quick_duration']}")
                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    if st.button("1 Day", key=f"d1_{f_name}", use_container_width=True):
                        ans, touch = "1 day", "1"
                with c2:
                    if st.button("2 Days", key=f"d2_{f_name}", use_container_width=True):
                        ans, touch = "2 days", "2"
                with c3:
                    if st.button("3 Days", key=f"d3_{f_name}", use_container_width=True):
                        ans, touch = "3 days", "3"
                with c4:
                    if st.button("1 Week", key=f"d7_{f_name}", use_container_width=True):
                        ans, touch = "7 days", "7"
                with c5:
                    if st.button("2+ Weeks", key=f"d14_{f_name}", use_container_width=True):
                        ans, touch = "14 days", "14"

            elif i_type == "yes_no":
                st.markdown(f"##### {ui['yes_no']}")
                cy, cn = st.columns(2)
                with cy:
                    if st.button("✅ YES", key=f"y_{f_name}", use_container_width=True):
                        ans, touch = "YES", "true"
                with cn:
                    if st.button("❌ NO", key=f"n_{f_name}", use_container_width=True):
                        ans, touch = "NO", "false"

            elif i_type == "scale":
                st.markdown(f"##### {ui['rate_scale']}")
                sc = st.slider("Severity:", 0, 10, 5, key=f"sc_{f_name}")
                if st.button("Confirm Rating ➔", key=f"sc_btn_{f_name}"):
                    ans, touch = str(sc), str(sc)

            # Primary Text input form
            form_title = ui['type_box'] if cur_mode == "voice" else f"⌨️ {ui['type_box'].replace(' (Alternative)', '')}"
            st.markdown(f"##### {form_title}")
            with st.form(f"txt_form_{f_name}"):
                txt = st.text_input("Your Response:", key=f"txt_in_{f_name}", placeholder="Type answer here...")
                c_s1, c_s2 = st.columns([3, 1])
                with c_s1:
                    sub_txt = st.form_submit_button(ui['submit_btn'], use_container_width=True)
                with c_s2:
                    clr_txt = st.form_submit_button(ui['clear_btn'], use_container_width=True)
                
                if sub_txt and txt.strip():
                    ans = txt.strip()

        # ── 5. PROCESS AND ADVANCE TO NEXT TURN ──
        if ans:
            with st.spinner("⚡ " + ui.get("rec_processing", "Understanding response...")):
                m_res, err = api_post(f"/history/session/{vid}/message", json_data={
                    "patient_message": ans,
                    "target_field": f_name,
                    "is_touch_input": touch is not None,
                    "touch_value": touch,
                    "language": cur_lang
                })
                if m_res:
                    # Append Patient Response to Dialogue History
                    st.session_state[dlg_key].append({"role": "patient", "content": ans, "q_num": curr_n})
                    st.session_state[s_key] = m_res
                    st.rerun()
                else:
                    st.error(f"❌ {err}")


# ── 9. Patient Portal Orchestrator ───────────────────────────────────────────
def render_patient_portal():
    u_data = st.session_state.get("user_data", {})
    patient_id = u_data.get("patient_id", "PAT-000001")
    full_name = u_data.get("full_name") or u_data.get("username", "Patient")

    cur_lang = st.session_state.get("pref_lang", "en")
    ui = PATIENT_UI_STRINGS.get(cur_lang, PATIENT_UI_STRINGS["en"])

    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div>
                <span style="font-size:0.85rem; font-weight:700; color:#38BDF8; letter-spacing:0.05em; text-transform:uppercase;">
                    {ui['pref_title']}
                </span>
                <h1 style="margin:4px 0 6px 0; color:#FFFFFF; font-size:2rem; font-weight:800;">
                    Welcome, {full_name}
                </h1>
                <div style="color:#94A3B8; font-size:0.95rem;">
                    Patient ID: <span class="badge-normal" style="font-family:monospace; font-size:0.9rem;">{patient_id}</span>
                </div>
            </div>
            <div style="font-size:3rem; background:rgba(255,255,255,0.06); padding:10px 16px; border-radius:16px; border:1px solid rgba(255,255,255,0.1);">
                🏥
            </div>
        </div>
        <p style="color:#CBD5E1; font-size:1.05rem; margin:14px 0 0 0;">
            {ui['pref_sub']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs([
        "🩺 Clinical Intake & Symptoms", 
        "📑 Medical Document Upload", 
        "📋 Visit History", 
        "💊 My Prescriptions"
    ])

    # Tab 1: Clinical Intake (Page 2 Preferences -> Page 3 Clinical Interview)
    with t1:
        patient_stage = st.session_state.get("patient_stage", "preferences")
        if patient_stage == "preferences":
            render_patient_preference_screen(patient_id, full_name)
        else:
            render_patient_interview(patient_id, full_name)

    # Tab 2: Documents
    with t2:
        st.markdown("### 📑 Upload Medical Reports (CBC, X-Ray, Prescriptions)")
        v_list, _ = api_get(f"/patients/{patient_id}/visits")
        v_id_doc = v_list[0]["visit_id"] if v_list else f"VIS-{patient_id[-6:]}"

        c_t, c_f = st.columns([1, 2])
        with c_t:
            d_type = st.selectbox("Document Type Hint", ["LAB_REPORT", "PRESCRIPTION", "HANDWRITTEN_PRESCRIPTION", "XRAY", "DISCHARGE_SUMMARY"])
        with c_f:
            up_file = st.file_uploader("Select PDF or Image", type=["pdf", "png", "jpg", "jpeg"])

        if up_file and st.button("🔬 Extract Document Data", use_container_width=True):
            with st.spinner("Extracting parameters with OCR Pipeline..."):
                files = {"file": (up_file.name, up_file.getvalue(), up_file.type)}
                data = {"patient_id": patient_id, "document_type": d_type, "visit_id": v_id_doc}
                res, err = api_post("/documents/upload", json_data=data, files=files)
                if res:
                    st.success(f"✓ Processed Document: `{res['document_id']}`")
                    st.write(f"**Confidence:** `{res['ocr_confidence']*100:.1f}%`")
                    st_data = res.get("structured_data", {})
                    t_list = st_data.get("tests", [])
                    if t_list:
                        abnormal_count = sum(1 for t in t_list if t.get("status") in ("HIGH", "LOW", "ABNORMAL", "CRITICAL") or t.get("flag") in ("#", "*", "H", "L"))
                        st.markdown(f"""
                        <div style="background:rgba(14,165,233,0.1); border:1px solid #0EA5E9; border-radius:8px; padding:10px; margin-bottom:12px;">
                            <b>🧪 Total Tests Extracted:</b> {len(t_list)} | 
                            <b>⚠️ Flagged/Abnormal:</b> <span style="color:{'#EF4444' if abnormal_count > 0 else '#10B981'}; font-weight:700;">{abnormal_count}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.dataframe(t_list, use_container_width=True)
                    with st.expander("🔍 View Raw JSON Structured Output", expanded=True):
                        st.json(st_data)
                else:
                    st.error(f"❌ {err}")

    # Tab 3: Visit History
    with t3:
        st.markdown("### 📋 Your Visit History & Recorded Clinical Data")
        all_v, _ = api_get(f"/patients/{patient_id}/visits")
        if all_v:
            for v in all_v:
                v_date = v.get('visit_date', '')[:10]
                v_prio = v.get('priority', 'NORMAL')
                with st.expander(f"🗓️ Visit {v['visit_id']} ({v_date}) — {v.get('department')}", expanded=(v == all_v[0])):
                    ch, _ = api_get(f"/history/{v['visit_id']}")
                    if ch and ch.get("history_json"):
                        h_json = ch.get("history_json", {})
                        cc_dict = h_json.get("chief_complaint", {})
                        cc_text = cc_dict.get("text") or cc_dict.get("canonical") or "General Outpatient Consultation"
                        hpi = h_json.get("hpi", {})
                        dur = hpi.get("duration_days")
                        sev = hpi.get("severity")
                        loc = hpi.get("location")
                        triage = h_json.get("triage", {})
                        flg = triage.get("flag", "GREEN")
                        t_color = "#EF4444" if flg == "RED" else "#F59E0B" if flg == "YELLOW" else "#10B981"
                        prio_text = "Priority Clinical Attention" if flg == "RED" else "Routine Evaluation"

                        st.markdown(f"""
                        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                                <span style="font-weight: 800; font-size: 1.15rem; color: #FFFFFF;">🩺 {cc_text.title()}</span>
                                <span style="background: rgba({('239,68,68' if flg=='RED' else '16,185,129')}, 0.2); color: {t_color}; border: 1px solid {t_color}; padding: 3px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.8rem;">
                                    ● {flg} • {prio_text}
                                </span>
                            </div>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; font-size: 0.9rem; color: #E2E8F0;">
                                <div><b>⏱️ Duration:</b> {f"{dur} Days" if dur is not None else "Reported"}</div>
                                <div><b>📊 Severity:</b> {f"{sev}/10" if sev is not None else "Recorded"}</div>
                                <div><b>📍 Location:</b> {loc.title() if loc else "General"}</div>
                                <div><b>🏥 Department:</b> {v.get('department')}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("ℹ️ Clinical history intake has not been recorded yet for this visit.")
        else:
            st.info("No past visits recorded.")

    # Tab 4: Prescriptions
    with t4:
        st.markdown("### 💊 Prescriptions")
        rxs, _ = api_get(f"/patients/{patient_id}/prescriptions")
        if rxs:
            for rx in rxs:
                st.markdown(f"#### Order `{rx['prescription_id']}` (Visit: {rx['visit_id']})")
                if rx.get("items"):
                    st.table(rx["items"])
                pdf_b, _ = api_get_bytes(f"/prescriptions/{rx['prescription_id']}/pdf")
                if pdf_b:
                    st.download_button(
                        "📥 Download Official PDF",
                        data=pdf_b,
                        file_name=f"{rx['prescription_id']}.pdf",
                        mime="application/pdf",
                        key=f"dl_{rx['prescription_id']}"
                    )
                st.divider()
        else:
            st.info("No active prescriptions.")


def _start_visit_intake(patient_id, department="General Medicine", complaint=None, language="en"):
    new_v, err = api_post("/visits", json_data={
        "patient_id": patient_id,
        "department": department,
        "priority": "NORMAL"
    })
    if new_v:
        vid = new_v["visit_id"]
        res, _ = api_post("/history/session/start", json_data={
            "patient_id": patient_id,
            "visit_id": vid,
            "language": language or "en",
            "initial_complaint": complaint
        })
        if res:
            st.session_state[f"session_data_{vid}"] = res
        return vid
    else:
        st.error(f"❌ Error creating visit: {err}")
        return None



# ── 7. Doctor Portal & Clinical Overview ────────────────────────────────────
def extract_patient_lab_trends(documents):
    """
    Extracts longitudinal numeric parameters from documents across visits for charting.
    Returns dict: { 'Hemoglobin': [{'date': '2026-08-20', 'value': 9.2, 'unit': 'g/dL', 'doc_id': 'DOC-123', 'ref': '12-15'}, ...] }
    """
    if not documents:
        return {}
    
    alias_map = {
        "hemoglobin": "Hemoglobin", "hb": "Hemoglobin", "hgb": "Hemoglobin",
        "wbc": "WBC (Total Count)", "white blood cells": "WBC (Total Count)", "tlc": "WBC (Total Count)", "total leukocyte count": "WBC (Total Count)",
        "platelet": "Platelet Count", "plt": "Platelet Count",
        "rbc": "RBC Count", "red blood cells": "RBC Count",
        "glucose": "Blood Glucose (Fasting)", "fasting blood sugar": "Blood Glucose (Fasting)", "fbs": "Blood Glucose (Fasting)",
        "creatinine": "Serum Creatinine",
        "hba1c": "HbA1c", "glycated": "HbA1c",
        "systolic": "Blood Pressure (Systolic)", "diastolic": "Blood Pressure (Diastolic)",
        "cholesterol": "Total Cholesterol", "sgot": "AST / SGOT", "sgpt": "ALT / SGPT"
    }
    
    trends = {}
    for doc in documents:
        d_date = (doc.get("document_date") or doc.get("created_at") or "")[:10]
        s_data = doc.get("structured_data", {})
        tests = s_data.get("tests", []) if isinstance(s_data, dict) else []
        for t in tests:
            raw_name = str(t.get("name", "")).strip().lower()
            norm_name = None
            for k, v in alias_map.items():
                if k in raw_name:
                    norm_name = v
                    break
            if not norm_name:
                norm_name = str(t.get("name", "")).strip().title()
            
            raw_val = str(t.get("value", "")).strip()
            num_match = re.search(r"[-+]?\d*\.\d+|\d+", raw_val)
            if num_match:
                try:
                    f_val = float(num_match.group())
                    if norm_name not in trends:
                        trends[norm_name] = []
                    trends[norm_name].append({
                        "date": d_date or "Unknown Date",
                        "value": f_val,
                        "unit": t.get("unit", ""),
                        "reference_range": t.get("reference_range", "N/A"),
                        "doc_id": doc.get("document_id"),
                        "doc_type": doc.get("document_type")
                    })
                except ValueError:
                    pass

    # Filter only parameters with >= 2 distinct data points and sort by date
    valid_trends = {}
    for k, pts in trends.items():
        if len(pts) >= 2:
            valid_trends[k] = sorted(pts, key=lambda x: x["date"])
    return valid_trends


def render_doctor_portal():
    st.title("👨‍⚕️ Doctor Panel — Clinical Consultation & Patient Overview")
    c_q, c_m = st.columns([1, 3])

    with c_q:
        st.markdown("### Today's Queue")
        queue, _ = api_get("/doctor/queue")
        if queue:
            for v in queue:
                p_id = v["patient_id"]
                v_id = v["visit_id"]
                badge = "🔴" if v.get("priority") in ["HIGH", "EMERGENCY"] else "🟢"
                prio_label = "RED" if v.get("priority") in ["HIGH", "EMERGENCY"] else "NORMAL"
                
                col_select, col_dismiss = st.columns([5, 1])
                with col_select:
                    if st.button(
                        f"{badge} {prio_label} | {p_id} ({v_id})",
                        key=f"q_btn_{v_id}",
                        use_container_width=True
                    ):
                        st.session_state["doc_pid"] = p_id
                        st.session_state["doc_vid"] = v_id
                with col_dismiss:
                    if st.button("✕", key=f"q_dismiss_{v_id}", help=f"Remove {v_id} from queue", use_container_width=True):
                        res, err = api_post(f"/visits/{v_id}/cancel")
                        if res:
                            if st.session_state.get("doc_vid") == v_id:
                                st.session_state["doc_vid"] = None
                            st.toast(f"✓ {v_id} removed from queue", icon="✅")
                            st.rerun()
                        else:
                            st.toast(f"Could not remove: {err}", icon="❌")
        else:
            st.info("✅ No patients currently waiting in queue.")

        st.divider()
        pid_in = st.text_input("Lookup Patient ID:", value=st.session_state.get("doc_pid", "PAT-000001"))
        if st.button("Open Record", use_container_width=True):
            st.session_state["doc_pid"] = pid_in
            st.session_state["doc_vid"] = None
            st.rerun()

    with c_m:
        pid = st.session_state.get("doc_pid", "PAT-000001")
        vid = st.session_state.get("doc_vid")
        p_data, _ = api_get(f"/patients/{pid}")

        if not p_data:
            st.warning(f"Patient record `{pid}` not found. Please select a patient from the queue or search by ID.")
            return

        # ── PATIENT CLINICAL HEADER ──
        p_name = p_data.get('name', 'Unknown')
        p_gender = p_data.get('gender', 'N/A')
        p_dob = p_data.get('date_of_birth', 'N/A')
        p_lang = p_data.get('preferred_language', 'English')
        p_phone = p_data.get('phone', 'N/A')
        
        # Get visits list to determine active visit info
        all_visits, _ = api_get(f"/patients/{pid}/visits")
        current_visit_obj = None
        if all_visits:
            if vid:
                current_visit_obj = next((v for v in all_visits if v["visit_id"] == vid), all_visits[0])
            else:
                current_visit_obj = all_visits[0]
                vid = current_visit_obj["visit_id"]
                st.session_state["doc_vid"] = vid

        act_v_date = current_visit_obj.get("visit_date", "")[:10] if current_visit_obj else "Today"
        act_dept = current_visit_obj.get("department", "General Medicine") if current_visit_obj else "General Medicine"
        act_prio = current_visit_obj.get("priority", "NORMAL") if current_visit_obj else "NORMAL"
        badge_prio_color = "#EF4444" if act_prio in ["RED", "HIGH", "EMERGENCY"] else "#10B981"

        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(14, 165, 233, 0.12) 0%, rgba(99, 102, 241, 0.08) 100%); border: 1.5px solid rgba(14, 165, 233, 0.35); border-radius: 16px; padding: 18px 24px; margin-bottom: 18px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                <div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                        <h2 style="margin: 0; color: #FFFFFF; font-size: 1.5rem; font-weight: 800;">{p_name}</h2>
                        <span style="background: rgba(14,165,233,0.25); color: #38BDF8; border: 1px solid #38BDF8; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 0.85rem;">{pid}</span>
                    </div>
                    <div style="color: #94A3B8; font-size: 0.9rem; display: flex; gap: 14px; flex-wrap: wrap;">
                        <span>👤 <b>Sex:</b> {p_gender}</span>
                        <span>🎂 <b>DOB:</b> {p_dob}</span>
                        <span>🌐 <b>Language:</b> {p_lang}</span>
                        <span>📞 <b>Phone:</b> {p_phone}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid {badge_prio_color}; border-radius: 10px; padding: 6px 14px; display: inline-block;">
                        <span style="color: #94A3B8; font-size: 0.75rem; text-transform: uppercase; font-weight: 700;">Active Review Visit</span>
                        <div style="color: #FFFFFF; font-weight: 800; font-size: 0.95rem;">{vid or 'None'} • {act_dept}</div>
                        <span style="color: {badge_prio_color}; font-weight: 700; font-size: 0.8rem;">● {act_prio} PRIORITY</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 5 CLINICAL DOCTOR TABS ──
        tab_summary, tab_visits, tab_docs, tab_trends, tab_rx = st.tabs([
            "📋 Clinical Overview", 
            "🗓️ Visit History", 
            "📑 Medical Documents", 
            "📈 Trends & Charts", 
            "💊 Prescriptions"
        ])

        # ══════════════════════════════════════════════════════════════════════
        # TAB 1: CLINICAL OVERVIEW (STRUCTURED SUMMARY & IMPORTANT FINDINGS)
        # ══════════════════════════════════════════════════════════════════════
        with tab_summary:
            st.markdown("### 🤖 Structured Clinical Briefing")
            st.caption("🔒 Non-diagnostic clinical summary synthesized strictly from EMR history, patient intake, and verified lab records.")

            with st.spinner("🔄 Loading clinical briefing via Groq AI..."):
                summary, err = api_get(f"/doctor/patients/{pid}/summary", params={"visit_id": vid} if vid else None, timeout=60)

            if summary:
                # Triage Banner
                flag = summary.get("current_triage_flag", act_prio)
                t_color = "#EF4444" if flag in ["RED", "HIGH", "EMERGENCY"] else "#10B981"
                st.markdown(f"""
                <div style="background: rgba({('239,68,68' if flag in ['RED','HIGH','EMERGENCY'] else '16,185,129')}, 0.12); border: 1.5px solid {t_color}; border-radius: 12px; padding: 12px 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 1.8rem;">{'🚨' if flag in ['RED','HIGH','EMERGENCY'] else '✅'}</span>
                    <div>
                        <div style="font-weight: 800; color: {t_color}; font-size: 1.05rem;">TRIAGE STATUS: {flag} {'PRIORITY CLINICAL ATTENTION' if flag in ['RED','HIGH','EMERGENCY'] else 'ROUTINE EVALUATION'}</div>
                        <div style="color: #94A3B8; font-size: 0.85rem;">Synthesized from patient case-taking interview and verified clinical questionnaires</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Structured Medical Summary Cards
                sections = [
                    ("🩺 Chief Complaint", "chief_complaint"),
                    ("📖 History of Present Illness (HPI)", "hpi"),
                    ("📋 Relevant Past Medical & Surgical History", "relevant_past_history"),
                    ("🧪 Previous Investigations & Significant Lab Findings", "relevant_previous_investigations"),
                    ("💉 Previous Treatments & Interventions", "previous_treatments"),
                    ("👨‍👩‍👧 Family & Personal History", "family_personal_history"),
                ]

                for label, key in sections:
                    val = summary.get(key, "")
                    if val and val.lower() not in ("none", "null", "n/a", "not recorded", ""):
                        st.markdown(f"""
                        <div class="med-card" style="margin-bottom: 12px; background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px 18px;">
                            <div style="font-size: 0.8rem; font-weight: 800; color: #38BDF8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">{label}</div>
                            <div style="color: #E2E8F0; line-height: 1.6; font-size: 0.95rem;">{val}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # Medications & Drug Allergies Dual Card
                meds = summary.get("medications", [])
                allergies = summary.get("allergies", [])
                col_m, col_a = st.columns(2)
                with col_m:
                    st.markdown(f"""
                    <div class="med-card" style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 12px; padding: 14px 18px; height: 100%;">
                        <div style="font-size: 0.8rem; font-weight: 800; color: #38BDF8; text-transform: uppercase; margin-bottom: 8px;">💊 Current / Prior Medications</div>
                        {''.join(f'<div style="color:#E2E8F0; margin-bottom: 4px;">• {m}</div>' for m in meds) if meds else '<div style="color:#64748B;">None recorded in current EMR</div>'}
                    </div>
                    """, unsafe_allow_html=True)
                with col_a:
                    st.markdown(f"""
                    <div class="med-card" style="background: rgba(239, 68, 68, 0.08); border: 1.5px solid rgba(239, 68, 68, 0.35); border-radius: 12px; padding: 14px 18px; height: 100%;">
                        <div style="font-size: 0.8rem; font-weight: 800; color: #F87171; text-transform: uppercase; margin-bottom: 8px;">⚠️ Known Drug Allergies</div>
                        {''.join(f'<div style="color:#FCA5A5; font-weight: 700; margin-bottom: 4px;">⚠️ {a}</div>' for a in allergies) if allergies else '<div style="color:#10B981; font-weight: 600;">✓ No known drug allergies documented</div>'}
                    </div>
                    """, unsafe_allow_html=True)

                # Grounding Sources
                sources = summary.get("sources", [])
                if sources:
                    st.write("")
                    with st.expander("📎 Grounding EMR Sources Used for Summary", expanded=False):
                        for src in sources:
                            st.write(f"• `{src.get('source_id')}` — {src.get('type', src.get('source_type', ''))}")
            else:
                if err and ("403" in str(err) or "permitted" in str(err)):
                    st.error("🔒 **Access Denied**: Only Doctor and Staff roles can view patient summaries.")
                elif err and "No history" in str(err):
                    st.info("ℹ️ No clinical history recorded yet for this patient. Ask the patient to complete the clinical intake questionnaire first.")
                else:
                    st.warning(f"⚠️ Clinical intake briefing pending for `{vid}`: **{err or 'No intake data recorded yet'}**")

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2: VISIT HISTORY (CHRONOLOGICAL VISITS & DETAILED RECORDS)
        # ══════════════════════════════════════════════════════════════════════
        with tab_visits:
            st.markdown(f"### 🗓️ Longitudinal Visit History for `{pid}`")
            if all_visits:
                for v in all_visits:
                    v_vid = v['visit_id']
                    v_date = v.get('visit_date', '')[:10]
                    v_prio = v.get('priority', 'NORMAL')
                    is_current = (v_vid == vid)
                    
                    # Fetch visit specific history & counts
                    ch, _ = api_get(f"/history/{v_vid}")
                    v_docs, _ = api_get(f"/patients/{pid}/documents")
                    v_doc_count = sum(1 for d in (v_docs or []) if d.get("visit_id") == v_vid)
                    v_rxs, _ = api_get(f"/patients/{pid}/prescriptions")
                    has_rx = any(r.get("visit_id") == v_vid for r in (v_rxs or []))

                    v_badge_prio = "🔴 RED PRIORITY" if v_prio in ["RED", "HIGH", "EMERGENCY"] else "🟢 ROUTINE"
                    v_title = f"🗓️ Visit {v_vid} ({v_date}) — {v.get('department')} {'[ACTIVE REVIEW]' if is_current else ''}"
                    
                    with st.expander(v_title, expanded=is_current):
                        c_vh1, c_vh2 = st.columns([3, 1])
                        with c_vh1:
                            st.write(f"**Department:** `{v.get('department')}` | **Status:** `{v.get('status')}` | **Priority:** `{v_badge_prio}`")
                            st.write(f"**Associated Records:** 📑 {v_doc_count} Document(s) | 💊 {'Prescription on file' if has_rx else 'No prescription'}")
                        with c_vh2:
                            if not is_current:
                                if st.button(f"🎯 Switch to {v_vid}", key=f"sw_v_{v_vid}", use_container_width=True):
                                    st.session_state["doc_vid"] = v_vid
                                    st.rerun()
                            else:
                                st.markdown("<span style='color:#38BDF8; font-weight:700;'>✓ Currently Viewing</span>", unsafe_allow_html=True)

                        if ch and ch.get("history_json"):
                            h_json = ch.get("history_json", {})
                            cc_dict = h_json.get("chief_complaint", {})
                            cc_text = cc_dict.get("text") or cc_dict.get("canonical") or "General Outpatient Consultation"
                            hpi = h_json.get("hpi", {})
                            triage = h_json.get("triage", {})
                            flg = triage.get("flag", "NORMAL")
                            flg_color = "#EF4444" if flg in ["RED", "HIGH", "EMERGENCY"] else "#10B981"

                            st.markdown(f"""
                            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 12px; padding: 14px 18px; margin: 10px 0;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                    <span style="font-weight: 700; color: #FFFFFF; font-size: 1.05rem;">🩺 {cc_text.title()}</span>
                                    <span style="color: {flg_color}; font-weight: 800; font-size: 0.85rem;">● Triage: {flg}</span>
                                </div>
                                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; font-size: 0.88rem; color: #CBD5E1;">
                                    <div><b>⏱️ Duration:</b> {hpi.get('duration_days', 'N/A')} Days</div>
                                    <div><b>📊 Severity:</b> {hpi.get('severity', 'N/A')}/10</div>
                                    <div><b>📍 Location:</b> {str(hpi.get('location', 'N/A')).title()}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            with st.expander("🔍 View Complete Raw Intake Fact Structure", expanded=False):
                                st.json(h_json)
                        else:
                            st.info("No intake history recorded for this visit.")
            else:
                st.info("No previous visits recorded.")

        # ══════════════════════════════════════════════════════════════════════
        # TAB 3: MEDICAL DOCUMENTS (CLEAN CARDS, KEY FINDINGS, ORIGINAL PDF)
        # ══════════════════════════════════════════════════════════════════════
        with tab_docs:
            st.markdown(f"### 📑 Medical Reports & Diagnostic Documents for `{pid}`")
            p_docs, _ = api_get(f"/patients/{pid}/documents")
            
            if p_docs:
                for doc in p_docs:
                    d_id = doc["document_id"]
                    d_type = doc.get("document_type", "LAB_REPORT")
                    d_date = (doc.get("document_date") or doc.get("created_at") or "")[:10]
                    d_conf = doc.get("ocr_confidence", 1.0)
                    s_data = doc.get("structured_data", {})
                    tests = s_data.get("tests", []) if isinstance(s_data, dict) else []
                    
                    # Compute abnormal parameters
                    abnormal_tests = [
                        t for t in tests 
                        if t.get("status") in ("HIGH", "LOW", "ABNORMAL", "CRITICAL") 
                        or t.get("flag") in ("#", "*", "H", "L")
                    ]
                    
                    # Card Header & Key Findings Summary
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.75); border: 1.5px solid rgba(14, 165, 233, 0.3); border-radius: 14px; padding: 18px 20px; margin-bottom: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
                            <div>
                                <span style="font-weight: 800; font-size: 1.15rem; color: #FFFFFF;">📑 {d_type.replace('_', ' ')}</span>
                                <span style="background: rgba(14,165,233,0.2); color: #38BDF8; padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem; margin-left: 8px;">{d_id}</span>
                            </div>
                            <div style="color: #94A3B8; font-size: 0.85rem;">
                                🗓️ <b>Date:</b> {d_date} | 🎯 <b>OCR Confidence:</b> {d_conf*100:.1f}%
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Highlight key findings
                    if d_type in ("LAB_REPORT", "CBC", "BLOOD_TEST") or tests:
                        if abnormal_tests:
                            st.markdown(f"""
                            <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;">
                                <span style="font-weight: 800; color: #F87171; font-size: 0.9rem;">⚠️ KEY FINDINGS: {len(abnormal_tests)} Abnormal / Out-of-Range Parameters Detected</span>
                                <div style="margin-top: 6px; font-size: 0.88rem; color: #FCA5A5;">
                                    {''.join(f'<div>• <b>{t.get("name")}:</b> {t.get("value")} {t.get("unit","")} (Ref: {t.get("reference_range","N/A")}) — <span style="color:#EF4444; font-weight:700;">{t.get("status", "ABNORMAL")}</span></div>' for t in abnormal_tests[:5])}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 8px 14px; margin-bottom: 10px; color: #34D399; font-size: 0.88rem; font-weight: 600;">
                                ✓ All {len(tests)} extracted parameters are within normal reference ranges.
                            </div>
                            """, unsafe_allow_html=True)
                    elif d_type in ("XRAY", "IMAGING", "SCAN", "DISCHARGE_SUMMARY"):
                        findings_text = s_data.get("impression") or s_data.get("findings") or s_data.get("clinical_notes") or doc.get("raw_text", "")[:300]
                        if findings_text:
                            st.markdown(f"""
                            <div style="background: rgba(14, 165, 233, 0.1); border: 1px solid rgba(14, 165, 233, 0.25); border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;">
                                <span style="font-weight: 800; color: #38BDF8; font-size: 0.85rem; text-transform: uppercase;">Radiological Impression / Clinical Summary:</span>
                                <div style="color: #E2E8F0; font-size: 0.92rem; margin-top: 4px; line-height: 1.5;">{findings_text}</div>
                            </div>
                            """, unsafe_allow_html=True)

                    st.markdown("</div>", unsafe_allow_html=True)

                    # Action buttons (View Extracted Details + Open Original Document)
                    col_det, col_orig = st.columns([1, 1])
                    with col_det:
                        with st.expander(f"🔍 View Extracted Parameters ({len(tests)} items)"):
                            if tests:
                                st.dataframe(tests, use_container_width=True)
                            else:
                                st.text_area("Extracted OCR Text Excerpt:", value=doc.get("raw_text", ""), height=150, disabled=True, key=f"txt_{d_id}")
                    
                    with col_orig:
                        doc_bytes, _ = api_get_bytes(f"/documents/{d_id}/download")
                        if doc_bytes:
                            st.download_button(
                                label=f"📥 Open / Download Original Report ({d_id})",
                                data=doc_bytes,
                                file_name=f"{d_id}_{d_type}.pdf",
                                mime="application/pdf",
                                key=f"dl_btn_{d_id}",
                                use_container_width=True
                            )
                        else:
                            st.button(f"📄 Original File Linked ({d_id})", disabled=True, use_container_width=True)
                    
                    st.divider()
            else:
                st.info("No medical documents or lab reports uploaded yet for this patient.")

        # ══════════════════════════════════════════════════════════════════════
        # TAB 4: TRENDS & CHARTS (LONGITUDINAL LAB PARAMETERS)
        # ══════════════════════════════════════════════════════════════════════
        with tab_trends:
            st.markdown(f"### 📈 Longitudinal Biomarker Trends & Laboratory Charts for `{pid}`")
            st.caption("Visualizes chronological progression of repeated laboratory parameters across dated diagnostic reports.")
            
            p_docs_for_trend, _ = api_get(f"/patients/{pid}/documents")
            trends_dict = extract_patient_lab_trends(p_docs_for_trend or [])

            if trends_dict:
                sel_param = st.selectbox(
                    "📊 Select Laboratory Parameter to Trend:", 
                    options=list(trends_dict.keys()),
                    format_func=lambda x: f"{x} ({len(trends_dict[x])} data points)"
                )
                
                pts = trends_dict[sel_param]
                df_trend = pd.DataFrame(pts)
                
                # Summary metrics (Latest vs Baseline)
                first_val = pts[0]["value"]
                latest_val = pts[-1]["value"]
                delta = latest_val - first_val
                unit_str = pts[-1].get("unit", "")
                ref_range_str = pts[-1].get("reference_range", "N/A")

                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1:
                    st.metric("Latest Value", f"{latest_val} {unit_str}", delta=f"{delta:+.2f} {unit_str}" if len(pts)>1 else None)
                with c_m2:
                    st.metric("Initial Baseline", f"{first_val} {unit_str}", f"Date: {pts[0]['date']}")
                with c_m3:
                    st.metric("Reference Range", ref_range_str)

                # Line Chart
                chart_df = df_trend[["date", "value"]].set_index("date")
                st.line_chart(chart_df, color="#0EA5E9", use_container_width=True)

                # Traceability Table
                st.markdown("##### 📋 Traceable Clinical Data Points:")
                display_df = df_trend[["date", "value", "unit", "reference_range", "doc_id", "doc_type"]]
                display_df.columns = ["Report Date", "Numeric Value", "Unit", "Reference Range", "Source Document ID", "Document Type"]
                st.dataframe(display_df, use_container_width=True)
            else:
                st.markdown("""
                <div style="background: rgba(14, 165, 233, 0.08); border: 1.5px dashed rgba(14, 165, 233, 0.35); border-radius: 14px; padding: 24px; text-align: center; margin: 16px 0;">
                    <div style="font-size: 2.2rem; margin-bottom: 8px;">📈</div>
                    <h4 style="color: #38BDF8; margin: 0 0 6px 0;">Longitudinal Data Accumulation</h4>
                    <p style="color: #94A3B8; max-width: 540px; margin: 0 auto; font-size: 0.92rem; line-height: 1.5;">
                        Longitudinal trend visualization requires at least 2 dated lab reports containing comparable parameters (e.g. Hemoglobin, Blood Glucose, Serum Creatinine). As sequential reports are uploaded across visits, trend curves will automatically chart here.
                    </p>
                </div>
                """, unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 5: PRESCRIPTIONS (PAST ORDERS & VOICE/TEXT RX GENERATOR)
        # ══════════════════════════════════════════════════════════════════════
        with tab_rx:
            st.markdown("### 💊 Prescription Orders & Voice/Text Generator")
            
            # 1. Past Prescription Orders for this patient
            p_rxs, _ = api_get(f"/patients/{pid}/prescriptions")
            if p_rxs:
                with st.expander(f"📜 Existing Prescriptions on File ({len(p_rxs)} Orders)", expanded=False):
                    for rx in p_rxs:
                        st.markdown(f"#### Order `{rx['prescription_id']}` (Visit: `{rx['visit_id']}`) — Status: `{rx.get('status')}`")
                        if rx.get("items"):
                            st.table(rx["items"])
                        pdf_b, _ = api_get_bytes(f"/prescriptions/{rx['prescription_id']}/pdf")
                        if pdf_b:
                            st.download_button(
                                "📥 Download Official PDF",
                                data=pdf_b,
                                file_name=f"{rx['prescription_id']}.pdf",
                                mime="application/pdf",
                                key=f"dl_rx_{rx['prescription_id']}"
                            )
                        st.divider()

            # 2. Generator for Current Active Visit
            act_vid = vid or (all_visits[0]["visit_id"] if all_visits else None)
            if not act_vid:
                st.warning("Please create or select an active visit to generate a new prescription.")
            else:
                st.markdown(f"#### 🎙️ Prescribe for Active Visit: `{act_vid}`")
                
                # Doctor Voice Dictation Controller (Click Only - No Hover Trigger)
                st.markdown("""
                <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(14, 165, 233, 0.25); border-radius: 12px; padding: 14px 18px; margin: 10px 0 16px 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <span style="font-weight: 700; color: #38BDF8; font-size: 0.95rem;">🎙️ DOCTOR VOICE DICTATION (Click to Record)</span>
                            <div style="font-size: 0.8rem; color: #94A3B8;">Click the microphone below to dictate medicines and dosage instructions. The text will automatically fill the input box below.</div>
                        </div>
                        <span class="badge-normal" style="font-size: 0.75rem;">Whisper Large V3 (Clinical Precision)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if "doc_dictation_text" not in st.session_state:
                    st.session_state["doc_dictation_text"] = "Paracetamol 650 mg twice daily for 3 days after food. Amoxicillin 500 mg thrice daily for 5 days."

                # Primary Voice Recorder (Groq Whisper-large-v3)
                try:
                    from audio_recorder_streamlit import audio_recorder
                    col_d_mic, col_d_info = st.columns([1, 4])
                    with col_d_mic:
                        doc_audio = audio_recorder(
                            text="Click to dictate voice:",
                            recording_color="#e63946",
                            neutral_color="#0284c7",
                            icon_size="2x",
                            key="doc_rx_mic"
                        )
                    with col_d_info:
                        if doc_audio:
                            with st.spinner("⚡ Transcribing clinical voice dictation via Groq Whisper-large-v3..."):
                                files = {"audio": ("dictation.wav", doc_audio, "audio/wav")}
                                res_doc_asr, err_doc_asr = api_post("/voice/transcribe", files=files, json_data={"model_quality": "accurate"})
                                if res_doc_asr and res_doc_asr.get("transcript"):
                                    transcribed_v = res_doc_asr["transcript"].strip()
                                    if transcribed_v:
                                        st.session_state["doc_dictation_text"] = transcribed_v
                                        st.success(f"✓ Voice Transcribed: \"{transcribed_v}\"")
                                        st.rerun()
                except Exception:
                    pass

                # Live In-Browser Speech Recognition Fallback
                with st.expander("🎙️ Or Use In-Browser Live Streaming Dictator (Zero Latency)"):
                    st.components.v1.html("""
                    <div style="font-family: sans-serif; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 12px 16px;">
                        <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap;">
                            <button id="doc_start_btn" onclick="startDocRec()" style="background: #0284C7; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; font-size: 0.85rem;">
                                🔴 Start Dictation
                            </button>
                            <button id="doc_pause_btn" onclick="toggleDocPause()" style="background: #475569; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; font-size: 0.85rem; display: none;">
                                ⏸️ Pause
                            </button>
                            <button id="doc_stop_btn" onclick="stopDocRec()" style="background: #DC2626; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; font-size: 0.85rem; display: none;">
                                ⏹️ Stop Dictation
                            </button>
                            <span id="doc_status" style="color: #94A3B8; font-size: 0.85rem; margin-left: 8px;">Status: Ready (Click Start)</span>
                        </div>
                        <div id="doc_live_box" style="min-height: 44px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 10px 14px; color: #38BDF8; font-size: 0.95rem; font-weight: 500;">
                            <i>Click "Start Dictation" and speak medication names, dosages, and durations...</i>
                        </div>
                    </div>
                    <script>
                    var docRec = null;
                    var docIsPaused = false;
                    var docTranscript = "";

                    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                        var SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                        docRec = new SpeechRec();
                        docRec.continuous = true;
                        docRec.interimResults = true;
                        docRec.lang = "en-IN";

                        docRec.onresult = function(event) {
                            var interim = "";
                            for (var i = event.resultIndex; i < event.results.length; ++i) {
                                if (event.results[i].isFinal) {
                                    docTranscript += event.results[i][0].transcript + " ";
                                } else {
                                    interim += event.results[i][0].transcript;
                                }
                            }
                            document.getElementById('doc_live_box').innerHTML = "<b>💊 Dictating Live:</b> " + (docTranscript + interim);
                        };

                        docRec.onerror = function(event) {
                            document.getElementById('doc_status').innerHTML = "⚠️ Status: " + event.error;
                        };
                    }

                    function startDocRec() {
                        if (!docRec) {
                            alert("Speech recognition not supported in this browser. Please type dictation text.");
                            return;
                        }
                        docTranscript = "";
                        docRec.start();
                        document.getElementById('doc_status').innerHTML = "🟢 <b>Listening Live to Dictation...</b>";
                        document.getElementById('doc_start_btn').style.display = "none";
                        document.getElementById('doc_pause_btn').style.display = "inline-block";
                        document.getElementById('doc_stop_btn').style.display = "inline-block";
                        document.getElementById('doc_live_box').innerHTML = "<i>Listening to your clinical dictation...</i>";
                    }

                    function toggleDocPause() {
                        if (!docIsPaused) {
                            docRec.stop();
                            docIsPaused = true;
                            document.getElementById('doc_pause_btn').innerHTML = "▶️ Resume";
                            document.getElementById('doc_status').innerHTML = "⏸️ <b>Paused</b>";
                        } else {
                            docRec.start();
                            docIsPaused = false;
                            document.getElementById('doc_pause_btn').innerHTML = "⏸️ Pause";
                            document.getElementById('doc_status').innerHTML = "🟢 <b>Listening Live...</b>";
                        }
                    }

                    function stopDocRec() {
                        if (docRec) docRec.stop();
                        document.getElementById('doc_status').innerHTML = "✓ <b>Dictation Finished! Select text above or use the main Mic button above.</b>";
                        document.getElementById('doc_start_btn').style.display = "inline-block";
                        document.getElementById('doc_pause_btn').style.display = "none";
                        document.getElementById('doc_stop_btn').style.display = "none";
                    }
                    </script>
                    """, height=130)

                    c_sync1, c_sync2 = st.columns([3, 1])
                    with c_sync1:
                        sync_val = st.text_input("Paste or edit live voice transcript here if needed:", placeholder="e.g. Paracetamol 650 mg twice daily for 3 days after food", key="manual_v_sync")
                    with c_sync2:
                        st.write("")
                        st.write("")
                        if st.button("📥 Apply to Dictation"):
                            if sync_val.strip():
                                st.session_state["doc_dictation_text"] = sync_val.strip()
                                st.rerun()

                st.markdown("##### 📝 Dictation Transcript / Medication Instructions:")
                transcript = st.text_area(
                    "Review or edit instructions before processing with Groq AI:",
                    value=st.session_state["doc_dictation_text"],
                    key="doc_rx_text_input",
                    height=110
                )

                col_parse, col_tts = st.columns([3, 2])
                with col_parse:
                    sub_parse = st.button("⚡ Process Prescription with Groq AI ➔", use_container_width=True)
                with col_tts:
                    clean_t = transcript.replace('"', '').replace('\n', ' ')
                    st.components.v1.html(f"""
                    <button onclick="speakRx()" style="background: rgba(255,255,255,0.1); color: #38BDF8; border: 1px solid #38BDF8; border-radius: 8px; padding: 7px 14px; font-weight: bold; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; font-family: sans-serif; font-size: 0.85rem; width: 100%; justify-content: center;">
                        🔊 Read Dictation Aloud
                    </button>
                    <script>
                    function speakRx() {{
                        if ('speechSynthesis' in window) {{
                            window.speechSynthesis.cancel();
                            var msg = new SpeechSynthesisUtterance("{clean_t}");
                            msg.rate = 0.95;
                            window.speechSynthesis.speak(msg);
                        }}
                    }}
                    </script>
                    """, height=44)

                if sub_parse:
                    with st.spinner("Parsing medications using Groq AI..."):
                        items, err = api_post("/prescriptions/voice-dictate", json_data={
                            "patient_id": pid,
                            "visit_id": act_vid,
                            "doctor_id": "DOC-101",
                            "transcript": transcript
                        })
                        if items:
                            st.session_state["doc_draft_rx"] = items
                            st.success("✓ Dictation structured into table! Review items below.")
                        else:
                            st.error(f"❌ {err}")

                if "doc_draft_rx" in st.session_state:
                    st.markdown("#### 📋 Review & Edit Prescription Items:")
                    ed_items = st.data_editor(st.session_state["doc_draft_rx"], num_rows="dynamic", use_container_width=True)
                    if st.button("✅ Confirm & Finalize Official PDF Prescription", use_container_width=True):
                        rx_d, _ = api_post("/prescriptions", json_data={
                            "patient_id": pid,
                            "visit_id": act_vid,
                            "doctor_id": "DOC-101",
                            "items": ed_items
                        })
                        if rx_d:
                            rx_f, _ = api_post(f"/prescriptions/{rx_d['prescription_id']}/confirm", json_data={"items": ed_items})
                            if rx_f:
                                st.success(f"🎉 Prescription `{rx_f['prescription_id']}` finalized & PDF generated!")
                                api_post(f"/visits/{act_vid}/complete")
                                del st.session_state["doc_draft_rx"]
                                st.rerun()


# ── 8. Pharmacist Portal ─────────────────────────────────────────────────────
def render_pharmacist_portal():
    st.title("💊 Pharmacist Verification Dashboard")
    docs, _ = api_get("/documents/unverified")
    if docs:
        st.info(f"📋 **{len(docs)}** Prescription(s) Awaiting Verification")
        for doc in docs:
            st.markdown(f"### Document `{doc['document_id']}` (Patient: `{doc['patient_id']}`)")
            st.text_area("Extracted OCR Text:", value=doc.get("raw_text", ""), disabled=True, key=f"raw_{doc['document_id']}")
            meds = doc.get("structured_data", {}).get("medications", [])
            ed_meds = st.data_editor(meds, num_rows="dynamic", key=f"ed_{doc['document_id']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirm & Verify", key=f"v_ok_{doc['document_id']}"):
                    api_post(f"/documents/{doc['document_id']}/verify", json_data={"verified": True, "structured_data": {"medications": ed_meds}})
                    st.success("Verified!")
                    st.rerun()
            with c2:
                if st.button("❌ Reject", key=f"v_no_{doc['document_id']}"):
                    api_post(f"/documents/{doc['document_id']}/verify", json_data={"verified": False, "structured_data": {}})
                    st.rerun()
            st.divider()
    else:
        st.success("✨ No unverified documents in queue.")


# ── 9. Staff Portal ──────────────────────────────────────────────────────────
def render_staff_portal():
    st.title("🏥 Staff Triage & Outpatient Queue")
    queue, _ = api_get("/doctor/queue")
    if queue:
        for v in queue:
            prio = v.get("priority", "NORMAL")
            badge = "🔴 RED PRIORITY" if prio in ["HIGH", "EMERGENCY"] else "🟢 NORMAL"
            with st.expander(f"{badge} | Patient `{v['patient_id']}` (Visit: `{v['visit_id']}`) — {v.get('department')}"):
                st.write(f"Status: `{v.get('status')}`")
                if st.button("Complete / Clear Flag", key=f"st_clr_{v['visit_id']}"):
                    api_post(f"/visits/{v['visit_id']}/complete")
                    st.rerun()
    else:
        st.info("No active patients waiting in queue.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {str(e)}")
        st.exception(e)
