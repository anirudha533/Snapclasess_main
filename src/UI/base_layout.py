import streamlit as st 

def style_background_home():

    st.markdown("""
        <style>
                .stApp{
                background:#5865F2 !important;
                
                }
                .stApp div[data-testid="stColumn"] {
                    background-color: #E0E3FF !important;
                    padding: 2rem 1.5rem !important;
                    border-radius: 3rem;
                    }
                .stApp div[data-testid="stColumn"] img {
                    width:220px !important;
                    height:380px !important;
                    object-fit:contain;
                    }
                .stApp .block-container {
                    max-width: 1000px !important;
                    }
                .stApp div[data-testid="stColumn"] h2 {
                    color:#000000 !important;
                    font-size:2rem !important;
                    text-align:center;
                    white-space:nowrap;
                    }
        </style>        


                """
                ,unsafe_allow_html=True)
    
def style_base_layout():

    st.markdown("""
        <style>
                @import url('https://fonts.googleapis.com/css2?family=Climate+Crisis:YEAR@1979&display=swap');
                @import url('https://fonts.googleapis.com/css2?family=Climate+Crisis:YEAR@1979&family=Outfit:wght@100..900&display=swap');
                /* Hide top bar of streamlit */
                 #MainMenu,footer,header{
                visibility:hidden;
                }
                .block-container{
                padding-top:1.5rem !important;
                }
                h1 {
                font-family: "Climate Crisis",sans-serif !important;
                font-size :3.5rem !important;
                line-height:1.1 !important;
                margin-bottom:0rem !important;
                
                }
                 h2 {
                font-family: "Climate Crisis",sans-serif !important;
                font-size :3.5rem !important;
                line-height:1.1 !important;
                margin-bottom:0rem !important;
                
                }
                h3,h4,p{
                  font-family:"Outfit",sans-serif;
                }
                button{
                border-radius:1.5rem !important;
                color:white !important;
                padding:10px 20px !important;
                border:none !important;
                transition: transform 0.25s ease-in-out !important;
                background:#5865F2 !important;
                }
                button[kind="secondary"]{
                border-radius:1.5rem !important;
                color:white !important;
                padding:10px 20px !important;
                border:none !important;
                transition: transform 0.25s ease-in-out !important;
                background:#EB459E !important;
                }
                button[kind="tertiary"]{
                border-radius:1.5rem !important;
                color:white !important;
                padding:10px 20px !important;
                border:none !important;
                transition: transform 0.25s ease-in-out !important;
                background:black!important;}

                button:hover{
                transform:scale(1.05)}
        </style>        


                """
                ,unsafe_allow_html=True)

PORTAL_INPUT_STYLES = """
<style>
:is(.st-key-student_portal, .st-key-teacher_portal) [data-baseweb="input"] {
    color-scheme: light;
    border-color: #A7A6CA !important;
    border-radius: .55rem;
}
:is(.st-key-student_portal, .st-key-teacher_portal)
:is([data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="input"] input) {
    background-color: #F7F7FF !important;
    color: #171730 !important;
}
:is(.st-key-student_portal, .st-key-teacher_portal) [data-baseweb="input"] input {
    -webkit-text-fill-color: #171730;
    caret-color: #4438B7;
}
:is(.st-key-student_portal, .st-key-teacher_portal) [data-baseweb="input"] input::placeholder {
    color: #5A5975;
    -webkit-text-fill-color: #5A5975;
    opacity: 1;
}
:is(.st-key-student_portal, .st-key-teacher_portal) [data-testid="InputInstructions"] {
    color: #5A5975;
}
:is(.st-key-student_portal, .st-key-teacher_portal) [data-baseweb="input"]:focus-within {
    outline: 2px solid #5149C3;
    outline-offset: 1px;
}
</style>
"""
