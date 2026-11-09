import os
from datetime import datetime, timedelta, timezone

import streamlit as st
from env_keys import load_keys
from supabase import create_client

load_keys()

st.set_page_config(page_title="AI 기록")

KST = timezone(timedelta(hours=9))

# app.py · helper.py 에서 save_ai_log 로 남기는 kind 값
KINDS = ["모두", "챗봇", "내 지역 가게 보기", "helper 챗봇"]


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


supabase = get_client()

st.title("AI 기록")

owner = st.text_input("이름", placeholder="기록을 남길 때 넣은 이름").strip()
kind = st.selectbox("어디서 물었나", KINDS)

if not owner:
    st.warning("이름을 입력해 주세요. 그 이름으로 남긴 기록만 보여 드려요")
    st.stop()

# 이름 칸의 이름과 owner 가 같은 줄만 받는다
query = supabase.table("ai_logs").select("created_at, kind, model, input, output").eq("owner", owner)
if kind != "모두":
    query = query.eq("kind", kind)
try:
    rows = query.order("created_at", desc=True).limit(50).execute().data
except Exception as e:
    st.error(f"Supabase 에서 기록을 받지 못했어요 : {e}")
    st.stop()

if not rows:
    st.caption("아직 남은 기록이 없어요")

for row in rows:
    # Supabase 는 UTC 로 돌려주므로 한국 시각으로 바꿔 보여 준다
    at = datetime.fromisoformat(row["created_at"]).astimezone(KST).strftime("%Y-%m-%d %H:%M")
    with st.container(border=True):
        st.caption(f"{at} · {row['kind']} · {row['model']}")
        st.markdown("**넣은 것**")
        st.text(row["input"])
        st.markdown("**받은 답**")
        st.text(row["output"])
