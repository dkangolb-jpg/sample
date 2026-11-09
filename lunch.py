import os
from urllib.parse import quote

import altair as alt
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="맛집 찾기", layout="wide")

# 카카오 로컬 API 키워드 검색·주소 검색 : https://developers.kakao.com/docs/ko/local/dev-guide
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
NAVER_MAP_URL = "https://map.naver.com/p/search/"
RESTAURANT_CODE = "FD6"  # 카카오 카테고리 코드 : 음식점
PAGE_SIZE = 15  # 문서 기준 한 쪽 최대 개수
MAX_PLACES = 45  # 문서 기준 검색어 하나로 볼 수 있는 최대 개수 (pageable_count)

RADIUS_OPTIONS = [500, 1000, 1500, 3000]
BAR_COLOR = "#D97845"  # .streamlit/config.toml 의 강조색과 같다

# 화면에 보이는 정렬 이름 : (정렬할 칸, 오름차순 여부)
SORT_OPTIONS = {
    "카카오 정확도 순": ("정확도 순위", True),
    "가까운 순": ("거리", True),
    "먼 순": ("거리", False),
    "이름순": ("가게 이름", True),
    "종류순": ("종류", True),
}

KAKAO_ERRORS = {
    401: "카카오가 키를 받아 주지 않았어요. .env 의 KAKAO_REST_API_KEY 가 REST API 키인지 확인해 주세요.",
    403: "카카오맵 API 를 쓸 수 없는 앱이에요. 카카오 개발자 콘솔의 [카카오맵] > [사용 설정] 상태를 ON 으로 바꿔 주세요.",
    429: "카카오 무료 사용량을 다 썼어요. 카카오 개발자 콘솔의 [통계] > [쿼터] 에서 확인해 주세요.",
}


class KakaoError(Exception):
    pass


def call_kakao(url, params):
    """카카오를 부르는 곳은 여기뿐이다."""
    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise KakaoError(".env 에서 KAKAO_REST_API_KEY 를 찾지 못했어요.")

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params=params,
            timeout=10,
        )
    except requests.RequestException as error:
        raise KakaoError("카카오에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 검색해 주세요.") from error

    if response.status_code != 200:
        message = KAKAO_ERRORS.get(response.status_code, "카카오 검색에 실패했어요.")
        raise KakaoError(f"{message} (응답 코드 {response.status_code})")
    return response.json()


def find_center(place):
    """기준 장소를 카카오에서 찾는다. 이름·주소·좌표는 모두 카카오 응답 값이고, 못 찾으면 None 이다.

    주소 검색을 먼저 한다. 동네 이름을 키워드 검색에 넣으면 동네 안의 다른 곳이 나온다 ("서신동" → 하천 "삼천").
    역 이름은 주소 검색에 없어 키워드 검색으로 찾는다.
    """
    data = call_kakao(ADDRESS_URL, {"query": place, "size": 1})
    if data["documents"]:
        doc = data["documents"][0]
        address = doc["address_name"]
        return {
            # 지명이면 주소의 마지막 낱말이 이름이다 ("전북특별자치도 전주시 완산구 서신동" → "서신동")
            "name": address.split()[-1] if doc["address_type"] == "REGION" else address,
            "address": address,
            "x": doc["x"],
            "y": doc["y"],
            "same_name_count": data["meta"]["total_count"],
        }

    data = call_kakao(KEYWORD_URL, {"query": place, "size": 1})
    if data["documents"]:
        doc = data["documents"][0]
        return {
            "name": doc["place_name"],
            "address": doc["road_address_name"] or doc["address_name"],
            "x": doc["x"],
            "y": doc["y"],
            "same_name_count": 1,
        }
    return None


