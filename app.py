
import streamlit as st

from src.screens.home_screen import home_screen
from src.screens.guest_demo_screen import guest_demo_screen



def main():
    if st.query_params.get('demo') == '1' and not st.query_params.get('join-code'):
        guest_demo_screen()
        return

    if 'login_type' not in st.session_state:
        st.session_state['login_type'] = 'student' if st.query_params.get('join-code') else None

    match st.session_state['login_type']:
        case 'teacher':
            from src.screens.teacher_screen import teacher_screen

            teacher_screen()
        case 'student':
            from src.screens.student_screen import student_screen

            student_screen()
        case None:
            home_screen()

main()
