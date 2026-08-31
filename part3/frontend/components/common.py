import streamlit as st
import requests
import os

API_BASE = os.getenv("BACKEND_API_BASE", "http://localhost:8000/api/v1")

def get_headers():
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}

def api_login(username, password):
    try:
        res = requests.post(f"{API_BASE}/auth/login", json={"username": username, "password": password}, timeout=10)
        if res.status_code == 200:
            return res.json(), None
        return None, res.json().get("detail", "Invalid username or password")
    except Exception as e:
        return None, f"Could not connect to backend server ({str(e)})"

def api_get(endpoint, params=None):
    try:
        res = requests.get(f"{API_BASE}{endpoint}", headers=get_headers(), params=params, timeout=12)
        if res.status_code == 200:
            return res.json(), None
        return None, res.json().get("detail", f"Error {res.status_code}")
    except Exception as e:
        return None, str(e)

def api_get_bytes(endpoint):
    try:
        res = requests.get(f"{API_BASE}{endpoint}", headers=get_headers(), timeout=15)
        if res.status_code == 200:
            return res.content, None
        return None, f"Error {res.status_code}"
    except Exception as e:
        return None, str(e)

def api_post(endpoint, json_data=None, files=None):
    try:
        if files:
            res = requests.post(f"{API_BASE}{endpoint}", headers=get_headers(), data=json_data, files=files, timeout=20)
        else:
            res = requests.post(f"{API_BASE}{endpoint}", headers=get_headers(), json=json_data, timeout=20)
        if res.status_code in [200, 201]:
            return res.json(), None
        return None, res.json().get("detail", f"Error {res.status_code}")
    except Exception as e:
        return None, str(e)

def apply_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    /* Global Typography & Safe Theme */
    .stApp {
        font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background: linear-gradient(180deg, #0B1120 0%, #0F172A 100%) !important;
    }
    .stApp, .stApp p, .stApp span, .stApp div, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #F1F5F9;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1200px !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #070D1E !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.08) !important;
    }

    /* Premium Cards & Containers */
    .med-card {
        background: rgba(30, 41, 59, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3) !important;
        margin-bottom: 16px !important;
        transition: transform 0.2s ease, border-color 0.2s ease !important;
    }
    .med-card:hover {
        border-color: rgba(14, 165, 233, 0.3) !important;
        transform: translateY(-2px) !important;
    }

    /* Hero Banner Card */
    .hero-banner {
        background: linear-gradient(135deg, rgba(13, 148, 136, 0.25) 0%, rgba(14, 165, 233, 0.15) 100%) !important;
        border: 1px solid rgba(20, 184, 166, 0.3) !important;
        border-radius: 20px !important;
        padding: 24px 28px !important;
        margin-bottom: 24px !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 0.55rem 1.25rem !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%) !important;
        color: #F8FAFC !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    .stButton > button:hover {
        border-color: #0EA5E9 !important;
        background: linear-gradient(180deg, #0284C7 0%, #0369A1 100%) !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3) !important;
    }
    .stButton > button:active {
        transform: translateY(0px) !important;
    }

    /* Primary Submit Buttons */
    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #0D9488 0%, #0284C7 100%) !important;
        border: none !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(13, 148, 136, 0.4) !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        background: linear-gradient(135deg, #0F766E 0%, #0369A1 100%) !important;
        box-shadow: 0 6px 20px rgba(13, 148, 136, 0.6) !important;
    }

    /* Input Fields */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stTextArea > div > div > textarea {
        background-color: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        color: #F8FAFC !important;
        font-size: 0.95rem !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #0EA5E9 !important;
        box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.2) !important;
    }

    /* Tabs Customization */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: rgba(15, 23, 42, 0.6) !important;
        padding: 6px 8px !important;
        border-radius: 14px !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        margin-bottom: 20px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px !important;
        padding: 8px 18px !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        color: #94A3B8 !important;
        border: none !important;
        background-color: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(13, 148, 136, 0.3) 0%, rgba(14, 165, 233, 0.25) 100%) !important;
        color: #38BDF8 !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
    }

    /* Progress Bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #0D9488 0%, #0EA5E9 100%) !important;
        border-radius: 9999px !important;
    }

    /* Badges */
    .badge-red {
        background-color: rgba(239, 68, 68, 0.2);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-normal {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.8rem;
        display: inline-block;
    }
    .badge-draft {
        background-color: rgba(245, 158, 11, 0.2);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.8rem;
        display: inline-block;
    }

    /* RAG & Note Boxes */
    .rag-box {
        background-color: rgba(30, 41, 59, 0.7);
        border-left: 4px solid #38BDF8;
        padding: 16px 20px;
        border-radius: 10px;
        margin-top: 12px;
        margin-bottom: 12px;
    }

    /* Quick Question Card */
    .question-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%) !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 18px !important;
        padding: 24px 28px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3) !important;
    }
    </style>
    """, unsafe_allow_html=True)
