from io import BytesIO
import re
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from postgrest.exceptions import APIError
import segno
import streamlit as st

from src.database.config import DatabaseConfigurationError
from src.database.db import get_subject_join_code, join_subject_by_code


def _subject_join_url(app_url: str, code: str) -> str:
    url = urlsplit(app_url)
    return urlunsplit((url.scheme, url.netloc, url.path or "/", urlencode({"join-code": code}), ""))


@st.dialog("Share Class Link", width="medium")
def share_subject_dialog(username: str, subject_id: int, subject_name: str):
    st.html("""
        <style>
        [role="dialog"]:has(.st-key-subject_share_dialog) {
            background: #fff;
            color: #24263B;
        }
        [role="dialog"]:has(.st-key-subject_share_dialog) :is(h2, h3, button) { color: #24263B; }
        .st-key-subject_share_dialog pre {
            background: #F2F0FC;
            color: #29254F;
        }
        </style>
    """)
    with st.container(key="subject_share_dialog"):
        try:
            with st.spinner("Preparing the share link and QR code…", show_time=True):
                code = get_subject_join_code(username, subject_id)
        except APIError as error:
            if error.code in {"42703", "PGRST204"}:
                st.info("Run the Supabase subject join codes migration to generate share codes.")
            else:
                st.error("Could not load the share code. Please try again.")
            return
        except (httpx.HTTPError, DatabaseConfigurationError):
            st.error("Could not connect to the subject database.")
            return

        if not code:
            st.error("A share code is unavailable for this subject.")
            return

        st.text(subject_name)
        join_url = _subject_join_url(st.context.url or "http://localhost:8501/", code)
        link, qr = st.columns(2)
        with link:
            st.subheader("Copy Link", anchor=False)
            st.code(join_url, language=None, wrap_lines=True)
            st.caption("Subject share code")
            st.code(code, language=None)
        with qr:
            st.subheader("Scan to Join", anchor=False)
            image = BytesIO()
            segno.make_qr(join_url).save(image, kind="png", scale=7, border=4)
            st.image(image.getvalue(), width="stretch", alt="QR code to join this subject.")


def render_join_subject_form(student_id: int):
    shared_code = st.query_params.get("join-code", "").strip().upper()[:32]
    with st.container(border=True):
        with st.form("student_join_subject"):
            code = st.text_input(
                "Subject share code", value=shared_code,
                placeholder="Enter the code from your teacher", max_chars=32,
            ).strip().upper()
            submitted = st.form_submit_button("Join subject", type="primary", width="stretch")
        if not submitted:
            return
        if not re.fullmatch(r"[0-9A-F]{12}", code):
            st.error("Enter the 12-character share code from your teacher.")
            return

        try:
            with st.spinner("Joining subject…", show_time=True):
                status = join_subject_by_code(student_id, code)
        except APIError as error:
            if error.code != "PGRST202":
                raise
            st.info("Subject sharing is unavailable until the Supabase join codes migration is applied.")
            return

        if status in {"joined", "already_joined"} and shared_code == code:
            del st.query_params["join-code"]

        if status == "joined":
            st.success("You joined the subject. It’s now available for attendance.")
        elif status == "already_joined":
            st.info("You’re already enrolled in this subject.")
        else:
            st.error("That share code is invalid. Check it with your teacher.")
