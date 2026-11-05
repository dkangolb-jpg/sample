import os
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client

load_dotenv()

st.set_page_config(page_title="가게 이름으로 찾기")

KST = timezone(timedelta(hours=9))

MODEL = "gemini-3.5-flash-lite"

AREA_INSTRUCTION = (
    "너는 여행객에게 지금 있는 지역의 음식점을 알려 주는 도우미다. "
    "확실히 아는 실제 가게만 적고, 없는 가게를 지어내지 않는다. "
    "알려 준 시각에 문을 열었을 음식점 5~10곳을 세로 목록으로 적고, 한 줄에 가게 이름과 짧은 위치만 쓴다. "
    "리뷰 문장은 옮기거나 요약하지 않는다."
)

PRD_PATH = Path(__file__).with_name("PRD.md")

# 챗봇 지시문은 이 파일에서 읽는다. 질문마다 다시 읽으므로 파일을 고치면 바로 반영된다
CHATBOT_INSTRUCTION_PATH = Path(__file__).with_name("chatbot-instruction.txt")

# 챗봇 창에서 고를 수 있는 말투. 맨 앞이 처음 골라져 있는 말투다
CHATBOT_TONES = {
    "친절한 존댓말": "'~해요'로 끝나는 부드러운 존댓말로 답한다.",
    "짧고 간단하게": "'~합니다'로 끝나는 존댓말로, 꾸미는 말 없이 문장마다 짧게 답한다.",
    "친구처럼 반말": "친한 친구에게 말하듯 '~해', '~야'로 끝나는 반말로 답한다.",
}

# 오른쪽 아래에 떠 있는 동그란 챗봇 아이콘
CHATBOT_CSS = """
<style>
.st-key-chatbot {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 1000;
    width: auto;
}
.st-key-chatbot [data-testid="stPopoverButton"] {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
}
.st-key-chatbot [data-testid="stPopoverButton"] [data-testid="stIconEmoji"] {
    font-size: 32px;
}
.st-key-chatbot [data-testid="stPopoverButton"] [data-testid="stIconMaterial"] {
    display: none;
}
</style>
"""


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


@st.cache_resource
def get_ai_client():
    # GEMINI_API_KEY 는 환경 변수에서 알아서 읽는다. 답이 60초 안에 안 오면 멈춘다
    return genai.Client(http_options=types.HttpOptions(timeout=60_000))


def is_open(store, now):
    if not store["open_time"] or not store["close_time"]:
        return False
    open_at = time.fromisoformat(store["open_time"])
    close_at = time.fromisoformat(store["close_time"])
    if open_at <= close_at:
        return open_at <= now < close_at
    # 자정을 넘겨 닫는 가게 (예: 18:00 ~ 02:00)
    return now >= open_at or now < close_at


