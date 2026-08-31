"""
SIH26047 — MediKiosk Unified Web and Kiosk Application
Multi-role: Patient Intake, Document OCR, Doctor Panel, Pharmacist Verification & Staff Queue
"""

import sys
import os
import traceback
from pathlib import Path
import streamlit as st
import requests

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

def api_get(endpoint, params=None):
    try:
        res = requests.get(
            f"{API_BASE}{endpoint}",
            headers=get_headers(),
            params=params,
            timeout=12
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
                u_in = st.text_input("Username", placeholder="e.g. patient1, doctor1, or custom username")
            with col2:
                p_in = st.text_input("Password", type="password", placeholder="••••••••")
            
            sub = st.form_submit_button("Sign In ➔", use_container_width=True)
            if sub:
                if not u_in or not p_in:
                    st.error("Please enter both username and password.")
                else:
                    res, err = api_login(u_in, p_in)
                    if res:
                        st.session_state["token"] = res["access_token"]
                        st.session_state["role"] = res["role"]
                        st.session_state["username"] = res["username"]
                        st.session_state["user_data"] = res
                        st.success("Signed in successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")

    with tab_reg:
        st.markdown("### 📝 Register New Patient Account")
        st.caption("A unique Patient ID (`PAT-XXXXXX`) will be generated automatically.")
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
                reg_lang = st.selectbox("Language", ["English", "Telugu / తెలుగు", "Hindi / हिन्दी"])

            sub_reg = st.form_submit_button("Create Patient Account ➔", use_container_width=True)
            if sub_reg:
                if not reg_name or not reg_user or not reg_pwd:
                    st.error("Full Name, Username, and Password are required.")
                else:
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
                        st.success(f"🎉 Registered successfully! Assigned ID: **{res['patient_id']}**")
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")


# ── 6. Patient Portal ────────────────────────────────────────────────────────
def render_patient_portal():
    u_data = st.session_state.get("user_data", {})
    patient_id = u_data.get("patient_id", "PAT-000001")
    full_name = u_data.get("full_name") or u_data.get("username", "Patient")

    st.markdown(f"""
    <div class="hero-banner">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <span style="font-size:0.85rem; font-weight:700; color:#38BDF8;">PATIENT OUTPATIENT PORTAL</span>
                <h1 style="margin:4px 0 6px 0; color:#FFFFFF; font-size:1.9rem;">Welcome, {full_name}</h1>
                <span class="badge-normal">{patient_id}</span>
            </div>
            <div style="font-size:2.8rem;">🏥</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    t1, t2, t3, t4 = st.tabs([
        "🩺 Clinical Intake & Symptoms", 
        "📑 Medical Document Upload", 
        "📋 Visit History", 
        "💊 My Prescriptions"
    ])

    # Tab 1: Clinical Intake
    with t1:
        st.markdown("### 🩺 Multilingual Clinical Intake")
        visits, _ = api_get(f"/patients/{patient_id}/visits")
        active_v = visits[0] if visits and visits[0].get("status") != "COMPLETED" else None

        if not active_v:
            st.markdown("#### Select your primary symptom to begin today's consultation:")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("💔 Chest Pain", use_container_width=True):
                    _start_visit_intake(patient_id, "Cardiology", "Chest pain for 3 days")
            with c2:
                if st.button("🌡️ Fever & Chills", use_container_width=True):
                    _start_visit_intake(patient_id, "General Medicine", "High fever with chills and body ache")
            with c3:
                if st.button("🤢 Stomach Pain", use_container_width=True):
                    _start_visit_intake(patient_id, "Gastroenterology", "Severe abdominal pain")

            c4, c5 = st.columns(2)
            with c4:
                if st.button("😮‍💨 Shortness of Breath / Cough", use_container_width=True):
                    _start_visit_intake(patient_id, "Pulmonology", "Difficulty breathing with cough")
            with c5:
                if st.button("🩺 General Outpatient Checkup", use_container_width=True):
                    _start_visit_intake(patient_id, "General Medicine", "General fatigue and checkup")

        else:
            vid = active_v["visit_id"]
            st.info(f"📋 **Active Visit:** `{vid}` | Department: **{active_v.get('department')}** | Status: `{active_v.get('status')}`")

            s_key = f"session_data_{vid}"
            if s_key not in st.session_state:
                res, _ = api_post("/history/session/start", json_data={
                    "patient_id": patient_id,
                    "visit_id": vid,
                    "language": "en",
                    "initial_complaint": "Outpatient intake"
                })
                if res:
                    st.session_state[s_key] = res

            sess = st.session_state.get(s_key, {})
            h_data = sess.get("history", {})
            next_q = sess.get("next_question")
            is_done = sess.get("is_completed", False)
            triage = h_data.get("triage", {})

            if triage.get("flag") == "RED":
                st.error("🚨 **RED-FLAG ALERT DETECTED**: Priority symptoms detected. Nursing staff flagged.")

            if is_done or not next_q:
                st.success("🎉 **Clinical Intake Completed!** Your structured case-taking report is ready for the doctor.")
                if st.button("🔄 Redo Intake"):
                    res, _ = api_post("/history/session/start", json_data={
                        "patient_id": patient_id,
                        "visit_id": vid,
                        "language": "en",
                        "initial_complaint": "Restart intake"
                    })
                    if res:
                        st.session_state[s_key] = res
                        st.rerun()
            else:
                curr_n = next_q.get("progress_current", 1)
                tot_n = max(next_q.get("progress_total", 6), 1)
                st.progress(min(curr_n / tot_n, 1.0))
                
                # Question Display with Audio Bot Reader
                prompt_text = next_q.get('prompt_text', '')
                
                col_q_text, col_q_audio = st.columns([4, 1])
                with col_q_text:
                    st.markdown(f"#### ❓ Question {curr_n} of {tot_n}: **{prompt_text}**")
                with col_q_audio:
                    # Web Speech API TTS button for natural bot voice reading
                    st.components.v1.html(f"""
                    <div style="text-align: right;">
                        <button onclick="speakText()" style="background: linear-gradient(135deg, #0284C7 0%, #0D9488 100%); color: white; border: none; border-radius: 8px; padding: 6px 12px; font-weight: bold; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; font-family: sans-serif; font-size: 0.85rem;">
                            🔊 Listen to Bot
                        </button>
                    </div>
                    <script>
                    function speakText() {{
                        if ('speechSynthesis' in window) {{
                            window.speechSynthesis.cancel();
                            var msg = new SpeechSynthesisUtterance("{prompt_text.replace('"', '')}");
                            msg.rate = 0.95;
                            msg.pitch = 1.0;
                            window.speechSynthesis.speak(msg);
                        }}
                    }}
                    </script>
                    """, height=42)

                f_name = next_q.get("field_name")
                i_type = next_q.get("input_type")
                options = next_q.get("options", [])
                ans = None
                touch = None

                # ── MULTIMODAL INPUT 1: MICROPHONE VOICE INPUT (Click Only - No Hover Trigger) ──
                st.markdown("""
                <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(14, 165, 233, 0.25); border-radius: 12px; padding: 14px 18px; margin: 10px 0 16px 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <span style="font-weight: 700; color: #38BDF8; font-size: 0.95rem;">🎙️ CLICK-TO-SPEAK VOICE ANSWER</span>
                            <div style="font-size: 0.8rem; color: #94A3B8;">Click buttons below to Start / Pause / Resume / Stop. Transcribed text appears live on screen.</div>
                        </div>
                        <span class="badge-normal" style="font-size: 0.75rem;">Whisper Large V3 Turbo & Web Speech</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Real-time Live Web Speech Component (Click to Start / Pause / Resume / Stop)
                st.components.v1.html(f"""
                <div style="font-family: sans-serif; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 12px 16px;">
                    <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap;">
                        <button id="p_start_btn" onclick="startRec()" style="background: #0284C7; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; font-size: 0.85rem;">
                            🔴 Start Recording
                        </button>
                        <button id="p_pause_btn" onclick="togglePause()" style="background: #475569; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; font-size: 0.85rem; display: none;">
                            ⏸️ Pause
                        </button>
                        <button id="p_stop_btn" onclick="stopRec()" style="background: #DC2626; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; font-size: 0.85rem; display: none;">
                            ⏹️ Stop & Copy
                        </button>
                        <span id="p_status" style="color: #94A3B8; font-size: 0.85rem; margin-left: 8px;">Status: Idle (Click Start)</span>
                    </div>
                    <div id="p_live_box" style="min-height: 38px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; padding: 8px 12px; color: #38BDF8; font-size: 0.95rem; font-weight: 500;">
                        <i>Click "Start Recording" and speak your answer...</i>
                    </div>
                </div>
                <script>
                var recognition = null;
                var isPaused = false;
                var finalTranscript = "";

                if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                    var SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                    recognition = new SpeechRec();
                    recognition.continuous = true;
                    recognition.interimResults = true;
                    recognition.lang = "en-IN";

                    recognition.onresult = function(event) {{
                        var interim = "";
                        for (var i = event.resultIndex; i < event.results.length; ++i) {{
                            if (event.results[i].isFinal) {{
                                finalTranscript += event.results[i][0].transcript + " ";
                            }} else {{
                                interim += event.results[i][0].transcript;
                            }}
                        }}
                        document.getElementById('p_live_box').innerHTML = "<b>🗣️ Live:</b> " + (finalTranscript + interim);
                    }};

                    recognition.onerror = function(event) {{
                        document.getElementById('p_status').innerHTML = "⚠️ Status: " + event.error;
                    }};
                }}

                function startRec() {{
                    if (!recognition) {{
                        alert("Speech recognition not supported in this browser. Please type or use audio file upload.");
                        return;
                    }}
                    finalTranscript = "";
                    recognition.start();
                    document.getElementById('p_status').innerHTML = "🟢 <b>Listening Live...</b>";
                    document.getElementById('p_start_btn').style.display = "none";
                    document.getElementById('p_pause_btn').style.display = "inline-block";
                    document.getElementById('p_stop_btn').style.display = "inline-block";
                    document.getElementById('p_live_box').innerHTML = "<i>Listening to your voice...</i>";
                }}

                function togglePause() {{
                    if (!isPaused) {{
                        recognition.stop();
                        isPaused = true;
                        document.getElementById('p_pause_btn').innerHTML = "▶️ Resume";
                        document.getElementById('p_status').innerHTML = "⏸️ <b>Paused</b>";
                    }} else {{
                        recognition.start();
                        isPaused = false;
                        document.getElementById('p_pause_btn').innerHTML = "⏸️ Pause";
                        document.getElementById('p_status').innerHTML = "🟢 <b>Listening Live...</b>";
                    }}
                }}

                function stopRec() {{
                    if (recognition) recognition.stop();
                    document.getElementById('p_status').innerHTML = "✓ <b>Done! Transcribed below.</b>";
                    document.getElementById('p_start_btn').style.display = "inline-block";
                    document.getElementById('p_pause_btn').style.display = "none";
                    document.getElementById('p_stop_btn').style.display = "none";
                }}
                </script>
                """, height=125)

                try:
                    from audio_recorder_streamlit import audio_recorder
                    col_mic_rec, col_mic_info = st.columns([1, 3])
                    with col_mic_rec:
                        rec_audio = audio_recorder(
                            text="Click to record Audio File:",
                            recording_color="#e63946",
                            neutral_color="#0284c7",
                            icon_size="2x",
                            key=f"rec_p_{f_name}_{curr_n}"
                        )
                    with col_mic_info:
                        if rec_audio:
                            with st.spinner("⚡ Transcribing via Groq Whisper-large-v3-turbo (<300ms)..."):
                                files = {"audio": ("response.wav", rec_audio, "audio/wav")}
                                res_asr, err_asr = api_post("/voice/transcribe", files=files, json_data={"model_quality": "fast"})
                                if res_asr and res_asr.get("transcript"):
                                    transcribed_text = res_asr["transcript"].strip()
                                    st.markdown(f"""
                                    <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 10px; padding: 8px 12px;">
                                        <div style="font-size: 0.75rem; color: #34D399; font-weight: 700;">🗣️ GROQ WHISPER TRANSCRIBED:</div>
                                        <div style="font-size: 0.95rem; color: #FFFFFF; font-weight: 600;">"{transcribed_text}"</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    ans = transcribed_text
                except Exception:
                    pass

                # ── MULTIMODAL INPUT 2: TOUCH CHIPS ──
                if options:
                    st.markdown("##### 🔘 Or Select an Option:")
                    cols = st.columns(min(len(options), 3))
                    for i, opt in enumerate(options):
                        with cols[i % 3]:
                            if st.button(f"🔘 {opt['label']}", key=f"opt_{f_name}_{opt['value']}", use_container_width=True):
                                ans, touch = opt["label"], opt["value"]

                elif i_type == "number" or "duration" in str(f_name):
                    st.markdown("##### ⏱️ Or Select Quick Duration:")
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
                    st.markdown("##### 🔘 Or Choose Yes / No:")
                    cy, cn = st.columns(2)
                    with cy:
                        if st.button("✅ YES", key=f"y_{f_name}", use_container_width=True):
                            ans, touch = "YES", "true"
                    with cn:
                        if st.button("❌ NO", key=f"n_{f_name}", use_container_width=True):
                            ans, touch = "NO", "false"

                elif i_type == "scale":
                    st.markdown("##### 📊 Rate Severity Scale:")
                    sc = st.slider("Rate Severity (0=None, 10=Severe):", 0, 10, 5, key=f"sc_{f_name}")
                    if st.button("Confirm Rating ➔", key=f"sc_btn_{f_name}"):
                        ans, touch = str(sc), str(sc)

                # ── MULTIMODAL INPUT 3: TEXT INPUT ──
                with st.form(f"txt_form_{f_name}"):
                    txt = st.text_input("Or type your response:", key=f"txt_in_{f_name}")
                    if st.form_submit_button("Submit Response ➔"):
                        if txt.strip():
                            ans = txt.strip()

                if ans:
                    m_res, err = api_post(f"/history/session/{vid}/message", json_data={
                        "patient_message": ans,
                        "target_field": f_name,
                        "is_touch_input": touch is not None,
                        "touch_value": touch,
                        "language": "en"
                    })
                    if m_res:
                        st.session_state[s_key] = m_res
                        st.rerun()
                    else:
                        st.error(f"❌ {err}")

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
        st.markdown("### 📋 Previous Consultations")
        all_v, _ = api_get(f"/patients/{patient_id}/visits")
        if all_v:
            for v in all_v:
                with st.expander(f"🗓️ Visit {v['visit_id']} ({v.get('visit_date','')[:10]}) — {v.get('department')}"):
                    st.write(f"Status: `{v.get('status')}` | Priority: `{v.get('priority')}`")
                    ch, _ = api_get(f"/history/{v['visit_id']}")
                    if ch:
                        st.json(ch.get("history_json", {}))
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


def _start_visit_intake(patient_id, department, complaint):
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
            "language": "en",
            "initial_complaint": complaint
        })
        if res:
            st.session_state[f"session_data_{vid}"] = res
        st.rerun()
    else:
        st.error(f"❌ Error creating visit: {err}")


# ── 7. Doctor Portal ─────────────────────────────────────────────────────────
def render_doctor_portal():
    st.title("👨‍⚕️ Doctor Panel — Outpatient Clinical Consultation")
    c_q, c_m = st.columns([1, 2])

    with c_q:
        st.markdown("### Today's Queue")
        queue, _ = api_get("/doctor/queue")
        if queue:
            for v in queue:
                p_id = v["patient_id"]
                v_id = v["visit_id"]
                badge = "🔴 RED" if v.get("priority") in ["HIGH", "EMERGENCY"] else "🟢 NORMAL"
                if st.button(f"{badge} | {p_id} ({v_id})", key=f"q_btn_{v_id}"):
                    st.session_state["doc_pid"] = p_id
                    st.session_state["doc_vid"] = v_id

        st.divider()
        pid_in = st.text_input("Lookup Patient ID:", value=st.session_state.get("doc_pid", "PAT-000001"))
        if st.button("Open Record"):
            st.session_state["doc_pid"] = pid_in
            st.session_state["doc_vid"] = None

    with c_m:
        pid = st.session_state.get("doc_pid", "PAT-000001")
        vid = st.session_state.get("doc_vid")
        p_data, _ = api_get(f"/patients/{pid}")

        if not p_data:
            st.warning(f"Patient record `{pid}` not found.")
            return

        st.markdown(f"## Patient Consultation: `{pid}` — **{p_data.get('name')}**")
        st.write(f"**Gender:** {p_data.get('gender')} | **Language:** {p_data.get('preferred_language')}")

        d_t1, d_t2, d_t3 = st.tabs(["🤖 Groq AI Summary", "📜 Past History & Documents", "🎤 Prescription Order"])

        with d_t1:
            st.markdown("### 🤖 Groq AI Clinical Briefing")
            st.caption("🔒 Non-diagnostic. Grounded strictly in patient records. Doctor confirmation required before any action.")
            
            # Show which model is being used
            st.markdown("""
            <div style="background:rgba(14,165,233,0.08); border:1px solid rgba(14,165,233,0.2); border-radius:10px; padding:8px 14px; margin-bottom:14px; font-size:0.85rem; color:#38BDF8;">
                ⚡ Powered by <b>Groq AI (openai/gpt-oss-120b)</b> — Responses grounded in EMR data only
            </div>
            """, unsafe_allow_html=True)

            with st.spinner("🔄 Generating clinical briefing via Groq AI..."):
                summary, err = api_get(f"/doctor/patients/{pid}/summary", params={"visit_id": vid} if vid else None)

            if summary:
                # Triage Badge
                flag = summary.get("current_triage_flag", "NORMAL")
                badge_color = "#EF4444" if flag in ["RED", "HIGH", "EMERGENCY"] else "#10B981"
                st.markdown(f"""
                <div style="background:rgba({('239,68,68' if flag in ['RED','HIGH','EMERGENCY'] else '16,185,129')},0.12); border:1px solid {badge_color}; border-radius:12px; padding:12px 18px; margin-bottom:16px; display:flex; align-items:center; gap:10px;">
                    <span style="font-size:1.5rem;">{'🚨' if flag in ['RED','HIGH','EMERGENCY'] else '✅'}</span>
                    <div>
                        <span style="font-weight:800; color:{badge_color}; font-size:1rem;">TRIAGE FLAG: {flag}</span>
                        <div style="color:#94A3B8; font-size:0.85rem;">Based on reported symptoms and automated case-taking questionnaire</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Summary cards
                sections = [
                    ("🩺 Chief Complaint", "chief_complaint"),
                    ("📖 History of Present Illness", "hpi"),
                    ("📋 Relevant Past Medical History", "relevant_past_history"),
                    ("🧪 Previous Investigations / Lab Findings", "relevant_previous_investigations"),
                    ("💉 Previous Treatments", "previous_treatments"),
                    ("👨‍👩‍👧 Family & Personal History", "family_personal_history"),
                ]

                for label, key in sections:
                    val = summary.get(key, "")
                    if val and val.lower() not in ("none", "null", "n/a", "not recorded", ""):
                        st.markdown(f"""
                        <div class="med-card" style="margin-bottom: 10px;">
                            <div style="font-size:0.8rem; font-weight:700; color:#38BDF8; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;">{label}</div>
                            <div style="color:#E2E8F0; line-height:1.6;">{val}</div>
                        </div>
                        """, unsafe_allow_html=True)

                # Medications & Allergies row
                meds = summary.get("medications", [])
                allergies = summary.get("allergies", [])
                col_m, col_a = st.columns(2)
                with col_m:
                    st.markdown(f"""
                    <div class="med-card">
                        <div style="font-size:0.8rem; font-weight:700; color:#38BDF8; text-transform:uppercase; margin-bottom:8px;">💊 Current / Prior Medications</div>
                        {''.join(f'<div style="color:#E2E8F0;">• {m}</div>' for m in meds) if meds else '<div style="color:#64748B;">None reported</div>'}
                    </div>
                    """, unsafe_allow_html=True)
                with col_a:
                    st.markdown(f"""
                    <div class="med-card">
                        <div style="font-size:0.8rem; font-weight:700; color:#F87171; text-transform:uppercase; margin-bottom:8px;">⚠️ Known Allergies</div>
                        {''.join(f'<div style="color:#FCA5A5;">• {a}</div>' for a in allergies) if allergies else '<div style="color:#64748B;">No known allergies</div>'}
                    </div>
                    """, unsafe_allow_html=True)

                # Sources footer
                sources = summary.get("sources", [])
                if sources:
                    with st.expander("📎 Grounding Sources (EMR Records Used)"):
                        for src in sources:
                            st.write(f"• `{src.get('source_id')}` — {src.get('type', src.get('source_type', ''))}")
            else:
                # Determine if it's an auth issue or missing history
                if err and ("403" in str(err) or "permitted" in str(err)):
                    st.error("🔒 **Access Denied**: Only Doctor and Staff roles can view patient summaries.")
                elif err and "No history" in str(err):
                    st.info("ℹ️ No clinical history recorded yet for this patient. Ask the patient to complete the clinical intake questionnaire first.")
                else:
                    st.warning(f"⚠️ Could not load Groq AI summary: **{err}**\n\nThis may be because no clinical intake has been completed yet for this visit.")

        with d_t2:
            v_all, _ = api_get(f"/patients/{pid}/visits")
            if v_all:
                for v in v_all:
                    with st.expander(f"Visit {v['visit_id']} ({v.get('visit_date','')[:10]})"):
                        ch, _ = api_get(f"/history/{v['visit_id']}")
                        if ch:
                            st.json(ch.get("history_json", {}))
            else:
                st.info("No previous visits.")

        with d_t3:
            st.markdown("### 🎤 Voice / Text Prescription Generator")
            st.caption("Dictate or type prescription instructions -> Transcribe via Groq Whisper -> Parse with Groq AI -> Finalize PDF")
            v_list, _ = api_get(f"/patients/{pid}/visits")
            act_vid = vid or (v_list[0]["visit_id"] if v_list else None)

            if not act_vid:
                st.warning("No active visit found for this patient.")
            else:
                # ── Doctor Voice Dictation Controller (Click Only - No Hover Trigger) ──
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

                # Live In-Browser Speech Recognition & Manual Paste Sync
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
                        sync_val = st.text_input("Paste or edit live voice transcript here if needed:", placeholder="e.g. hi only give Paracetamol 200 mg 2 days after eating Mills", key="manual_v_sync")
                    with c_sync2:
                        st.write("")
                        st.write("")
                        if st.form_submit_button if False else st.button("📥 Apply to Dictation"):
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
                    # TTS Playback of prescription text
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
