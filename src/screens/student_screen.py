from html import escape
import logging

import httpx
from postgrest.exceptions import APIError
import streamlit as st

from src.UI.base_layout import PORTAL_INPUT_STYLES
from src.database.config import DatabaseConfigurationError
from src.database.db import (
    create_student,
    get_student_profile,
    get_student_profiles_by_name,
    get_student_subjects,
    record_attendance,
    unenroll_from_subject,
)
from src.screens.components.subject_sharing.forms import render_join_subject_form
from src.voice_pipelines.recognition import VoiceCaptureError, get_voice_embedding, identify_speaker
from src.face_pipelines.recognition import FaceCaptureError, face_matches, get_face_embedding


logger = logging.getLogger(__name__)


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
        .stApp:has(.st-key-student_dashboard) .block-container { max-width: 900px; }
        .st-key-student_dashboard .student-subject {
            min-height: 8.25rem;
            padding: 1.65rem;
            background: #fff;
            color: #1e2030;
            border: 1px solid #303244;
            border-radius: 1.25rem;
            font: 400 1rem Outfit, sans-serif;
            overflow-wrap: anywhere;
        }
        .st-key-student_dashboard .student-subject h3 {
            color: inherit;
            font: 700 1.35rem Outfit, sans-serif;
            margin: 0 0 1rem;
            padding: 0;
        }
        .student-subject .student-code {
            background: #e9e8ff;
            color: #4148a7;
            padding: .2rem .45rem;
            border-radius: .35rem;
        }
        .st-key-student_dashboard .student-footer {
            text-align: center;
            padding: 2rem 0 .5rem;
            color: #282a3f;
            font: 600 .9rem Outfit, sans-serif;
        }
        .st-key-student_enroll button {
            background: #595FDA;
            color: white;
            border: 0;
            border-radius: 999px;
        }
        .st-key-student_dashboard [class*="st-key-student_mark_"] button {
            background: #171721;
            color: white;
            border: 0;
            border-radius: 999px;
        }
        .st-key-student_sign_out button {
            background: #C91E79;
            color: #FFFFFF;
            border: 0;
            border-radius: 999px;
            padding-inline: 1.25rem;
        }
        .st-key-student_sign_out button:hover { background: #AC1665; }
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
    student = st.session_state.get("student_identity")
    with st.container(key="student_portal"):
        with st.container(key="student_dashboard" if student else "student_auth"):
            _student_portal_content(student)


def _student_portal_content(student):
    brand, back = st.columns([2, 1], vertical_alignment="center")
    with brand:
        st.html('''
            <div class="student-brand">
                <span class="student-brand-icon" aria-hidden="true">🎓</span>
                <span class="student-wordmark">SNAP<br>CLASS</span>
            </div>
        ''')
    with back:
        if student:
            student_id, name = student
            st.html(f'<div class="student-welcome">Welcome, {escape(name)}</div>'
                    f'<div class="student-id">Student ID <strong>{student_id}</strong></div>')
            if st.button("Log out", key="student_sign_out"):
                del st.session_state["student_identity"]
                st.session_state.pop("student_attendance_subject", None)
                st.session_state.pop("student_enrollment_open", None)
                st.session_state.pop("student_unenroll_subject", None)
                st.rerun()
        elif st.button("Go back to Home", key="student_home", width="stretch"):
            st.session_state["login_type"] = None
            st.rerun()

    try:
        if student is None:
            mode = st.radio("Student account", ("Sign in", "Register new profile"), horizontal=True)
            _student_account_form(registering=mode == "Register new profile")
        else:
            _student_attendance(student[0])
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
                "Full name", key="student_login_name",
                placeholder="Enter the name you registered with", max_chars=80,
            )
        photo = st.camera_input("Position your face in the center")
        audio = _capture_voice()
        submitted = st.form_submit_button(
            "Create account" if registering else "Sign in", type="primary", width="stretch",
        )

    if not submitted:
        return
    student_input = student_input.strip()
    if not student_input:
        st.error("Enter your name.")
        return
    if photo is None or audio is None:
        st.error("Take a photo and record your voice before continuing.")
        return

    if registering:
        with st.spinner("Building your face and voice profiles…", show_time=True):
            student_id = create_student(
                student_input, get_face_embedding(photo.getvalue()), get_voice_embedding(audio.getvalue()),
            )
        name = student_input
    else:
        with st.spinner("Verifying your face and voice…", show_time=True):
            profile = _match_student_profile(student_input, photo.getvalue(), audio.getvalue())
        if profile is None:
            st.error("Sign-in failed. Check the name you registered with and try a new photo and recording.")
            return
        student_id, name = profile["student_id"], profile["name"]

    st.session_state["student_identity"] = (student_id, name)
    st.rerun()


