import os
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import requests
import streamlit as st
from env_keys import load_keys
from google import genai
from google.genai import types
from supabase import create_client

from landing import show_landing

load_keys()

st.set_page_config(page_title="가게 이름으로 찾기")

KST = timezone(timedelta(hours=9))

MODEL = "gemini-3.5-flash-lite"

AREA_INSTRUCTION = (
    "너는 여행객에게 지금 있는 지역의 음식점을 알려 주는 도우미다. "
    "확실히 아는 실제 가게만 적고, 없는 가게를 지어내지 않는다. "
    "알려 준 시각에 문을 열었을 음식점 5~10곳을 세로 목록으로 적고, 한 줄에 가게 이름과 짧은 위치만 쓴다. "
    "리뷰 문장은 옮기거나 요약하지 않는다."
)

# 카카오 로컬 API 키워드 검색 : https://developers.kakao.com/docs/ko/local/dev-guide
# 응답에 별점과 영업시간이 없어, 카카오에서만 찾은 가게는 통합 점수를 낼 수 없다
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_RESTAURANT_CODE = "FD6"  # 카카오 카테고리 코드 : 음식점
KAKAO_MAX_PLACES = 10  # 화면 2 세로 목록에 맞춰 최대 10곳만 받는다
KAKAO_ERRORS = {
    401: "카카오가 키를 받아 주지 않았어요. .env 의 KAKAO_REST_API_KEY 가 REST API 키인지 확인해 주세요.",
    403: "카카오맵 API 를 쓸 수 없는 앱이에요. 카카오 개발자 콘솔의 [카카오맵] > [사용 설정] 상태를 ON 으로 바꿔 주세요.",
    429: "카카오 무료 사용량을 다 썼어요. 카카오 개발자 콘솔의 [통계] > [쿼터] 에서 확인해 주세요.",
}

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


class KakaoError(Exception):
    pass


def search_kakao(name):
    """가게 이름으로 카카오에서 음식점을 찾는다. 지역을 정하지 않아 전국에서 정확도 순으로 받는다."""
    api_key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if not api_key:
        raise KakaoError(".env 에서 KAKAO_REST_API_KEY 를 찾지 못했어요.")
    try:
        response = requests.get(
            KAKAO_KEYWORD_URL,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params={
                "query": name,
                "category_group_code": KAKAO_RESTAURANT_CODE,
                "sort": "accuracy",
                "size": KAKAO_MAX_PLACES,
            },
            timeout=10,
        )
    except requests.RequestException as error:
        raise KakaoError("카카오에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 검색해 주세요.") from error
    if response.status_code != 200:
        message = KAKAO_ERRORS.get(response.status_code, "카카오 검색에 실패했어요.")
        raise KakaoError(f"{message} (응답 코드 {response.status_code})")
    return [
        # 도로명 주소가 없는 가게는 지번 주소를 쓴다
        {"name": doc["place_name"], "address": doc["road_address_name"] or doc["address_name"]}
        for doc in response.json()["documents"]
    ]


