import re

from postgrest.exceptions import APIError
import streamlit as st

from src.database.db import get_subject_join_code, join_subject_by_code


def render_subject_share_code(username: str, subject_id: int):
    try:
        code = get_subject_join_code(username, subject_id)
    except APIError as error:
        if error.code not in {"42703", "PGRST204"}:
            raise
        st.info("Apply the Supabase subject join codes migration to enable sharing.")
        return

    if code is None:
        st.error("A share code is unavailable for this subject.")
        return

    st.write("Share this code with students so they can join this subject.")
    st.code(code, language=None)


def render_join_subject_form(student_id: int):
    with st.expander("Join a Subject"):
        with st.form("student_join_subject"):
            code = st.text_input(
                "Subject share code", placeholder="Enter the code from your teacher", max_chars=32,
            ).strip().upper()
            submitted = st.form_submit_button("Join subject", type="primary", width="stretch")
        if not submitted:
            return
        if not re.fullmatch(r"[0-9A-F]{12}", code):
            st.error("Enter the 12-character share code from your teacher.")
            return

        try:
            status = join_subject_by_code(student_id, code)
        except APIError as error:
            if error.code != "PGRST202":
                raise
            st.info("Subject sharing is unavailable until the Supabase join codes migration is applied.")
            return

        if status == "joined":
            st.success("You joined the subject. It’s now available for attendance.")
        elif status == "already_joined":
            st.info("You’re already enrolled in this subject.")
        else:
            st.error("That share code is invalid. Check it with your teacher.")