def search_places(query, center, radius):
    """기준 장소 둘레 반경 안의 음식점을 받아 온다.

    최대 45곳만 볼 수 있어, 가까운 순으로 받으면 기준 장소 바로 옆 가게만 온다 (전주 객사 반경 1500m 에서 45곳 모두 165m 안).
    그래서 정확도 순으로 받고 거리 정렬은 화면에서 한다.
    """
    params = {
        "query": query,
        "category_group_code": RESTAURANT_CODE,
        "x": center["x"],
        "y": center["y"],
        "radius": radius,
        "sort": "accuracy",
        "size": PAGE_SIZE,
    }
    documents = []
    total_count = 0
    for page in range(1, MAX_PLACES // PAGE_SIZE + 1):
        data = call_kakao(KEYWORD_URL, {**params, "page": page})
        documents.extend(data["documents"])
        total_count = data["meta"]["total_count"]
        if data["meta"]["is_end"]:
            break
    return documents, total_count


def to_table(documents):
    rows = []
    for rank, doc in enumerate(documents, start=1):
        # category_name 은 "음식점 > 한식 > 국밥" 꼴이다. 둘째 칸을 종류로 쓴다
        categories = doc["category_name"].split(" > ")
        # 도로명 주소가 없는 가게는 표와 같이 지번 주소를 쓴다
        address = doc["road_address_name"] or doc["address_name"]
        rows.append(
            {
                "정확도 순위": rank,
                "가게 이름": doc["place_name"],
                "종류": categories[1] if len(categories) > 1 else categories[0],
                "거리": int(doc["distance"]),
                "전화": doc["phone"],
                "주소": address,
                "카카오맵": doc["place_url"],
                # 이름에 띄어쓰기·# 같은 글자가 있어도 주소가 깨지지 않게 바꿔 붙인다
                "네이버 지도": NAVER_MAP_URL + quote(f"{doc['place_name']} {address}", safe=""),
            }
        )
    return pd.DataFrame(rows)


def category_chart(places):
    counts = places["종류"].value_counts().rename_axis("종류").reset_index(name="가게 수")
    return (
        alt.Chart(counts, height=alt.Step(28))
        .mark_bar(color=BAR_COLOR, cornerRadiusEnd=4, size=16)
        .encode(
            x=alt.X("가게 수:Q", title="가게 수", axis=alt.Axis(tickMinStep=1, tickCount=5, format="d")),
            y=alt.Y("종류:N", sort="-x", title=None),
            tooltip=["종류:N", "가게 수:Q"],
        )
    )


def distance_chart(places, center_name):
    bins = alt.Bin(maxbins=10)
    return (
        alt.Chart(places, height=280)
        .mark_bar(color=BAR_COLOR, cornerRadiusEnd=4, binSpacing=2)
        .encode(
            x=alt.X("거리:Q", bin=bins, title=f"{center_name}에서 떨어진 거리(m)"),
            y=alt.Y("count():Q", title="가게 수", axis=alt.Axis(tickMinStep=1, tickCount=5, format="d")),
            tooltip=[
                alt.Tooltip("거리:Q", bin=bins, title="거리(m)"),
                alt.Tooltip("count():Q", title="가게 수"),
            ],
        )
    )


def show_pick(places):
    with st.container(border=True):
        # 받아 둔 표 안에서만 고른다. 카카오를 부르지 않는다
        if st.button("맛집 뽑기", key="pick_button"):
            st.session_state["pick"] = places.sample(1).iloc[0].to_dict()
        pick = st.session_state.get("pick")
        if pick:
            st.header(pick["가게 이름"], anchor=False)
            st.subheader(f"{pick['종류']} · {pick['거리']}m", anchor=False)


def show_center(center):
    with st.container(border=True):
        st.markdown(f"**기준 장소 : {center['name']}**")
        st.caption(f"주소 : {center['address']}")
        if center["same_name_count"] > 1:
            st.caption(
                f"같은 이름이 {center['same_name_count']}곳 있어 카카오의 첫 번째 결과를 썼어요. "
                "다른 곳이면 '전주 중앙동'처럼 지역까지 함께 적어 주세요."
            )
        else:
            st.caption("카카오에서 찾은 값이에요. 다른 곳이면 지역까지 함께 적어 주세요.")


def show_result(result):
    places = result["places"]
    center = result["center"]
    show_center(center)
    if places.empty:
        st.warning(f"'{result['query']}'라는 가게를 찾지 못했어요. 이름을 다시 확인해 주세요")
        return

    caption = f"'{result['query']}' · 반경 {result['radius']}m 검색 결과"
    if result["total_count"] > len(places):
        caption += f" · 전체 {result['total_count']}곳 중 카카오 정확도가 높은 {len(places)}곳만 받아 왔어요"
    st.caption(caption)

    nearest = places.loc[places["거리"].idxmin()]
    with st.container(horizontal=True):
        st.metric("찾은 가게", f"{len(places)}곳", border=True)
        st.metric(f"가장 가까운 가게 ({nearest['거리']}m)", nearest["가게 이름"], border=True)
        st.metric("가장 많은 종류", places["종류"].mode()[0], border=True)

    show_pick(places)

    left, right = st.columns(2)
    with left:
        with st.container(border=True, height="stretch"):
            st.markdown("**종류별 가게 수**")
            st.altair_chart(category_chart(places), alt="음식 종류별 가게 수, 많은 종류부터")
    with right:
        with st.container(border=True, height="stretch"):
            st.markdown("**거리별 가게 수**")
            st.altair_chart(distance_chart(places, center["name"]), alt=f"{center['name']}에서 떨어진 거리별 가게 수")

    with st.container(border=True):
        st.markdown("**가게 목록**")
        sort_name = st.selectbox("정렬", list(SORT_OPTIONS), key="sort_name")
        column, ascending = SORT_OPTIONS[sort_name]
        st.dataframe(
            places.sort_values(column, ascending=ascending),
            column_config={
                "거리": st.column_config.NumberColumn("거리", format="%d m"),
                "카카오맵": st.column_config.LinkColumn("카카오맵", display_text="열기"),
                "네이버 지도": st.column_config.LinkColumn("네이버 지도", display_text="열기"),
            },
            hide_index=True,
            alt=f"{center['name']} 근처 가게 목록",
        )


st.title("맛집 찾기")
st.caption("카카오 로컬 API 응답에는 별점과 영업시간이 없어 거리와 종류로 보여 줍니다.")

with st.container(horizontal=True, vertical_alignment="bottom"):
    place = st.text_input("기준 장소 (역·동네 이름)", value="전주 객사", key="place")
    query = st.text_input("찾을 음식 또는 가게 이름", value="음식점", key="query")
    radius = st.selectbox(
        "반경",
        RADIUS_OPTIONS,
        index=RADIUS_OPTIONS.index(1500),
        format_func=lambda meters: f"{meters}m",
        key="radius",
    )
    searched = st.button("검색", type="primary")

# 카카오는 버튼을 누른 그 한 번만 부른다. 정렬·입력을 바꿔 다시 그릴 때는 받아 둔 결과를 쓴다
if searched:
    st.session_state.pop("result", None)
    st.session_state.pop("pick", None)
    place = place.strip()
    query = query.strip()
    if not place:
        st.warning("기준 장소를 입력해 주세요")
    elif not query:
        st.warning("가게 이름을 입력해 주세요")
    else:
        try:
            with st.spinner("카카오에서 찾는 중이에요..."):
                center = find_center(place)
                if center is None:
                    st.warning(f"'{place}'라는 장소를 찾지 못했어요. 이름을 다시 확인해 주세요")
                else:
                    documents, total_count = search_places(query, center, radius)
                    st.session_state["result"] = {
                        "query": query,
                        "center": center,
                        "radius": radius,
                        "places": to_table(documents),
                        "total_count": total_count,
                    }
        except KakaoError as error:
            st.error(str(error))

if "result" in st.session_state:
    show_result(st.session_state["result"])
elif not searched:
    st.info("검색 버튼을 누르면 카카오에서 찾아 옵니다.")