def total_score(store):
    ratings = [Decimal(str(r)) for r in (store["naver_rating"], store["kakao_rating"]) if r is not None]
    if not ratings:
        return None
    return (sum(ratings) / len(ratings)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def save_search_log(name, output_text):
    # 가게 이름으로 검색할 때마다 ai_logs 표에 한 줄 남기고, owner 에 검색한 가게 이름을 적는다
    # 남기지 못해도 검색은 그대로 하고, 안내는 다음에 그려지는 가게 찾기 탭 맨 위에 띄운다
    try:
        get_client().table("ai_logs").insert(
            {"kind": "가게 검색", "model": "AI 안 씀", "input": name, "output": output_text, "owner": name}
        ).execute()
    except Exception as e:
        st.session_state.search_log_error = f"검색 기록을 남기지 못했어요 : {e}"


SEARCH_HISTORY_SIZE = 10  # 사이드바에 보여 줄 검색했던 가게 이름 수

# 버튼 글자는 마크다운으로 읽히므로, 가게 이름 속 이 글자들은 앞에 \ 를 붙여 글자 그대로 보이게 한다
MARKDOWN_CHARS = "\\`*_[]~#$:"


def search_again(name):
    # 사이드바에서 검색했던 가게를 누르면, 그 이름을 가게 이름 칸에 넣고 "검색"을 누른 것처럼 한다
    st.session_state.store_name = name
    st.session_state.search_again = True


def show_search_history():
    # ai_logs 표의 "가게 검색" 줄에서 최근에 검색한 가게 이름을 겹치지 않게 골라 사이드바에 보여 준다
    st.subheader("검색했던 가게", anchor=False)
    try:
        rows = (
            get_client()
            .table("ai_logs")
            .select("owner, created_at")
            .eq("kind", "가게 검색")
            .order("created_at", desc=True)
            .limit(SEARCH_HISTORY_SIZE * 5)
            .execute()
            .data
        )
    except Exception as e:
        st.caption(f"검색 기록을 불러오지 못했어요 : {e}")
        return
    # 같은 이름을 여러 번 검색했으면 가장 최근 것 하나만 남긴다
    latest = {}
    for row in rows:
        if row["owner"] and row["owner"] not in latest:
            latest[row["owner"]] = row["created_at"]
    if not latest:
        st.caption("아직 검색한 가게가 없어요")
        return
    for owner, created_at in list(latest.items())[:SEARCH_HISTORY_SIZE]:
        # Supabase 는 UTC 로 돌려주므로 한국 시각으로 바꿔 보여 준다
        at = datetime.fromisoformat(created_at).astimezone(KST).strftime("%m-%d %H:%M")
        label = "".join(f"\\{ch}" if ch in MARKDOWN_CHARS else ch for ch in owner)
        st.button(
            f"{label}  ·  {at}",
            key=f"history_{owner}",
            icon=":material/history:",
            type="tertiary",
            help="이 이름으로 다시 검색해요",
            on_click=search_again,
            args=(owner,),
        )


def save_ai_log(kind, input_text, output_text):
    # AI 에 넣은 것과 받은 답을 마지막으로 검색한 가게 이름과 함께 ai_logs 표에 남긴다. 남기지 못해도 답은 그대로 보여 준다
    owner = st.session_state.get("last_search", "").strip()
    if not owner:
        st.warning("검색한 가게 이름이 없어 기록을 남기지 않았어요. 먼저 가게 이름으로 검색해 주세요")
        return
    try:
        get_client().table("ai_logs").insert(
            {"kind": kind, "model": MODEL, "input": input_text, "output": output_text, "owner": owner}
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


def show_login():
    # 구글 계정으로 들어오기 전에만 그린다. 구글 키는 .streamlit/secrets.toml 의 [auth] · [auth.google] 에서 읽는다
    st.title("가게 이름으로 찾기", anchor=False)
    st.markdown("구글 계정으로 들어오면 서비스를 쓸 수 있어요.")
    if st.button("구글 계정으로 들어가기", type="primary", icon=":material/login:"):
        try:
            st.login("google")
        except Exception as e:
            st.error(f"구글 로그인을 시작하지 못했어요. .streamlit/secrets.toml 의 [auth] 값을 확인해 주세요 : {e}")


def show_user_bar():
    # 모든 화면 맨 위 오른쪽에 들어온 사람의 이름과 로그아웃 버튼을 둔다. 이름이 없으면 이메일을 보여 준다
    who = st.user.get("name") or st.user.get("email") or "이름 없음"
    who = "".join(f"\\{ch}" if ch in MARKDOWN_CHARS else ch for ch in who)
    with st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
        st.markdown(f":material/account_circle: **{who}** 님")
        if st.button("로그아웃", type="tertiary", icon=":material/logout:"):
            st.logout()


def is_admin():
    # 들어온 사람의 메일이 secrets.toml 맨 위 ADMIN_EMAILS 목록에 있으면 관리자다. 목록이 없거나 못 읽으면 아무도 관리자가 아니다
    email = (st.user.get("email") or "").strip().lower()
    if not email:
        return False
    try:
        admins = st.secrets.get("ADMIN_EMAILS", [])
    except Exception:
        return False
    # "a@x.com, b@x.com" 처럼 글자 하나로 적어 두어도 목록으로 읽는다
    if isinstance(admins, str):
        admins = admins.split(",")
    return email in {str(a).strip().lower() for a in admins}


def show_admin():
    # 관리 화면 · 관리자가 아니면 아무것도 그리지 않는다 (버튼을 숨기는 것과 따로 한 번 더 막는다)
    if not is_admin():
        return
    st.write("관리자만 보는 화면입니다")
    # 들어오기 전 화면(화면 1 또는 화면 2)으로 돌아간다
    if st.button("돌아가기", icon=":material/arrow_back:"):
        st.session_state.screen = st.session_state.pop("screen_before_admin", 1)
        st.rerun()


# 구글 계정으로 들어와야 첫 화면부터 모든 화면이 보인다
# secrets.toml 에 [auth] 가 아직 없으면 is_logged_in 값 자체가 없으므로 .get 으로 읽어 들어오지 않은 것으로 본다
if not st.user.get("is_logged_in"):
    show_login()
    st.stop()

show_user_bar()

# 첫 화면 · 앱을 열면 먼저 뜨고, 「시작하기」를 누르면 화면 1 로 간다
if not st.session_state.get("started"):
    if show_landing():
        st.session_state.started = True
        st.session_state.screen = 1
        st.rerun()
    st.stop()

# 화면 1·2 의 사이드바 · 첫 화면으로 돌아가는 버튼
with st.sidebar:
    if st.button("첫 화면으로 돌아가기", icon=":material/home:", width="stretch"):
        st.session_state.started = False
        st.rerun()

# 관리자에게만 사이드바에 「관리」 버튼을 보여 준다
admin = is_admin()
if admin:
    with st.sidebar:
        if st.button("관리", icon=":material/admin_panel_settings:", width="stretch"):
            # 「돌아가기」 로 다시 갈 수 있게 들어오기 전 화면을 기억해 둔다
            if st.session_state.get("screen") != "admin":
                st.session_state.screen_before_admin = st.session_state.get("screen", 1)
            st.session_state.screen = "admin"
            st.rerun()

# 관리 화면 · 관리자가 아니면 화면 1 로 돌려보내고 관리 화면의 코드는 돌지 않는다
if st.session_state.get("screen") == "admin":
    if admin:
        show_admin()
        st.stop()
    st.session_state.screen = 1

supabase = get_client()

if "screen" not in st.session_state:
    st.session_state.screen = 1
if "chat" not in st.session_state:
    st.session_state.chat = []
    st.session_state.chat_id = None

chatbot()

# 가게 찾기 결과 칸의 맨 위 한 줄에 띄울 안내. (종류, 문구) 꼴이다
notice = None

# 제목과 넣는 칸 · 화면 1 과 화면 2 가 같은 자리를 쓴다
st.title("가게 이름으로 찾기" if st.session_state.screen == 1 else "검색 결과")
if st.session_state.screen == 2:
    input_area, back_area = st.columns([5, 1], vertical_alignment="bottom")
else:
    input_area, back_area = st.container(), None

with input_area:
    # 폼으로 묶어서, 입력 칸에서 엔터를 쳐도 "검색"을 누른 것처럼 검색한다
    with st.form("search_form", border=False):
        name_col, button_col = st.columns([4, 1], vertical_alignment="bottom")
        name = name_col.text_input("가게 이름", placeholder="예) 행복분식", key="store_name").strip()
        searched = button_col.form_submit_button("검색", use_container_width=True)
    # 사이드바의 검색했던 가게를 눌렀을 때도 검색한 것으로 친다
    searched = st.session_state.pop("search_again", False) or searched

if back_area is not None and back_area.button("다시 검색하기", use_container_width=True):
    st.session_state.screen = 1
    st.rerun()

if searched:
    # 검색하면 결과가 보이는 "가게 찾기" 탭으로 돌아온다
    st.session_state.main_tab = "가게 찾기"

if searched and not name:
    notice = ("warning", "가게 이름을 입력해 주세요")
elif searched:
    found = (
        supabase.table("stores")
        .select("name, open_time, close_time, naver_rating, kakao_rating")
        .ilike("name", f"%{name}%")
        .execute()
        .data
    )
    kakao_error = None
    try:
        with st.spinner("카카오에서 찾는 중이에요"):
            kakao = search_kakao(name)
    except KakaoError as error:
        kakao, kakao_error = [], str(error)
    # stores 표에 이미 있는 가게는 통합 점수가 있는 왼쪽 목록에만 보여 준다
    known = {s["name"] for s in found}
    kakao = [p for p in kakao if p["name"] not in known]

    # 검색한 가게 이름을 기록으로 남기고, 뒤에 AI 기록을 남길 때 owner 로 쓰도록 기억해 둔다
    st.session_state.last_search = name
    if kakao_error:
        search_result = f"우리 표 {len(found)}곳 · 카카오 오류 : {kakao_error}"
    else:
        search_result = f"우리 표 {len(found)}곳 · 카카오 {len(kakao)}곳"
    save_search_log(name, search_result)

    if found or kakao:
        st.session_state.found = found
        st.session_state.kakao = kakao
        st.session_state.kakao_error = kakao_error
        st.session_state.screen = 2
        st.rerun()
    if kakao_error:
        notice = ("error", kakao_error)
    else:
        notice = ("warning", f"'{name}'라는 가게를 찾지 못했어요. 이름을 다시 확인해 주세요")

# 화면 1·2 의 사이드바 · 방금 한 검색까지 들어가도록 검색을 마친 뒤에 그린다
with st.sidebar:
    show_search_history()


def show_open_stores(found):
    # stores 표에서 찾은 가게 가운데 지금 영업 중인 곳만 통합 점수와 함께 보여 준다
    now = datetime.now(KST).time()
    stores = [s for s in found if is_open(s, now)]
    stores.sort(key=lambda s: total_score(s) or 0, reverse=True)
    stores = stores[:10]

    st.caption(f"영업 중 · {len(stores)}곳")
    if not stores:
        st.info("현재 영업중인 가게가 없습니다.")
    for store in stores:
        score = total_score(store)
        with st.container(border=True):
            name_col, score_col = st.columns([3, 1])
            name_col.write(store["name"])
            score_col.write(f"통합 점수 {score}" if score is not None else "통합 점수 없음")


def show_kakao_places(kakao):
    st.subheader("카카오에서 찾은 가게", anchor=False)
    st.caption(f"{len(kakao)}곳 · 별점과 영업시간 정보가 없어 통합 점수를 낼 수 없고, 영업 중인지 알 수 없어요")
    for place in kakao:
        with st.container(border=True):
            name_col, score_col = st.columns([3, 1])
            name_col.write(place["name"])
            name_col.caption(place["address"])
            score_col.write("통합 점수 없음")


find_tab, ai_tab = st.tabs(["가게 찾기", "AI 지역 추천"], key="main_tab", on_change="rerun")

with find_tab:
    # 안내 문구는 탭 맨 위 한 줄에 띄운다
    if notice:
        getattr(st, notice[0])(notice[1])
    if "search_log_error" in st.session_state:
        st.caption(st.session_state.pop("search_log_error"))

    if st.session_state.screen == 2:
        # 화면 2 · 나오는 화면
        if st.session_state.get("kakao_error"):
            st.error(st.session_state.kakao_error)

        found = st.session_state.found
        kakao = st.session_state.get("kakao", [])
        # 둘 다 있으면 왼쪽에 영업 중 목록, 오른쪽에 카카오 목록을 나란히 둔다
        if found and kakao:
            left, right = st.columns(2)
            with left:
                show_open_stores(found)
            with right:
                show_kakao_places(kakao)
        elif found:
            show_open_stores(found)
        elif kakao:
            show_kakao_places(kakao)

with ai_tab:
    # 가끔 쓰는 기능 · 지역 이름을 넣으면 AI 가 가게를 적어 준다
    with st.form("area_form", border=False):
        area = st.text_input("지금 있는 지역", placeholder="예) 강릉 중앙동").strip()
        area_asked = st.form_submit_button("내 지역 가게 보기", use_container_width=True)

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

st.caption("copyright by SIMON")
