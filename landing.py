"""첫 화면 · 서비스를 소개하고 「시작하기」 버튼으로 기능 화면(화면 1)에 보낸다.

색은 이 화면에만 입힌다. 아래 CSS 는 첫 화면이 그려질 때만 들어가고,
기능 화면으로 넘어가면 함께 빠지므로 기능 화면 색은 그대로다.
"""

import streamlit as st

BACKGROUND = "#F6F3EC"
TEXT = "#343B32"
ACCENT = "#D97845"

LANDING_CSS = f"""
<style>
.stApp, [data-testid="stHeader"] {{
    background-color: {BACKGROUND};
}}
.stApp h1, .stApp h3, .stApp p, .stApp li {{
    color: {TEXT};
}}
.stApp h1 {{
    font-size: 3rem;
    line-height: 1.2;
}}
.st-key-landing_intro p {{
    font-size: 1.2rem;
}}
[class*="st-key-landing_card_"] {{
    border: 1px solid rgba(52, 59, 50, 0.18);
    border-radius: 12px;
    padding: 1.25rem;
    background-color: rgba(255, 255, 255, 0.55);
}}
[class*="st-key-landing_card_"] [data-testid="stIconMaterial"] {{
    color: {ACCENT};
}}
.stApp [data-testid="stCaptionContainer"] {{
    color: rgba(52, 59, 50, 0.7);
}}
.st-key-landing_start button {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    padding: 0.6rem 2rem;
}}
.st-key-landing_start button:hover {{
    background-color: {ACCENT};
    border-color: {TEXT};
}}
.st-key-landing_start button p {{
    color: #FFFFFF;
    font-size: 1.2rem;
    font-weight: 700;
}}
</style>
"""

# 하는 일 세 가지 · (아이콘, 짧은 이름, 설명, 아직 만들지 않은 기능인지)
FEATURES = [
    (":material/star:", "통합 점수", "네이버 별점과 카카오 별점을 하나의 점수로 합쳐서 보여 줍니다.", False),
    (":material/schedule:", "영업 중인 가게", "지금 영업 중인 가게만 세로 목록으로 보여 줍니다.", False),
    (":material/map:", "지도로 보기", "현재 위치에서 반경 1.5km 이내의 가게를 지도 위에 표시합니다.", True),
]


def show_landing():
    """첫 화면을 그리고, 「시작하기」를 눌렀으면 True 를 돌려준다."""
    st.html(LANDING_CSS)

    st.title("가게 이름으로 찾기", anchor=False)
    with st.container(key="landing_intro"):
        # PRD.md 의 한 줄 정의를 그대로 쓴다
        st.markdown("여행하며 현재 위치하고 있는 지역의 지도상에서 맛집을 골라 찾아갈 수 있는 서비스.")

    st.space("medium")

    with st.container(horizontal=True, gap="medium"):
        for number, (icon, name, body, coming) in enumerate(FEATURES, start=1):
            with st.container(key=f"landing_card_{number}"):
                st.subheader(f"{icon} {name}", anchor=False)
                st.markdown(body)
                if coming:
                    st.caption("준비 중")

    st.space("medium")

    return st.button(
        "시작하기",
        type="primary",
        icon=":material/arrow_forward:",
        icon_position="right",
        key="landing_start",
    )
