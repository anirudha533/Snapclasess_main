from datetime import date, datetime, time, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import httpx
from PIL import Image, ImageOps
from postgrest.exceptions import APIError
import streamlit as st

from src.database.config import DatabaseConfigurationError
from src.database.db import (
    get_attendance_report,
    get_subject_biometrics,
    get_teacher_subjects,
    record_attendance,
)

from src.face_pipelines.recognition import (
    MAX_GROUP_PHOTO_PIXELS,
    FaceCaptureError,
    get_group_face_embeddings,
    match_group_faces,
)
from src.voice_pipelines.recognition import VoiceCaptureError, get_voice_embedding, identify_speaker
from src.screens.components.create_subject.form import render_create_subject
from src.screens.components.subject_card.card import render_subject_cards

_SCHOOL_TZ = ZoneInfo("Asia/Kolkata")


def teacher_attendance(username: str):
    st.html("""
        <style>
        .st-key-teacher_take_controls button,
        .st-key-teacher_add_photos button {
            width: 100%;
            min-height: 3.15rem;
            border-radius: 999px;
        }
        .st-key-teacher_portal .st-key-teacher_add_photos button {
            background: #595fda;
            color: white;
            border: 0;
        }
        .st-key-teacher_take_subject [data-baseweb="select"] > div {
            background: #f6f6fc;
            color: #25263a;
            border-color: transparent;
            border-radius: .55rem;
            min-height: 3.15rem;
        }
        .st-key-teacher_take_subject [data-baseweb="select"] svg { color: #25263a; }
        .st-key-teacher_take_controls button:disabled { opacity: .7; }
        .st-key-teacher_portal .st-key-teacher_clear_photos button {
            background: #16161e;
            color: white;
        }
        .st-key-teacher_portal .st-key-teacher_run_faces button {
            background: #c51f78;
            color: white;
        }
        .st-key-teacher_portal .st-key-teacher_voice button {
            background: #595fda;
            color: white;
        }
        </style>
    """)
    take, manage, records = st.tabs(
        ["Take Attendance", "Manage Subjects", "Attendance Records"],
        key="current_teacher_tab",
        on_change="rerun",
    )
    active_tab = st.session_state["current_teacher_tab"]
    try:
        with st.spinner("Loading your subjects…", show_time=True):
            rows = get_teacher_subjects(username, include_stats=active_tab == "Manage Subjects")
            subjects = {row["subject_id"]: row for row in rows}
        match active_tab:
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


def _choose_subject(subjects: dict, key: str, label: str = "Subject") -> int | None:
    if not subjects:
        st.info("Create a subject in Manage Subjects to get started.")
        return None
    return st.selectbox(
        label, list(subjects), key=key,
        format_func=lambda subject_id: (
            f"{subjects[subject_id]['name']} · "
            f"{subjects[subject_id]['subject_code']} · {subjects[subject_id]['section']}"
        ),
    )


def _report_for_day(subject_id: int, day: date, *, include_history: bool = False) -> list[dict]:
    start = datetime.combine(day, time.min, tzinfo=_SCHOOL_TZ)
    return get_attendance_report(
        subject_id, start.isoformat(), (start + timedelta(days=1)).isoformat(),
        include_history=include_history,
    )


