from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from postgrest.exceptions import APIError
import streamlit as st

from src.database.config import DatabaseConfigurationError
from src.database.db import (
    get_attendance_report,
    get_teacher_subjects,
    record_attendance,
)

from src.screens.components.create_subject.form import render_create_subject
from src.screens.components.subject_card.card import render_subject_cards

_SCHOOL_TZ = ZoneInfo("Asia/Kolkata")


def teacher_attendance(username: str):
    take, manage, records = st.tabs(
        ["Take Attendance", "Manage Subjects", "Attendance Records"],
        key="current_teacher_tab",
        on_change="rerun",
    )
    try:
        subjects = {row["subject_id"]: row for row in get_teacher_subjects(username)}
        match st.session_state["current_teacher_tab"]:
            case "Take Attendance":
                with take:
                    teacher_tab_take_attendance(subjects)
            case "Manage Subjects":
                with manage:
                    teacher_tab_manage_subjects(username, subjects)
            case "Attendance Records":
                with records:
                    teacher_tab_attendance_records(subjects)
    except (APIError, httpx.HTTPError, DatabaseConfigurationError):
        st.error("Attendance data is unavailable. Check the Supabase attendance migration.")


def _choose_subject(subjects: dict, key: str) -> int | None:
    if not subjects:
        st.info("Create a subject in Manage Subjects to get started.")
        return None
    return st.selectbox(
        "Subject", list(subjects), key=key,
        format_func=lambda subject_id: (
            f"{subjects[subject_id]['subject_code']} · "
            f"{subjects[subject_id]['name']} · {subjects[subject_id]['section']}"
        ),
    )


def _report_for_day(subject_id: int, day: date) -> list[dict]:
    start = datetime.combine(day, time.min, tzinfo=_SCHOOL_TZ)
    return get_attendance_report(subject_id, start.isoformat(), (start + timedelta(days=1)).isoformat())


def teacher_tab_take_attendance(subjects: dict):
    st.header("Take Attendance", anchor=False)
    subject_id = _choose_subject(subjects, "teacher_take_subject")
    if subject_id is None:
        return

    today = datetime.now(_SCHOOL_TZ).date()
    roster = _report_for_day(subject_id, today)
    if not roster:
        st.info("Add students to this subject in Manage Subjects.")
        return

    pending = {row["Student ID"]: row["Name"] for row in roster if row["Status"] == "Absent"}
    if not pending:
        st.success("Everyone on this subject’s roster is marked present today.")
        return

    with st.form("teacher_mark_attendance", clear_on_submit=True):
        student_id = st.selectbox(
            "Student", list(pending), index=None, placeholder="Choose a student",
            format_func=lambda key: f"{pending[key]} · ID {key}",
        )
        submitted = st.form_submit_button("Mark present", type="primary")
    if not submitted:
        return
    if student_id is None:
        st.error("Choose a student to mark present.")
        return

    status = record_attendance(student_id, subject_id)
    if status == "recorded":
        st.success(f"{pending[student_id]} was marked present.")
    elif status == "already_recorded":
        st.info("This student is already marked present today.")
    else:
        st.error("This student is no longer on the subject roster.")


def teacher_tab_manage_subjects(username: str, subjects: dict):
    render_create_subject(username)

    if not subjects:
        st.info("Create a subject to see it here.")
        return
    render_subject_cards(username, subjects.values())


def teacher_tab_attendance_records(subjects: dict):
    st.header("Attendance Records", anchor=False)
    subject_id = _choose_subject(subjects, "teacher_records_subject")
    if subject_id is None:
        return
    today = datetime.now(_SCHOOL_TZ).date()
    day = st.date_input("Attendance date", today, max_value=today)
    report = _report_for_day(subject_id, day)
    if report:
        st.dataframe(report, hide_index=True, width="stretch")
    else:
        st.info("This subject has no enrolled students.")
