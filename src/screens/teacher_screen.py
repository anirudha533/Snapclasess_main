from html import escape
import re

import httpx
import streamlit as st
from postgrest.exceptions import APIError

from src.UI.base_layout import PORTAL_INPUT_STYLES
from src.database.config import DatabaseConfigurationError
from src.database.db import create_teacher, teacher_login
from src.screens.components.attendance import teacher_attendance


TEACHER_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Climate+Crisis:YEAR@1979&family=Outfit:wght@400;500;600;700&display=swap');

.stApp:has(.st-key-teacher_portal) {
    background: #E0E3FF;
    color: #141522;
}
.stApp:has(.st-key-teacher_portal) header {
    visibility: hidden;
}
.stApp:has(.st-key-teacher_portal) .block-container {
    max-width: 1000px;
    padding-top: clamp(2rem, 5vh, 3.5rem);
    padding-bottom: 2rem;
}
.stApp:has(.st-key-teacher_portal) .block-container:has(.st-key-teacher_auth) {
    width: 100%;
    max-width: 700px;
    min-height: 100dvh;
    margin-inline: auto;
    padding: clamp(1.25rem, 4vw, 2rem);
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.st-key-teacher_portal {
    font-family: Outfit, sans-serif;
    color-scheme: light;
}
.st-key-teacher_portal .teacher-brand {
    display: flex;
    align-items: center;
    gap: .65rem;
}
.st-key-teacher_portal .teacher-brand-icon {
    display: grid;
    place-items: center;
    width: 5rem;
    aspect-ratio: 1;
    border: 2px solid #232335;
    border-radius: 1rem;
    background: #ffeb00;
    font-size: 2.6rem;
}
.st-key-teacher_portal .teacher-wordmark,
.st-key-teacher_portal h1 {
    font-family: "Climate Crisis", "Arial Black", sans-serif;
    font-weight: 900;
}
.st-key-teacher_portal .teacher-wordmark {
    color: #6268e9;
    font-size: clamp(1.25rem, 4vw, 2.15rem);
    line-height: .95;
}
.st-key-teacher_portal h1 {
    color: #10101a;
    font-size: clamp(1.55rem, 4vw, 2.45rem);
    line-height: 1.2;
    padding: .4rem 0 0;
}
.st-key-teacher_portal label p {
    color: #303249;
    font: 500 1rem Outfit, sans-serif;
}
.st-key-teacher_portal [data-baseweb="input"] input {
    font: 400 1rem Outfit, sans-serif;
    min-height: 2.8rem;
}
.st-key-teacher_portal [data-baseweb="input"] button {
    color: #514fc5;
    background: #e2e5ff;
    border-radius: 999px;
    margin: .2rem;
}
.st-key-teacher_portal button[kind="primary"],
.st-key-teacher_portal button[kind="secondary"],
.st-key-teacher_portal button[kind="secondaryFormSubmit"],
.st-key-teacher_portal button[kind="primaryFormSubmit"] {
    min-height: 2.9rem;
    padding-inline: 1.25rem;
    border: 0;
    border-radius: 999px;
    color: #fff;
    background: #595fda;
}
.st-key-teacher_portal button[kind^="secondary"] {
    background: #eb459e;
    color: #201020;
}
.st-key-teacher_portal button:hover {
    filter: brightness(.91);
}
.st-key-teacher_portal button:focus-visible {
    outline: 2px solid #333685;
    outline-offset: 2px;
}
.st-key-teacher_portal .teacher-divider {
    border: 0;
    border-top: 1px solid #bfc3e1;
    margin: 1rem 0 .5rem;
}
.st-key-teacher_portal .teacher-welcome {
    color: #141522;
    font: 700 1.2rem Outfit, sans-serif;
    margin-bottom: .5rem;
}
.st-key-current_teacher_tab [role="tablist"] {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
}
.st-key-teacher_portal .st-key-current_teacher_tab [role="tab"] {
    flex: 1 1 12rem;
    justify-content: center;
    min-height: 3.15rem;
    padding: .55rem 1rem;
    border: 0;
    border-radius: 999px;
    background: #09090b;
    color: #fff;
    font: 600 1rem Outfit, sans-serif;
    transition: background-color .15s ease;
}
.st-key-teacher_portal .st-key-current_teacher_tab [role="tab"]:hover {
    background: #09090b;
    color: #fff;
    filter: none;
}
.st-key-teacher_portal .st-key-current_teacher_tab [role="tab"][aria-selected="true"] {
    background: #515BDD;
}
.st-key-teacher_portal .st-key-current_teacher_tab [role="tab"][aria-selected="true"]:hover {
    background: #3D46BC;
}
.st-key-teacher_portal .teacher-credit {
    text-align: center;
    color: #222438;
    padding-top: 1.6rem;
    font: 600 .95rem Outfit, sans-serif;
}
</style>
"""


def teacher_screen():
    st.html(PORTAL_INPUT_STYLES)
    st.html(TEACHER_STYLES)
    st.session_state.setdefault("teacher_auth_mode", "register")

    identity = st.session_state.get("teacher_identity")
    with st.container(key="teacher_portal"):
        brand, navigation = st.columns([3, 2], vertical_alignment="center")
        with brand:
            st.html("""
                <div class="teacher-brand" aria-label="Snap Class">
                    <span class="teacher-brand-icon" aria-hidden="true">🎓</span>
                    <span class="teacher-wordmark" aria-hidden="true">SNAP<br>CLASS</span>
                </div>
            """)
        with navigation:
            if identity is None:
                if st.button("Go back to Home", key="teacher_home", width="stretch"):
                    st.session_state.pop("teacher_auth_mode", None)
                    st.session_state["login_type"] = None
                    st.rerun()
            else:
                name, username = identity
                st.html(f'<div class="teacher-welcome">Welcome, {escape(name)}</div>')
                if st.button("Logout", key="teacher_sign_out", icon=":material/logout:"):
                    del st.session_state["teacher_identity"]
                    st.session_state.pop("teacher_subject_form_open", None)
                    st.session_state.pop("teacher_capture_scope", None)
                    st.session_state.pop("teacher_attendance_photos", None)
                    st.session_state.pop("teacher_attendance_suggestions", None)
                    st.session_state.pop("teacher_photo_analysis", None)
                    st.session_state.pop("teacher_attendance_result", None)
                    st.session_state["teacher_auth_mode"] = "login"
                    st.rerun()

        if identity is None:
            with st.container(key="teacher_auth"):
                _teacher_auth_form()
        else:
            st.space("small")
            teacher_attendance(username)

        st.html('<div class="teacher-credit">Created with ❤️ by Anirudh</div>')


def _teacher_auth_form():
    mode = st.session_state["teacher_auth_mode"]
    registering = mode == "register"
    title = "Register your teacher profile" if registering else "Log in to your teacher profile"
    st.title(title, anchor=False)
    st.space("small")

    with st.form(f"teacher_{mode}", border=False):
        username = st.text_input(
            "Enter username", placeholder="e.g. abhishek", max_chars=33,
            help="Use 3–32 letters, numbers, or underscores. A leading @ is optional.",
        ).strip().removeprefix("@").lower()
        if registering:
            name = st.text_input(
                "Enter name", placeholder="Abhishek Sharma", max_chars=80,
            ).strip()
        else:
            name = ""
        password = st.text_input(
            "Enter password", type="password", placeholder="Enter your password",
            max_chars=128,
        )
        confirmation = ""
        if registering:
            confirmation = st.text_input(
                "Confirm password", type="password", placeholder="Confirm your password",
                max_chars=128,
            )

        st.html('<hr class="teacher-divider">')
        submit_column, switch_column = st.columns(2)
        with submit_column:
            submit = st.form_submit_button(
                "Register Now" if registering else "Log In",
                type="primary", width="stretch",
            )
        with switch_column:
            switch = st.form_submit_button(
                "Login instead" if registering else "Register instead", width="stretch",
            )

    if switch:
        st.session_state["teacher_auth_mode"] = "login" if registering else "register"
        st.rerun()
    if not submit:
        return

    try:
        if registering:
            error = _registration_error(username, name, password, confirmation)
            if error:
                st.error(error)
                return
            with st.spinner("Creating your teacher account…", show_time=True):
                if not create_teacher(username, password, name):
                    st.error("That username is already registered. Choose another or log in.")
                    return
        else:
            with st.spinner("Checking your sign-in details…", show_time=True):
                authenticated_name = teacher_login(username, password)
            if authenticated_name is None:
                st.error("The username or password is incorrect.")
                return
            name = authenticated_name
    except DatabaseConfigurationError:
        st.error("Teacher sign-in requires a configured Supabase server key.")
        return
    except (APIError, httpx.HTTPError):
        st.error("Teacher accounts are temporarily unavailable. Please try again.")
        return

    st.session_state["teacher_identity"] = (name, username)
    st.rerun()


def _registration_error(username: str, name: str, password: str, confirmation: str) -> str | None:
    if not username:
        return "Enter a username to register."
    if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
        return "Use 3–32 letters, numbers, or underscores for your username."
    if not name:
        return "Enter your name."
    if len(password) < 8:
        return "Use at least 8 characters for your password."
    if len(password.encode("utf-8")) > 72:
        return "Use a password that fits within 72 bytes."
    if password != confirmation:
        return "The passwords do not match."
    return None
