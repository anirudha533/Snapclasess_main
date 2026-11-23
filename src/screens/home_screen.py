import streamlit as st
from src.screens.components.header import header_home   
from src.UI.base_layout import style_base_layout,style_background_home
from src.screens.components.footer import footer_home 

def home_screen():
    header_home()
    

    style_background_home()
    style_base_layout()
    
    col1, col2 = st.columns(2)

    with col1, st.container(horizontal_alignment="center"):
        st.header("I'm Teacher")
        st.image("https://images.rawpixel.com/image_png_800/cHJpdmF0ZS9sci9pbWFnZXMvd2Vic2l0ZS8yMDIzLTA4L3Jhd3BpeGVsX29mZmljZV8zMF8zZF9yZW5kZXJfY2hhcmFjdGVyX29mX3RlYWNoZXJfY3V0ZV9jYXJ0b29uX180Y2Q0YmExMS02MDU1LTQ3OWEtYTc1Yy1kNGJkOWMxNmU5MWFfMS5wbmc.png", width=220, alt="Cartoon teacher")
        if st.button('Teacher Portal'):
            st.session_state['login_type'] = 'teacher'
            st.rerun()

    with col2, st.container(horizontal_alignment="center"):
        st.header("I'm Student")
        st.image("https://img.magnific.com/premium-photo/png-junior-student-cartoon-white-background-achievement_53876-753391.jpg?semt=ais_hybrid&w=740&q=80", width=220, alt="Cartoon student")
        if st.button('Student Portal'):
            st.session_state['login_type'] = 'student'
            st.rerun()
    footer_home()        