def total_score(store):
    ratings = [Decimal(str(r)) for r in (store["naver_rating"], store["kakao_rating"]) if r is not None]
    if not ratings:
        return None
    return (sum(ratings) / len(ratings)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def save_ai_log(kind, input_text, output_text):
    # AI 에 넣은 것과 받은 답을 ai_logs 표에 남긴다. 남기지 못해도 답은 그대로 보여 준다
    try:
        get_client().table("ai_logs").insert(
            {"kind": kind, "model": MODEL, "input": input_text, "output": output_text}
        ).execute()
    except Exception as e:
        st.caption(f"기록을 남기지 못했어요 : {e}")


@st.fragment
def chatbot():
    # 대화를 주고받아도 이 부분만 다시 그려서, 화면 1·2 의 내용은 그대로 남는다
    st.html(CHATBOT_CSS)
    with st.container(key="chatbot"):
        with st.popover("", icon="🐣", help="서비스에 대해 물어보세요"):
            st.markdown("**가게 이름으로 찾기 · 챗봇**")
            tone = st.selectbox("말투", list(CHATBOT_TONES), key="chatbot_tone")
            history = st.container(height=320)
            with history:
                with st.chat_message("assistant", avatar="🐣"):
                    st.write("안녕하세요! 이 서비스에 대해 궁금한 걸 물어보세요")
                for msg in st.session_state.chat:
                    with st.chat_message(msg["role"], avatar="🐣" if msg["role"] == "assistant" else None):
                        # 마크다운은 줄 하나만 바꾸면 이어 붙이므로, 줄 끝에 빈칸 두 개를 붙여 줄바꿈을 살린다
                        st.write(msg["content"].replace("\n", "  \n"))

            question = st.chat_input("물어볼 말", key="chatbot_input", submit_mode="disable")
            if not question:
                return
            if not os.environ.get("GEMINI_API_KEY", "").strip():
                st.warning("GEMINI_API_KEY 가 비어 있어요. .env 에 값을 넣어 주세요")
                return

            with history:
                with st.chat_message("user"):
                    st.write(question)
                with st.chat_message("assistant", avatar="🐣"):
                    with st.spinner("답을 기다리는 중이에요"):
                        options = {}
                        if st.session_state.chat_id:
                            options["previous_interaction_id"] = st.session_state.chat_id
                        try:
                            interaction = get_ai_client().interactions.create(
                                model=MODEL,
                                # 대화가 이어져도 system_instruction 은 매번 다시 보내야 한다
                                system_instruction=CHATBOT_INSTRUCTION_PATH.read_text(encoding="utf-8")
                                + f"\n## 고른 말투 : {tone}\n{CHATBOT_TONES[tone]}\n"
                                + "\n<PRD>\n"
                                + PRD_PATH.read_text(encoding="utf-8")
                                + "\n</PRD>",
                                input=question,
                                **options,
                            )
                        except Exception as e:
                            st.error(f"Gemini 에서 답을 받지 못했어요 : {e}")
                            return
                    st.write(interaction.output_text.replace("\n", "  \n"))
                    save_ai_log("챗봇", f"[{tone}] {question}", interaction.output_text)

            st.session_state.chat_id = interaction.id
            st.session_state.chat += [
                {"role": "user", "content": question},
                {"role": "assistant", "content": interaction.output_text},
            ]


supabase = get_client()

if "screen" not in st.session_state:
    st.session_state.screen = 1
if "chat" not in st.session_state:
    st.session_state.chat = []
    st.session_state.chat_id = None

chatbot()

if st.session_state.screen == 1:
    # 화면 1 · 넣는 화면
    st.title("가게 이름으로 찾기")

    name = st.text_input("가게 이름", placeholder="예) 행복분식").strip()
    searched = st.button("검색", use_container_width=True)

    if searched and not name:
        st.warning("가게 이름을 입력해 주세요")
    elif searched:
        found = (
            supabase.table("stores")
            .select("name, open_time, close_time, naver_rating, kakao_rating")
            .ilike("name", f"%{name}%")
            .execute()
            .data
        )
        if found:
            st.session_state.found = found
            st.session_state.screen = 2
            st.rerun()
        st.warning(f"'{name}'라는 가게를 찾지 못했어요. 이름을 다시 확인해 주세요")

    st.divider()

    area = st.text_input("지금 있는 지역", placeholder="예) 강릉 중앙동").strip()
    area_asked = st.button("내 지역 가게 보기", use_container_width=True)

    if area_asked and not area:
        st.warning("지금 있는 지역을 입력해 주세요")
    elif area_asked and not os.environ.get("GEMINI_API_KEY", "").strip():
        st.warning("GEMINI_API_KEY 가 비어 있어요. .env 에 값을 넣어 주세요")
    elif area_asked:
        now = datetime.now(KST).strftime("%H:%M")
        area_input = f"지역 : {area}\n지금 시각 : {now}"
        with st.spinner("AI 가 가게를 찾는 중이에요"):
            try:
                interaction = get_ai_client().interactions.create(
                    model=MODEL,
                    system_instruction=AREA_INSTRUCTION,
                    input=area_input,
                )
            except Exception as e:
                st.error(f"Gemini 에서 답을 받지 못했어요 : {e}")
            else:
                st.write(interaction.output_text)
                save_ai_log("내 지역 가게 보기", area_input, interaction.output_text)
                st.caption("AI 가 알고 있는 내용으로 만든 목록이라 실제 영업 여부와 다를 수 있어요")
                usage = interaction.usage
                if usage:
                    st.caption(
                        f"쓴 토큰 : 모두 {usage.total_tokens or 0}"
                        f" (보낸 말 {usage.total_input_tokens or 0} · 받은 답 {usage.total_output_tokens or 0})"
                    )

else:
    # 화면 2 · 나오는 화면
    title_col, back_col = st.columns([3, 1], vertical_alignment="center")
    title_col.title("검색 결과")
    if back_col.button("다시 검색하기"):
        st.session_state.screen = 1
        st.rerun()

    now = datetime.now(KST).time()
    stores = [s for s in st.session_state.found if is_open(s, now)]
    stores.sort(key=lambda s: total_score(s) or 0, reverse=True)
    stores = stores[:10]

    st.caption(f"영업 중 · {len(stores)}곳")

    for store in stores:
        score = total_score(store)
        with st.container(border=True):
            name_col, score_col = st.columns([3, 1])
            name_col.write(store["name"])
            score_col.write(f"통합 점수 {score}" if score is not None else "통합 점수 없음")