def _match_student_profile(name: str, photo: bytes, audio: bytes) -> dict | None:
    profiles = get_student_profiles_by_name(name)
    if not profiles:
        logger.warning("Student sign-in failed: no profile matched the supplied name")
        return None
    face = get_face_embedding(photo)
    face_matches_by_name = [
        profile for profile in profiles if face_matches(face, profile["face_embedding"])
    ]
    if not face_matches_by_name:
        logger.warning("Student sign-in failed: face did not match")
        return None
    voice = get_voice_embedding(audio)
    matches = []
    for profile in face_matches_by_name:
        student_id = profile["student_id"]
        matched_id, _ = identify_speaker(voice, {student_id: profile["voice_embedding"]})
        if matched_id == student_id:
            matches.append(profile)
    if len(matches) != 1:
        logger.warning("Student sign-in failed: no unique face and voice match")
        return None
    return matches[0]


def _voice_matches(student_id, audio, reference):
    matched_id, _ = identify_speaker(get_voice_embedding(audio.getvalue()), {student_id: reference})
    return matched_id == student_id


def _student_attendance(student_id: int):
    title, enroll = st.columns([1, 1], vertical_alignment="center")
    with title:
        st.title("Your Enrolled Subjects", anchor=False)
    with enroll:
        enrollment_open = st.session_state.setdefault("student_enrollment_open", False)
        if st.button("Enroll in Subject", key="student_enroll", width="stretch"):
            st.session_state["student_enrollment_open"] = not enrollment_open
    st.divider()

    if st.session_state["student_enrollment_open"] or st.query_params.get("join-code"):
        render_join_subject_form(student_id)

    with st.spinner("Loading your enrolled subjects…", show_time=True):
        subjects = get_student_subjects(student_id)
    if not subjects:
        st.info("Ask your teacher for a share code or give them your student ID.")

    for index in range(0, len(subjects), 2):
        for column, subject in zip(st.columns(2), subjects[index:index + 2]):
            with column:
                subject_id = subject["subject_id"]
                st.html(f"""
                    <article class="student-subject">
                        <h3>{escape(subject["name"])}</h3>
                        Code <span class="student-code">{escape(subject["subject_code"])}</span>
                        &nbsp;·&nbsp; Section {escape(subject["section"])}
                    </article>
                """)
                if st.button("Mark attendance", key=f"student_mark_{subject_id}", width="stretch"):
                    st.session_state["student_attendance_subject"] = subject_id
                if st.button("Unenroll", key=f"student_unenroll_{subject_id}", width="stretch"):
                    st.session_state["student_unenroll_subject"] = subject_id
                    st.rerun()
                if st.session_state.get("student_unenroll_subject") == subject_id:
                    st.write(f'Unenroll from {subject["name"]}?')
                    confirm, cancel = st.columns(2)
                    if confirm.button("Confirm", key=f"student_unenroll_confirm_{subject_id}"):
                        with st.spinner("Removing your enrollment…", show_time=True):
                            unenroll_from_subject(student_id, subject_id)
                        del st.session_state["student_unenroll_subject"]
                        if st.session_state.get("student_attendance_subject") == subject_id:
                            del st.session_state["student_attendance_subject"]
                        st.rerun()
                    if cancel.button("Cancel", key=f"student_unenroll_cancel_{subject_id}"):
                        del st.session_state["student_unenroll_subject"]
                        st.rerun()

    selected = st.session_state.get("student_attendance_subject")
    subject = next((row for row in subjects if row["subject_id"] == selected), None)
    if subject:
        st.divider()
        st.subheader(f'Attendance for {subject["name"]}', anchor=False)
        if st.button("Close attendance"):
            del st.session_state["student_attendance_subject"]
            st.rerun()
        _mark_student_attendance(student_id, selected)

    st.html('<footer class="student-footer">Created with ❤️ by Anirudh</footer>')


def _mark_student_attendance(student_id: int, subject_id: int):
    method = st.radio("Attendance method", ("Photo", "Voice"), horizontal=True)
    with st.form(f"student_attendance_{subject_id}_{method}", border=False, clear_on_submit=True):
        sample = st.camera_input("Take a new photo") if method == "Photo" else _capture_voice()
        submitted = st.form_submit_button("Mark attendance", type="primary", width="stretch")
    if not submitted:
        return
    if sample is None:
        st.error("Capture a sample before marking attendance.")
        return

    with st.spinner("Verifying your attendance sample…", show_time=True):
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

    with st.spinner("Saving attendance…", show_time=True):
        status = record_attendance(student_id, subject_id)
    if status == "recorded":
        st.success("Attendance marked.")
    elif status == "already_recorded":
        st.info("Your attendance is already marked for this subject today.")
    else:
        st.error("Ask your teacher to add you to this subject.")
