from html import escape
import re

import httpx
from postgrest.exceptions import APIError
import streamlit as st

from src.UI.base_layout import PORTAL_INPUT_STYLES
from src.database.config import DatabaseConfigurationError
from src.database.db import create_student, get_student_profile, get_student_subjects, record_attendance
from src.screens.components.subject_sharing.forms import render_join_subject_form
from src.voice_pipelines.recognition import VoiceCaptureError, get_voice_embedding, identify_speaker
from src.face_pipelines.recognition import FaceCaptureError, face_matches, get_face_embedding


def student_screen():
    st.html(PORTAL_INPUT_STYLES)
    st.html("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Climate+Crisis:YEAR@1979&family=Outfit:wght@400;500;600;700&display=swap');
        .stApp:has(.st-key-student_portal) { background: #E0E3FF; color: #141522; }
        .stApp:has(.st-key-student_portal) header {
            background-color: #E0E3FF;
        }
        .stApp:has(.st-key-student_portal) .block-container {
            max-width: 700px;
            margin-inline: auto;
            padding-top: 5.25rem;
        }
        .st-key-student_portal .student-brand {
            container-type: inline-size;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: .65rem;
            color: #595FDA;
        }
        .st-key-student_portal .student-wordmark {
            font: 900 2rem/.95 "Climate Crisis", "Arial Black", sans-serif;
            font-size: clamp(1rem, 8cqi, 2.75rem);
        }
        .st-key-student_portal .student-brand-icon {
            display: grid;
            place-items: center;
            flex: 0 0 auto;
            width: clamp(2.5rem, 20cqi, 4.5rem);
            aspect-ratio: 1;
            border: 2px solid #232335;
            border-radius: 1rem;
            background: #ffeb00;
            font: 2rem/1 sans-serif;
        }
        .st-key-student_portal h1 {
            font: 900 clamp(1.65rem, 4vw, 2.3rem)/1.2 "Climate Crisis", "Arial Black", sans-serif;
        }
        .st-key-student_portal :is(label p, button p) { font-family: Outfit, sans-serif; }
        .st-key-student_portal :is(h1, h2, label p) { color: #141522; }
        .st-key-student_home button {
            background: #EB459E;
            color: #201020;
            border: 0;
            border-radius: 999px;
        }
        .st-key-student_portal .student-welcome {
            color: #141522;
            font: 600 1.125rem Outfit, sans-serif;
            margin-bottom: .65rem;
        }
        .st-key-student_portal .student-id {
            display: inline-block;
            color: #27205F;
            background: #F5F3FF;
            border: 1px solid #B9B1E9;
            border-radius: .5rem;
            padding: .45rem .8rem;
            font: 700 1.125rem Outfit, sans-serif;
        }
        .st-key-student_sign_out button {
            background: #4438B7;
            color: #FFFFFF;
            border: 0;
            border-radius: 999px;
            padding-inline: 1.25rem;
        }
        .st-key-student_sign_out button:hover { background: #392E9C; }
        .st-key-student_sign_out button:focus-visible {
            outline: 2px solid #392E9C;
            outline-offset: 3px;
        }
        .st-key-student_portal button[kind="primaryFormSubmit"] {
            background: #595FDA;
            color: white;
            border-radius: 999px;
        }
        </style>
    """)
    with st.container(key="student_portal"):
        brand, back = st.columns([2, 1], vertical_alignment="center")
        with brand:
            st.html('''
                <div class="student-brand">
                    <span class="student-brand-icon" aria-hidden="true">🎓</span>
                    <span class="student-wordmark">SNAP<br>CLASS</span>
                </div>
            ''')
        with back:
            if st.button("Go back to Home", key="student_home", width="stretch"):
                st.session_state.pop("student_identity", None)
                st.session_state["login_type"] = None
                st.rerun()

        student = st.session_state.get("student_identity")
        try:
            if student is None:
                mode = st.radio("Student account", ("Sign in", "Register new profile"), horizontal=True)
                _student_account_form(registering=mode == "Register new profile")
            else:
                _student_attendance(*student)
        except APIError as error:
            if error.code == "42501":
                st.error(
                    "Supabase denied student access. Ask your administrator to apply "
                    "the student attendance migration, then try again."
                )
            else:
                st.error("Student data is unavailable. Please try again.")
        except (httpx.HTTPError, DatabaseConfigurationError):
            st.error("Student data is unavailable. Ask your administrator to check the database setup.")
        except (FaceCaptureError, VoiceCaptureError) as error:
            st.error(str(error))
        except RuntimeError:
            st.error("Biometric processing is unavailable. Please try again.")


def _capture_voice():
    return st.audio_input('Say “I am present. My name is …”', sample_rate=16000)


def _student_account_form(*, registering: bool):
    st.title("Register new profile" if registering else "Student sign-in", anchor=False)
    with st.form("student_register" if registering else "student_sign_in", border=False):
        if registering:
            student_input = st.text_input("Enter your name", max_chars=80)
            st.caption("Your profile stores face and voice embeddings for sign-in and attendance.")
        else:
            student_input = st.text_input(
                "Student ID", key="student_login_id",
                placeholder="Enter your student ID", max_chars=19,
            )
        photo = st.camera_input("Position your face in the center")
        audio = _capture_voice()
        submitted = st.form_submit_button(
            "Create account" if registering else "Sign in", type="primary", width="stretch",
        )

    if not submitted:
        return
    student_input = student_input.strip()
    if registering and not student_input:
        st.error("Enter your name.")
        return
    if not registering and (
        not re.fullmatch(r"[0-9]{1,19}", student_input) or not 0 < int(student_input) <= 2**63 - 1
    ):
        st.error("Enter a valid student ID.")
        return
    if photo is None or audio is None:
        st.error("Take a photo and record your voice before continuing.")
        return

    if registering:
        student_id = create_student(
            student_input, get_face_embedding(photo.getvalue()), get_voice_embedding(audio.getvalue()),
        )
        name = student_input
    else:
        student_id = int(student_input)
        profile = get_student_profile(student_id)
        if not profile or not face_matches(get_face_embedding(photo.getvalue()), profile["face_embedding"]):
            st.error("Sign-in failed. Check your student ID and try a new recording and photo.")
            return
        if not _voice_matches(student_id, audio, profile["voice_embedding"]):
            st.error("Sign-in failed. Check your student ID and try a new recording and photo.")
            return
        name = profile["name"]

    st.session_state["student_identity"] = (student_id, name)
    st.rerun()


def _voice_matches(student_id, audio, reference):
    matched_id, _ = identify_speaker(get_voice_embedding(audio.getvalue()), {student_id: reference})
    return matched_id == student_id


def _student_attendance(student_id: int, name: str):
    st.title("Student attendance", anchor=False)
    st.html(f"""
        <div class="student-welcome">Welcome, {escape(name)}.</div>
        <div class="student-id">Student ID <strong>{student_id}</strong></div>
    """)
    if st.button("Sign out", key="student_sign_out"):
        del st.session_state["student_identity"]
        st.rerun()

    render_join_subject_form(student_id)
    subjects = {row["subject_id"]: row for row in get_student_subjects(student_id)}
    if not subjects:
        st.info("Ask your teacher for a share code or give them your student ID.")
        return

    subject_id = st.selectbox(
        "Subject", list(subjects),
        format_func=lambda key: f"{subjects[key]['subject_code']} · {subjects[key]['section']}",
    )
    method = st.radio("Attendance method", ("Photo", "Voice"), horizontal=True)
    with st.form(f"student_attendance_{method}", border=False, clear_on_submit=True):
        sample = st.camera_input("Take a new photo") if method == "Photo" else _capture_voice()
        submitted = st.form_submit_button("Mark attendance", type="primary", width="stretch")
    if not submitted:
        return
    if sample is None:
        st.error("Capture a sample before marking attendance.")
        return

    profile = get_student_profile(student_id)
    if profile is None:
        st.error("Your student profile is unavailable.")
        return
    if method == "Photo":
        matched = face_matches(get_face_embedding(sample.getvalue()), profile["face_embedding"])
    else:
        matched = _voice_matches(student_id, sample, profile["voice_embedding"])
    if not matched:
        st.error("The sample did not match your profile. Try again.")
        return

    status = record_attendance(student_id, subject_id)
    if status == "recorded":
        st.success("Attendance marked.")
    elif status == "already_recorded":
        st.info("Your attendance is already marked for this subject today.")
    else:
        st.error("Ask your teacher to add you to this subject.")
