import streamlit as st
from components.common import api_get, api_post

def render_staff_view():
    st.title("🏥 Staff Triage & Priority Queue Dashboard")

    queue, err = api_get("/doctor/queue")

    if queue:
        col_red, col_norm = st.columns(2)

        with col_red:
            st.markdown("### 🚨 HIGH / RED PRIORITY QUEUE")
            red_items = [v for v in queue if v["priority"] in ["HIGH", "EMERGENCY"]]
            if red_items:
                for v in red_items:
                    with st.expander(f"🔴 `{v['patient_id']}` (Visit: {v['visit_id']})"):
                        st.write(f"**Department:** {v['department']}")
                        st.write(f"**Status:** {v['status']}")
                        if st.button("Complete / Clear Priority Flag", key=f"clr_{v['visit_id']}"):
                            api_post(f"/visits/{v['visit_id']}/complete")
                            st.rerun()
            else:
                st.info("No RED priority patients in queue.")

        with col_norm:
            st.markdown("### 🟢 NORMAL PRIORITY QUEUE")
            norm_items = [v for v in queue if v["priority"] not in ["HIGH", "EMERGENCY"]]
            if norm_items:
                for v in norm_items:
                    st.write(f"🟢 `{v['patient_id']}` | Visit: `{v['visit_id']}` | Department: {v['department']} | Status: {v['status']}")
            else:
                st.info("No normal priority patients waiting.")
    else:
        st.info("No active patients in queue today.")
