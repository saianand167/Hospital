import streamlit as st
from app.services.auth_service import AuthService
from app.models.user import UserRegister, UserLogin

def render_login_screen():
    st.markdown("""
        <div style="text-align:center; padding: 20px 0 10px 0;">
            <div style="font-size: 3rem;">🏥</div>
            <h1 style="color:#0f172a; margin:0; font-size:2.2rem; font-weight:900;">MediKiosk</h1>
            <p style="color:#64748b; font-size:1rem; margin-top:4px;">
                Multilingual Outpatient Clinical History & Intake System
            </p>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔑 Patient Login", "📝 Register New Patient"])

    with tab_login:
        st.markdown("##### Sign in to your patient account")
        with st.form("login_form"):
            username_or_email = st.text_input("Patient ID / Username / Email", placeholder="e.g. USR-000001, saianand, or sai@example.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Sign In ➔", use_container_width=True)

            if submit_login:
                if not username_or_email or not password:
                    st.error("Please enter both Patient ID / Username / Email and Password.")
                else:
                    user = AuthService.login(UserLogin(username_or_email=username_or_email.strip(), password=password))
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user.model_dump()
                        st.session_state.current_screen = "dashboard"
                        st.success(f"Welcome, {user.full_name}!")
                        st.rerun()
                    else:
                        st.error("Invalid Patient ID/Username or password.")

    with tab_register:
        st.markdown("##### Create a new patient registration")
        with st.form("register_form"):
            full_name = st.text_input("Full Name", placeholder="e.g. Sai Anand")
            col_u, col_e = st.columns(2)
            with col_u:
                username = st.text_input("Username", placeholder="e.g. saianand")
            with col_e:
                email = st.text_input("Email", placeholder="e.g. sai@example.com")
            
            col_p, col_ph = st.columns(2)
            with col_p:
                password = st.text_input("Password", type="password", placeholder="••••••••")
            with col_ph:
                phone = st.text_input("Phone Number (Optional)", placeholder="e.g. 9876543210")
                
            pref_lang = st.selectbox("Preferred Language", [("en", "English"), ("te", "తెలుగు (Telugu)"), ("or", "ଓଡ଼ିଆ (Odia)"), ("hi", "हिन्दी (Hindi)")], format_func=lambda x: x[1])
            submit_reg = st.form_submit_button("Register Patient Account ➔", use_container_width=True)

            if submit_reg:
                if not full_name or not username or not email or not password:
                    st.error("Please fill in all required fields (Full Name, Username, Email, Password).")
                else:
                    try:
                        new_user = AuthService.register(UserRegister(
                            full_name=full_name.strip(),
                            username=username.strip(),
                            email=email.strip(),
                            password=password,
                            phone=phone.strip() if phone else None,
                            preferred_language=pref_lang[0]
                        ))
                        st.session_state.authenticated = True
                        st.session_state.user = new_user.model_dump()
                        st.session_state.current_screen = "dashboard"
                        st.success(f"Registration successful! Your Patient ID is **{new_user.user_id}**.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