def teacher_tab_take_attendance(subjects: dict):
    st.divider()
    st.title("Take AI Attendance", anchor=False)
    subject_column, upload_column = st.columns([3, 1], vertical_alignment="bottom")
    with subject_column:
        subject_id = _choose_subject(subjects, "teacher_take_subject", "Select Subject")
    if subject_id is None:
        return

    today = datetime.now(_SCHOOL_TZ).date()
    with st.spinner("Loading today’s roster…", show_time=True):
        roster = _report_for_day(subject_id, today)
    if not roster:
        st.info("Add students to this subject in Manage Subjects.")
    pending = {row["Student ID"]: row["Name"] for row in roster if row["Status"] == "Absent"}
    scope = (st.session_state.get("teacher_identity"), subject_id, today)
    result = st.session_state.pop("teacher_attendance_result", None)
    if result and result[0] == scope:
        statuses = result[1]
        st.success(f"Marked {statuses.count('recorded')} student(s) present.")
        if statuses.count("already_recorded"):
            st.info(f"{statuses.count('already_recorded')} student(s) already marked present.")
        if statuses.count("not_enrolled"):
            st.warning(f"{statuses.count('not_enrolled')} student(s) are no longer enrolled.")
    if roster and not pending:
        st.success("Everyone on this subject’s roster is marked present today.")

    if st.session_state.get("teacher_capture_scope") != scope:
        st.session_state["teacher_capture_scope"] = scope
        st.session_state.pop("teacher_attendance_photos", None)
        st.session_state["teacher_capture_revision"] = st.session_state.get("teacher_capture_revision", 0) + 1
        _clear_suggestions()

    revision = st.session_state["teacher_capture_revision"]
    if upload_column.button(
        "Add Photos", key="teacher_add_photos", width="stretch",
        icon=":material/add_photo_alternate:", type="primary",
    ):
        st.session_state["teacher_photo_source"] = "Camera"
        _capture_attendance_photos(revision)
    photos = st.session_state.get("teacher_attendance_photos", [])
    st.divider()
    if photos:
        _render_added_photos(photos)
    with st.container(key="teacher_take_controls"):
        clear, analyze, voice = st.columns(3)
        if clear.button(
            "Clear all photos", key="teacher_clear_photos", icon=":material/delete:",
            disabled=not photos, width="stretch",
        ):
            st.session_state.pop("teacher_attendance_photos", None)
            st.session_state["teacher_capture_revision"] += 1
            _clear_suggestions()
            st.rerun()
        if voice.button(
            "Use Voice Attendance", key="teacher_voice", icon=":material/mic:",
            type="primary", width="stretch",
        ):
            st.session_state.pop("teacher_voice_result", None)
            st.session_state["teacher_voice_revision"] = st.session_state.get("teacher_voice_revision", 0) + 1
            _voice_attendance_dialog(subject_id, pending, scope, st.session_state["teacher_voice_revision"])
        run = analyze.button(
            "Run Face Analysis", key="teacher_run_faces", icon=":material/face:",
            disabled=not photos or not pending, width="stretch",
        )
    if run:
        _clear_suggestions()
        _analyze_group_photos(photos, subject_id, pending)
    summary = st.session_state.get("teacher_photo_analysis")
    if summary:
        faces, matched, new, issues = summary
        st.info(f"Detected {faces} face(s), matched {matched} enrolled student(s), "
                f"and found {new} new attendance match(es).")
        if issues:
            with st.expander("Photo analysis details"):
                for issue in issues:
                    st.write(issue)

    suggestions = [student_id for student_id in st.session_state.get("teacher_attendance_suggestions", [])
                   if student_id in pending]
    if suggestions:
        with st.form("teacher_confirm_attendance"):
            selected = st.multiselect(
                "Review students to mark present", options=suggestions, default=suggestions,
                format_func=lambda student_id: f"{pending[student_id]} · ID {student_id}",
                key=f"teacher_review_{revision}_{'_'.join(map(str, suggestions))}",
            )
            confirmed = st.form_submit_button("Confirm attendance", type="primary")
        if confirmed:
            if selected:
                statuses = []
                try:
                    with st.spinner("Saving attendance…", show_time=True):
                        for student_id in selected:
                            statuses.append(record_attendance(student_id, subject_id))
                except (APIError, httpx.HTTPError, DatabaseConfigurationError):
                    st.session_state["teacher_attendance_suggestions"] = selected[len(statuses):]
                    st.warning(
                        f"Save interrupted. {statuses.count('recorded')} new attendance record(s) were confirmed saved. "
                        "Click Confirm attendance again to retry the remaining students."
                    )
                    return
                _clear_suggestions()
                st.session_state["teacher_attendance_result"] = (scope, statuses)
                st.rerun()
            st.info("Select at least one student to confirm attendance.")

    if pending:
        with st.expander("Mark attendance manually"):
            _mark_manually(subject_id, pending)


