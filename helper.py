import os

import streamlit as st
from env_keys import load_keys
from google import genai
from google.genai import types
from supabase import create_client

load_keys()

st.set_page_config(page_title="챗봇")

MODEL = "gemini-3.5-flash-lite"


@st.cache_resource
def get_client():
    # GEMINI_API_KEY 는 환경 변수에서 알아서 읽는다. 답이 60초 안에 안 오면 멈춘다
    return genai.Client(http_options=types.HttpOptions(timeout=60_000))


@st.cache_resource
def get_log_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


def save_ai_log(owner, input_text, output_text):
    # AI 에 넣은 것과 받은 답을 가게 이름 칸의 이름과 함께 ai_logs 표에 남긴다. 남기지 못해도 답은 그대로 보여 준다
    # 이 화면에는 가게 검색이 없어서, owner 에 적을 가게 이름을 칸에 직접 넣는다
    if not owner:
        st.warning("가게 이름이 비어 있어 기록을 남기지 않았어요. 가게 이름을 입력해 주세요")
        return
    try:
        get_log_client().table("ai_logs").insert(
            {"kind": "helper 챗봇", "model": MODEL, "input": input_text, "output": output_text, "owner": owner}
        ).execute()
    except Exception as e:
        st.caption(f"기록을 남기지 못했어요 : {e}")


st.title("챗봇")

owner = st.text_input("가게 이름", placeholder="예) 행복분식 · 이 대화 기록을 묶어 둘 가게 이름").strip()

if not os.environ.get("GEMINI_API_KEY", "").strip():
    st.warning("GEMINI_API_KEY 가 비어 있어요. .env 에 값을 넣어 주세요")
    st.stop()

if "chat" not in st.session_state:
    st.session_state.chat = []
    st.session_state.chat_id = None

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("예) 여행지에서 맛집 고르는 요령 알려 줘", submit_mode="disable")

if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        # 앞 대화의 번호를 함께 보내면 Gemini 가 앞에서 나눈 말을 이어서 답한다
        options = {}
        if st.session_state.chat_id:
            options["previous_interaction_id"] = st.session_state.chat_id
        with st.spinner("답을 기다리는 중이에요"):
            try:
                interaction = get_client().interactions.create(model=MODEL, input=question, **options)
            except Exception as e:
                st.error(f"Gemini 에서 답을 받지 못했어요 : {e}")
                st.stop()
        st.write(interaction.output_text)
        save_ai_log(owner, question, interaction.output_text)
        usage = interaction.usage
        if usage:
            st.caption(
                f"쓴 토큰 : 모두 {usage.total_tokens or 0}"
                f" (보낸 말 {usage.total_input_tokens or 0} · 받은 답 {usage.total_output_tokens or 0})"
            )

    st.session_state.chat_id = interaction.id
    st.session_state.chat += [
        {"role": "user", "content": question},
        {"role": "assistant", "content": interaction.output_text},
    ]
