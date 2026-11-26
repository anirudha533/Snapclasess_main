from datetime import datetime
from zoneinfo import ZoneInfo

import bcrypt
from postgrest.exceptions import APIError

from src.database.config import get_supabase


# Keep failed lookups comparable to failed checks on existing accounts.
_DUMMY_HASH = bcrypt.hashpw(b"unused-password", bcrypt.gensalt())


def hash_pass(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def check_pass(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def check_teacher_exists(username: str) -> bool:
    response = (
        get_supabase().table("teachers").select("teacher_id")
        .eq("username", username).limit(1).execute()
    )
    return bool(response.data)


def create_teacher(username: str, password: str, name: str) -> bool:
    if check_teacher_exists(username):
        return False

    try:
        get_supabase().table("teachers").insert(
            {"username": username, "password_hash": hash_pass(password), "name": name},
            returning="minimal",
        ).execute()
    except APIError as error:
        if error.code == "23505":
            return False
        raise
    return True


def teacher_login(username: str, password: str) -> str | None:
    response = (
        get_supabase().table("teachers").select("name,password_hash")
        .eq("username", username).limit(1).execute()
    )
    teacher = response.data[0] if response.data else None
    password_hash = teacher["password_hash"] if teacher else None
    if check_pass(password, password_hash or _DUMMY_HASH.decode("ascii")) and password_hash:
        return teacher["name"]
    return None


def get_student_profile(student_id: int) -> dict | None:
    response = (
        get_supabase().table("students").select("name,face_embedding,voice_embedding")
        .eq("student_id", student_id).limit(1).execute()
    )
    return response.data[0] if response.data else None


def get_student_profiles_by_name(name: str) -> list[dict]:
    # PostgREST treats "*" as a LIKE wildcard. Match it as one character
    # in the query, then verify the literal name before using a profile.
    pattern = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("*", "_")
    client = get_supabase()
    profiles = []
    offset = 0
    while True:
        batch = (
            client.table("students").select("student_id,name,face_embedding,voice_embedding")
            .ilike("name", pattern).order("student_id").range(offset, offset + 499).execute().data
        )
        if not batch:
            return profiles
        profiles.extend(row for row in batch if row["name"].casefold() == name.casefold())
        offset += len(batch)


def create_student(name: str, face_embedding: list[float], voice_embedding: list[float]) -> int:
    response = get_supabase().table("students").insert({
        "name": name,
        "face_embedding": face_embedding,
        "voice_embedding": voice_embedding,
    }).select("student_id").execute()
    return response.data[0]["student_id"]


def get_student_subjects(student_id: int) -> list[dict]:
    response = (
        get_supabase().table("subject_students")
        .select("subjects(subject_id,subject_code,name,section)")
        .eq("student_id", student_id).order("subject_id").execute()
    )
    return [row["subjects"] for row in response.data if row["subjects"]]


def record_attendance(student_id: int, subject_id: int) -> str:
    return get_supabase().rpc("record_student_attendance", {
        "p_student_id": student_id, "p_subject_id": subject_id,
    }).execute().data


def get_teacher_subjects(username: str, *, include_stats: bool = True) -> list[dict]:
    client = get_supabase()
    columns = "subject_id,subject_code,name,section,teachers!inner(username)"
    if include_stats:
        columns += ",subject_students(count)"
    response = (
        client.table("subjects").select(columns)
        .eq("teachers.username", username).order("subject_id").execute()
    )
    if not include_stats:
        return response.data

    school_timezone = ZoneInfo("Asia/Kolkata")
    for subject in response.data:
        roster_count = subject.pop("subject_students", [])
        subject["total_students"] = roster_count[0]["count"] if roster_count else 0

        attendance_dates = set()
        offset = 0
        while True:
            logs = (
                client.table("attendance_logs").select("timestamp")
                .eq("subject_id", subject["subject_id"]).order("id")
                .range(offset, offset + 499).execute().data
            )
            if not logs:
                break
            attendance_dates.update(
                datetime.fromisoformat(log["timestamp"]).astimezone(school_timezone).date()
                for log in logs
            )
            offset += len(logs)
        subject["total_classes"] = len(attendance_dates)
    return response.data


def create_subject(username: str, code: str, name: str, section: str) -> None:
    client = get_supabase()
    teacher = (
        client.table("teachers").select("teacher_id")
        .eq("username", username).single().execute().data
    )
    client.table("subjects").insert({
        "teacher_id": teacher["teacher_id"],
        "subject_code": code,
        "name": name,
        "section": section,
    }, returning="minimal").execute()


def enroll_in_subject(student_id: int, subject_id: int) -> None:
    get_supabase().table("subject_students").upsert(
        {"student_id": student_id, "subject_id": subject_id},
        on_conflict="subject_id,student_id", ignore_duplicates=True, returning="minimal",
    ).execute()


def unenroll_from_subject(student_id: int, subject_id: int) -> None:
    get_supabase().table("subject_students").delete(returning="minimal").eq(
        "student_id", student_id,
    ).eq("subject_id", subject_id).execute()


def get_subject_biometrics(subject_id: int, field: str) -> dict:
    if field not in {"face_embedding", "voice_embedding"}:
        raise ValueError("Unsupported biometric field")
    client = get_supabase()
    candidates = {}
    offset = 0
    while True:
        batch = (
            client.table("subject_students").select(f"student_id,students({field})")
            .eq("subject_id", subject_id).order("student_id")
            .range(offset, offset + 499).execute().data
        )
        if not batch:
            return candidates
        candidates.update(
            (row["student_id"], row["students"][field])
            for row in batch if row["students"] and row["students"][field] is not None
        )
        offset += len(batch)


def get_attendance_report(
    subject_id: int, start: str, end: str, *, include_history: bool = False,
) -> list[dict]:
    client = get_supabase()
    roster_query = (
        client.table("subject_students").select("student_id,students(name)")
        .eq("subject_id", subject_id).order("student_id")
    )
    log_columns = "student_id,timestamp,students(name)" if include_history else "student_id"
    logs_query = (
        client.table("attendance_logs").select(log_columns)
        .eq("subject_id", subject_id).gte("timestamp", start).lt("timestamp", end).order("id")
    )
    rows = {}
    present = set()
    for query in (roster_query, logs_query):
        offset = 0
        while True:
            batch = query.range(offset, offset + 499).execute().data
            if not batch:
                break
            offset += len(batch)
            for row in batch:
                student_id = row["student_id"]
                if query is roster_query:
                    rows[student_id] = {
                        "Student ID": student_id, "Name": row["students"]["name"], "Status": "Absent",
                    }
                    continue
                present.add(student_id)
                if include_history:
                    entry = rows.setdefault(student_id, {
                        "Student ID": student_id, "Name": row["students"]["name"], "Status": "Absent",
                    })
                    marked_at = datetime.fromisoformat(row["timestamp"])
                    if "Marked At" not in entry or marked_at < entry["Marked At"]:
                        entry["Marked At"] = marked_at

    for student_id in present.intersection(rows):
        rows[student_id]["Status"] = "Present"
    return list(rows.values())


def get_subject_join_code(username: str, subject_id: int) -> str | None:
    response = (
        get_supabase().table("subjects").select("join_code,teachers!inner(username)")
        .eq("subject_id", subject_id).eq("teachers.username", username).limit(1).execute()
    )
    return response.data[0]["join_code"] if response.data else None


def join_subject_by_code(student_id: int, code: str) -> str:
    return get_supabase().rpc("join_subject_by_code", {
        "p_student_id": student_id, "p_join_code": code,
    }).execute().data