@st.dialog("Voice Attendance", width="medium")
def _voice_attendance_dialog(subject_id: int, pending: dict, scope: tuple, revision: int):
    with st.container(key="teacher_voice_dialog"):
        st.html("""
            <style>
            [role="dialog"]:has(.st-key-teacher_voice_dialog) {
                background: #fff;
                color: #202133;
                border: 0;
                border-radius: 1.25rem;
                width: min(38rem, calc(100% - 1.5rem));
                max-height: calc(100dvh - 1.5rem);
                overflow-y: auto;
            }
            [role="dialog"]:has(.st-key-teacher_voice_dialog) :is(h2, label),
            .st-key-teacher_voice_dialog [data-testid="stMarkdownContainer"] p {
                color: #202133;
            }
            .st-key-teacher_voice_dialog [data-testid="stAudioInput"] {
                background: #f2f3fa;
                border-radius: .8rem;
                padding: .75rem;
                color-scheme: light;
            }
            .st-key-teacher_voice_dialog button:is([kind="primary"], [kind="secondary"]) {
                min-height: 2.85rem;
                border: 0;
                border-radius: 999px;
                color: white;
                background: #535ce2;
            }
            .st-key-teacher_voice_discard button[kind="secondary"] { background: #bc236e; }
            .st-key-teacher_voice_dialog button [data-testid="stMarkdownContainer"] p { color: inherit; }
            .st-key-teacher_voice_dialog button:disabled { opacity: .45; }
            </style>
        """)
        st.write('Record one enrolled student saying “I am present,” followed by their name.')
        audio = st.audio_input(
            "Record classroom audio", sample_rate=16000, key=f"teacher_voice_audio_{revision}",
            on_change=st.session_state.pop, args=("teacher_voice_result", None),
        )
        if st.button("Analyze Audio", type="primary", width="stretch", disabled=audio is None):
            st.session_state.pop("teacher_voice_result", None)
            try:
                with st.spinner("Processing audio…", show_time=True):
                    candidates = get_subject_biometrics(subject_id, "voice_embedding")
                    if candidates:
                        match, _ = identify_speaker(get_voice_embedding(audio.getvalue()), candidates)
                if not candidates:
                    st.info("No students in this subject have a saved voice profile.")
                elif match is None:
                    st.warning("Speech was detected, but it did not match this subject’s voice profiles. "
                               "Try 4–8 seconds of clear speech from the enrolled student.")
                elif match not in pending:
                    st.info("Voice recognized. This student is already marked present today.")
                else:
                    st.session_state["teacher_voice_result"] = match
            except VoiceCaptureError as error:
                st.error(str(error))
            except (APIError, httpx.HTTPError, DatabaseConfigurationError, RuntimeError):
                st.error("Voice analysis is unavailable. Try again or mark attendance manually.")

        st.divider()
        match = st.session_state.get("teacher_voice_result")
        if match in pending:
            st.write("Review attendance before confirming.")
            st.dataframe(
                [{"Name": pending[match], "ID": match, "Source": "Voice", "Status": "Present"}],
                hide_index=True, width="stretch",
            )
        else:
            st.caption("A matched student will appear here for review.")

        discard, save = st.columns(2)
        if discard.button("Discard", key="teacher_voice_discard", width="stretch"):
            st.session_state.pop("teacher_voice_result", None)
            st.rerun()
        if save.button("Confirm & Save", type="primary", width="stretch", disabled=match not in pending):
            if datetime.now(_SCHOOL_TZ).date() != scope[2]:
                st.warning("The attendance date changed. Reopen Voice Attendance and analyze again.")
                return
            try:
                with st.spinner("Saving attendance…", show_time=True):
                    status = record_attendance(match, subject_id)
            except (APIError, httpx.HTTPError, DatabaseConfigurationError):
                st.error("Attendance could not be saved. Please try again.")
                return
            st.session_state.pop("teacher_voice_result", None)
            st.session_state["teacher_attendance_result"] = (scope, [status])
            st.rerun()


def _analyze_group_photos(photos: list[bytes], subject_id: int, pending: dict):
    matched = set()
    issues = []
    detected = 0
    with st.status("Loading enrolled student face profiles…", expanded=True) as status:
        candidates = get_subject_biometrics(subject_id, "face_embedding")
        if not candidates:
            status.update(label="No enrolled face profiles available", state="error")
            st.info("Students need a saved face profile before they can be matched from photos.")
            return
        progress = st.progress(0)
        for index, photo in enumerate(photos, start=1):
            label = f"Analyzing photo {index} of {len(photos)}"
            status.update(label=label)
            progress.progress((index - 1) / len(photos), text=label)
            try:
                faces = get_group_face_embeddings(photo)
            except FaceCaptureError as error:
                issues.append(f"Photo {index}: {error}")
                continue
            except RuntimeError:
                issues.append(f"Photo {index}: face processing was unavailable.")
                continue

            detected += len(faces)
            if not faces:
                issues.append(f"Photo {index}: no faces detected. Try a sharper, well-lit photo.")
                continue
            unmatched = 0
            ambiguous = 0
            for matches in match_group_faces(faces, candidates):
                if len(matches) == 1:
                    matched.add(matches[0])
                elif matches:
                    ambiguous += 1
                else:
                    unmatched += 1
            if unmatched or ambiguous:
                issues.append(f"Photo {index}: {unmatched} unmatched face(s), "
                              f"{ambiguous} face(s) with multiple possible matches.")
        progress.progress(1.0, text=f"Processed {len(photos)} of {len(photos)} photos")
        status.update(label="Face analysis complete", state="complete", expanded=False)

    st.session_state["teacher_photo_analysis"] = (
        detected, len(matched), len(matched.intersection(pending)), issues,
    )
    _show_suggestions(matched, pending)


def _render_added_photos(photos: list[bytes]):
    st.title("Added Photos", anchor=False)
    for start in range(0, len(photos), 4):
        for index, (column, photo) in enumerate(
            zip(st.columns(4), photos[start:start + 4]), start=start + 1,
        ):
            with column:
                try:
                    with Image.open(BytesIO(photo)) as source:
                        if source.width * source.height > MAX_GROUP_PHOTO_PIXELS:
                            st.caption(f"Photo {index} is too large to preview.")
                            continue
                        thumbnail = ImageOps.exif_transpose(source).convert("RGB")
                        thumbnail.thumbnail((420, 320))
                    st.image(thumbnail, caption=f"Photo {index}", width="stretch")
                except (OSError, Image.DecompressionBombError):
                    st.caption(f"Photo {index} could not be previewed.")


@st.dialog("Capture or upload photos", width="medium")
def _capture_attendance_photos(revision: int):
    with st.container(key="teacher_photo_dialog"):
        st.html("""
            <style>
            [data-testid="stDialog"]:has(.st-key-teacher_photo_dialog) [data-baseweb="modal"],
            [role="dialog"]:has(.st-key-teacher_photo_dialog) {
                border: 0;
                box-shadow: none;
            }
            [role="dialog"]:has(.st-key-teacher_photo_dialog) {
                outline: none;
                background: white;
                color: #202133;
                border-radius: 1.25rem;
                width: min(40rem, calc(100% - 1.5rem));
                max-height: calc(100dvh - 1.5rem);
                overflow-y: auto;
            }
            [role="dialog"]:has(.st-key-teacher_photo_dialog) :is(h2, label, [data-testid="stBaseButton-headerNoPadding"]) {
                color: #202133;
            }
            .st-key-teacher_photo_dialog [data-testid="stMarkdownContainer"] p {
                color: #202133;
            }
            .st-key-teacher_photo_dialog [data-testid="stCameraInput"] {
                width: min(100%, 30rem, max(14rem, 65dvh)) !important;
                margin-inline: auto;
            }
            .st-key-teacher_photo_dialog [data-testid="stCameraInput"] :is(video, img) {
                display: block;
                max-width: 100%;
                max-height: 34dvh;
                object-fit: contain;
                margin-inline: auto;
            }
            .st-key-teacher_photo_dialog button[kind="primary"],
            .st-key-teacher_photo_dialog [data-testid="stCameraInput"] button {
                background: #595fda;
                border: 0;
                color: white;
            }
            .st-key-teacher_photo_dialog button[kind="secondary"] {
                background: #09090b;
                border: 0;
                color: white;
            }
            .st-key-teacher_photo_dialog button:is([kind="primary"], [kind="secondary"]) {
                min-height: 2.75rem;
                border-radius: 999px;
            }
            .st-key-teacher_photo_dialog button [data-testid="stMarkdownContainer"] p {
                color: inherit;
            }
            </style>
        """)
        st.write("Add clear classroom photos with faces visible. For large groups, add photos from more than one angle.")
        source = st.session_state["teacher_photo_source"]
        camera, upload = st.columns(2, vertical_alignment="center")
        for column, label in ((camera, "Camera"), (upload, "Upload photos")):
            column.button(
                label, type="primary" if source == label else "secondary",
                width="stretch", on_click=st.session_state.update,
                args=({"teacher_photo_source": label},),
            )

        if source == "Camera":
            st.caption("Taking a photo adds it to the gallery.")
            snapshot = st.camera_input("Take Snapshot", key=f"teacher_snapshot_{revision}")
            if snapshot is not None:
                _finish_adding_photos([snapshot])
            selected = []
        else:
            selected = st.file_uploader(
                "Choose classroom photos", type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True, max_upload_size=10,
                key=f"teacher_upload_photos_{revision}",
                help="Group photos are supported. Add up to 20 photos in total.",
            )

        if st.button("Done", type="primary", width="stretch"):
            _finish_adding_photos(selected)


