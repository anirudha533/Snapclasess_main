import streamlit as st

def header_home():
    logo_url = "https://i.pinimg.com/736x/65/25/ea/6525ea3430a2145e472ce030dd98bdcb.jpg"
    st.markdown(f"""
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; margin-bottom:30px; margin-top:30px">
            <img src='{logo_url}' style='height:100px;' />
            <h1 style='text-align:center; color:#E0E3FF'>SNAP<br/>CLASS</h1>
        </div>
        """, unsafe_allow_html=True)    