import os

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

st.set_page_config(page_title="한 줄 방명록")


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


supabase = get_client()

st.title("한 줄 방명록")

with st.form("write", clear_on_submit=True):
    message = st.text_input("한 줄 남기기", max_chars=100)
    submitted = st.form_submit_button("남기기", use_container_width=True)

if submitted:
    if message.strip():
        supabase.table("guestbook").insert({"message": message.strip()}).execute()
    else:
        st.warning("남길 말을 입력해 주세요")

rows = (
    supabase.table("guestbook")
    .select("message, created_at")
    .order("created_at", desc=True)
    .limit(50)
    .execute()
    .data
)

if not rows:
    st.caption("아직 남긴 글이 없어요")

for row in rows:
    with st.container(border=True):
        st.write(row["message"])
        st.caption(row["created_at"][:16].replace("T", " "))
