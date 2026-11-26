import streamlit as st

from src.database.db import create_subject


def render_create_subject(username: str):
    """Render the Manage Subjects header and subject creation form."""
    st.html("""
        <style>
        .st-key-teacher_subject_header {
            border-top: 1px solid #C5C6E4;
            margin-top: .75rem;
            padding-top: 1rem;
        }
        .st-key-teacher_subject_header h2 {
            max-width: 100%;
            color: #24263B;
            font: 900 clamp(1.45rem, 4vw, 2rem)/1.1 "Climate Crisis", "Arial Black", sans-serif;
            overflow-wrap: anywhere;
        }
        .st-key-teacher_portal .st-key-teacher_new_subject button {
            background: #B72270;
            color: #fff;
        }
        .st-key-teacher_portal .st-key-teacher_new_subject button:hover {
            background: #9D195D;
        }
        </style>
    """)
    with st.container(key="teacher_subject_header"):
        heading, action = st.columns(2, vertical_alignment="center")
        with heading:
            st.header("Manage Subjects", anchor=False)
        with action:
            if st.button("Create New Subject", key="teacher_new_subject", width="stretch"):
                st.session_state["teacher_subject_form_open"] = not st.session_state.get(
                    "teacher_subject_form_open", False,
                )

    if st.session_state.get("teacher_subject_form_open"):
        with st.form("teacher_create_subject"):
            code = st.text_input("Subject code", max_chars=32).strip()
            name = st.text_input("Subject name", max_chars=80).strip()
            section = st.text_input("Section", max_chars=32).strip()
            if st.form_submit_button("Save subject", type="primary", width="stretch"):
                if code and name:
                    with st.spinner("Creating subject…", show_time=True):
                        create_subject(username, code, name, section or "N/A")
                    st.session_state.pop("teacher_subject_form_open", None)
                    st.rerun()
                st.error("Enter a subject code and name.")
