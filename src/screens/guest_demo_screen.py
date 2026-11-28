import streamlit as st


SAMPLE_STUDENTS = ("Aarav Mehta", "Diya Rao", "Ishaan Patel", "Meera Shah", "Riya Kapoor")
SAMPLE_MATCHES = {
    "Group photo": ("Aarav Mehta", "Diya Rao", "Meera Shah"),
    "Voice": ("Ishaan Patel",),
}


def guest_demo_screen():
    if st.button("Back to SnapClass"):
        del st.query_params["demo"]
        st.rerun()

    st.title("SnapClass guest demo")
    st.subheader("Introduction to Data Science · Sample class")
    st.write(
        "Choose a sample input, review the simulated matches, and confirm who is present. "
        "This demo uses fictional students and does not save attendance."
    )

    sample = st.radio("Sample input", SAMPLE_MATCHES.keys(), horizontal=True)
    suggested = SAMPLE_MATCHES[sample]
    st.write("Suggested matches: " + ", ".join(suggested))

    with st.form(f"guest_attendance_{sample}"):
        present = st.multiselect(
            "Students present",
            SAMPLE_STUDENTS,
            default=suggested,
            key=f"guest_present_{sample}",
            help="Add a missed student or remove an incorrect match before confirming.",
        )
        confirmed = st.form_submit_button("Confirm sample attendance", type="primary")

    if confirmed:
        st.success(f"Preview confirmed for {len(present)} of {len(SAMPLE_STUDENTS)} students.")
        st.table([
            {"Student": name, "Attendance": "Present" if name in present else "Absent"}
            for name in SAMPLE_STUDENTS
        ])