def _finish_adding_photos(selected):
    photos = st.session_state.get("teacher_attendance_photos", [])
    if len(photos) + len(selected) > 20:
        st.error("The gallery can hold up to 20 photos. Remove some files or clear the gallery and try again.")
        return
    if selected:
        with st.spinner("Adding photos to the gallery…", show_time=True):
            st.session_state["teacher_attendance_photos"] = photos + [
                photo.getvalue() for photo in selected
            ]
        _clear_suggestions()
    st.session_state["teacher_capture_revision"] += 1
    st.rerun()


def _clear_suggestions():
    st.session_state.pop("teacher_attendance_suggestions", None)
    st.session_state.pop("teacher_photo_analysis", None)


def _show_suggestions(matches: set, pending: dict):
    suggestions = sorted(matches.intersection(pending))
    st.session_state["teacher_attendance_suggestions"] = suggestions
    if not suggestions:
        st.info("No new attendance matches. Try another sample or mark attendance manually.")


def _mark_manually(subject_id: int, pending: dict):
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

    with st.spinner("Marking student present…", show_time=True):
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
    if not subjects:
        st.info("Create a subject in Manage Subjects to get started.")
        return

    today = datetime.now(_SCHOOL_TZ).date()
    day = st.date_input("Attendance date", today, max_value=today)
    with st.spinner("Loading attendance records…", show_time=True):
        reports = {
            subject_id: _report_for_day(subject_id, day, include_history=True)
            for subject_id in subjects
        }

    summary = []
    for subject_id, report in reports.items():
        if not report:
            continue
        subject = subjects[subject_id]
        first_marked = min((row["Marked At"] for row in report if "Marked At" in row), default=None)
        present = sum(row["Status"] == "Present" for row in report)
        summary.append((first_marked, {
            "Time": first_marked.astimezone(_SCHOOL_TZ).strftime("%Y-%m-%d %I:%M %p") if first_marked else "—",
            "Subject": subject["name"],
            "Subject Code": subject["subject_code"],
            "Attendance Stats": f"✅ {present}/{len(report)} students",
        }))

    if not summary:
        st.info("No enrolled students or attendance records for this date.")
        return

    no_time = datetime.min.replace(tzinfo=_SCHOOL_TZ)
    summary.sort(key=lambda entry: entry[0] if entry[0] is not None else no_time, reverse=True)
    st.subheader("Attendance Summary", anchor=False)
    st.dataframe([row for _, row in summary], hide_index=True, width="stretch")
    st.caption("Total includes the current roster and any former students marked present on this date.")

    subject_id = _choose_subject(subjects, "teacher_records_subject", "Subject details")
    details = []
    for row in reports[subject_id]:
        detail = dict(row)
        marked_at = detail.get("Marked At")
        detail["Marked At"] = marked_at.astimezone(_SCHOOL_TZ).strftime("%I:%M %p") if marked_at else "—"
        details.append(detail)
    if details:
        st.dataframe(details, hide_index=True, width="stretch")
    else:
        st.info("No enrolled students or attendance records for this subject and date.")
