import streamlit as st



def footer_home():
    st.markdown(
        """
        <div style="text-align:center; margin-top:40px; margin-bottom:20px;
                    color:#E0E3FF; font-family:'Outfit',sans-serif;">
            &copy; Created with ❤️ Anirudh. All rights reserved.
        </div>
        """,
        unsafe_allow_html=True,
    )
