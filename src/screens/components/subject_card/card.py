from collections.abc import Iterable
from html import escape

from postgrest.exceptions import APIError
import streamlit as st

from src.database.db import enroll_in_subject
from src.screens.components.subject_sharing.forms import share_subject_dialog


_SUBJECT_CARD_STYLE = """
<style>
.st-key-teacher_subject_cards article {
    box-sizing: border-box;
    width: 100%;
    padding: clamp(1rem, 3vw, 1.6rem);
    border: 1px solid #B6B5D3;
    border-radius: 1.1rem;
    background: #fff;
    color: #27283C;
    font-family: Outfit, sans-serif;
    overflow-wrap: anywhere;
}
.st-key-teacher_subject_cards article h3 {
    margin: 0 0 .6rem;
    padding: 0;
    color: #141522;
    font: 700 clamp(1.2rem, 3vw, 1.5rem)/1.25 Outfit, sans-serif;
}
.st-key-teacher_subject_cards .subject-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: .45rem .9rem;
    color: #4D4F65;
}
.st-key-teacher_subject_cards .subject-card-code,
.st-key-teacher_subject_cards .subject-card-counts span {
    display: inline-block;
    border-radius: .5rem;
    padding: .2rem .55rem;
}
.st-key-teacher_subject_cards .subject-card-code {
    background: #EBE9FB;
    color: #463DA1;
    font-weight: 600;
}
.st-key-teacher_subject_cards .subject-card-counts {
    display: flex;
    flex-wrap: wrap;
    gap: .45rem;
    margin-top: .65rem;
}
.st-key-teacher_subject_cards .subject-card-counts span { background: #F8EEF5; }
</style>
"""


def render_subject_cards(username: str, subjects: Iterable[dict]):
    st.html(_SUBJECT_CARD_STYLE)
    with st.container(key="teacher_subject_cards", gap="medium"):
        for subject in subjects:
            _render_subject_card(username, subject)


def _render_subject_card(username: str, subject: dict):
    subject_id = subject["subject_id"]
    name = escape(subject["name"] or "Untitled subject")
    code = escape(subject["subject_code"])
    section = escape(subject["section"] or "N/A")
    students = int(subject["total_students"])
    classes = int(subject["total_classes"])
    with st.container(key=f"teacher_subject_card_{subject_id}", gap="small"):
        st.html(f"""
            <article>
                <h3>{name}</h3>
                <div class="subject-card-meta">
                    <span>Code <strong class="subject-card-code">{code}</strong></span>
                    <span>Section <strong>{section}</strong></span>
                </div>
                <div class="subject-card-counts">
                    <span>{students} {"student" if students == 1 else "students"}</span>
                    <span>{classes} {"class" if classes == 1 else "classes"}</span>
                </div>
            </article>
        """)
        with st.container(horizontal=True, gap="small"):
            if st.button(
                "Share Code", key=f"teacher_share_subject_{subject_id}",
                icon=":material/share:",
                help=f"Share the join code for {subject['subject_code']}.",
            ):
                share_subject_dialog(username, subject_id, subject["name"] or "Untitled subject")
            manual = st.popover(
                "Add Student by ID", key=f"teacher_add_to_subject_{subject_id}",
                type="tertiary", on_change="rerun",
                help=f"Add a student to {subject['subject_code']}.",
            )
            if manual.open:
                with manual:
                    _add_student_by_id(subject_id)


def _add_student_by_id(subject_id: int):
    feedback_key = f"teacher_student_added_{subject_id}"
    if st.session_state.pop(feedback_key, False):
        st.success("Student is on the subject roster.")
    with st.form(f"teacher_add_student_{subject_id}", clear_on_submit=True):
        student_id = st.text_input("Student ID to add", max_chars=19).strip()
        if st.form_submit_button("Add student", width="stretch"):
            if student_id.isascii() and student_id.isdecimal() and 0 < int(student_id) <= 2**63 - 1:
                try:
                    with st.spinner("Enrolling student…", show_time=True):
                        enroll_in_subject(int(student_id), subject_id)
                except APIError as error:
                    if error.code != "23503":
                        raise
                    st.error("No student profile exists for that ID.")
                else:
                    st.session_state[feedback_key] = True
                    st.rerun()
            else:
                st.error("Enter a valid student ID.")

