import streamlit as st
from supabase import Client, ClientOptions, create_client


class DatabaseConfigurationError(RuntimeError):
    pass


@st.cache_resource
def get_supabase() -> Client:
    try:
        settings = st.secrets["supabase"]
        url = settings["url"].strip()
        key = settings["secret_key"].strip()
    except (FileNotFoundError, KeyError) as error:
        raise DatabaseConfigurationError("Supabase connection settings are missing.") from error

    if not url or not key:
        raise DatabaseConfigurationError("Supabase URL and server key are required.")

    return create_client(
        url, key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )
