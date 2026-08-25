import streamlit as st

def apply_kiosk_theme():
    st.markdown("""
        <style>
        /* Elder-Friendly Kiosk Theme */
        .main {
            background-color: #f8fafc;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }
        .stButton>button {
            width: 100%;
            height: 60px;
            font-size: 1.15rem !important;
            font-weight: 700 !important;
            border-radius: 16px !important;
            border: 2px solid #cbd5e1 !important;
            background-color: #ffffff !important;
            color: #1e293b !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
            transition: all 0.2s ease !important;
        }
        .stButton>button:hover {
            border-color: #0d9488 !important;
            color: #0d9488 !important;
            background-color: #f0fdfa !important;
            transform: translateY(-2px);
        }
        .kiosk-title {
            font-size: 2.2rem;
            font-weight: 900;
            color: #0f172a;
            letter-spacing: -0.5px;
        }
        .kiosk-badge {
            display: inline-block;
            padding: 4px 12px;
            background: #ccfbf1;
            color: #0f766e;
            border-radius: 9999px;
            font-weight: 800;
            font-size: 0.8rem;
        }
        .question-card {
            background: #ffffff;
            border: 2px solid #e2e8f0;
            border-radius: 24px;
            padding: 28px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
            margin: 16px 0;
        }
        .red-alert-card {
            background: #fff1f2;
            border: 3px solid #e11d48;
            border-radius: 24px;
            padding: 28px;
            color: #9f1239;
            box-shadow: 0 10px 25px -5px rgba(225, 29, 72, 0.2);
            margin: 16px 0;
        }
        </style>
    """, unsafe_allow_html=True)
