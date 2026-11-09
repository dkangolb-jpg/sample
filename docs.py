import base64
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import streamlit as st
from env_keys import load_keys
from supabase import create_client

load_keys()

st.set_page_config(page_title="문서 보관함")

BUCKET = "docs"
DOC_TYPES = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "hwp", "hwpx", "txt", "csv", "md"]
# docs 버킷은 공개가 아니라서, 문서마다 잠깐만 열리는 내려받기 주소를 받는다
URL_SECONDS = 60
# 주소가 닫히기 전에 목록을 다시 그려 화면의 링크가 늘 열려 있게 한다
REFRESH_SECONDS = 50
# 원래 이름은 Storage 이름 안에 이 표시 뒤에 숨겨 둔다
NAME_MARK = "__"


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


supabase = get_client()
bucket = supabase.storage.from_(BUCKET)


def new_name(file_name):
    """한글·띄어쓰기가 든 이름은 Storage 가 거부하므로, 겹치지 않는 영문 이름에 원래 이름을 base64 로 바꿔 붙인다"""
    ext = file_name.rsplit(".", 1)[-1].lower()
    hidden = base64.urlsafe_b64encode(file_name[:200].encode()).decode().rstrip("=")
    return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{NAME_MARK}{hidden}.{ext}"


def original_name(key):
    """new_name 으로 붙인 이름에서 원래 이름을 되살린다. 다른 곳에서 올린 파일은 Storage 이름을 그대로 쓴다"""
    if NAME_MARK not in key:
        return key
    hidden = key.split(NAME_MARK, 1)[1].rsplit(".", 1)[0]
    try:
        return base64.urlsafe_b64decode(hidden + "=" * (-len(hidden) % 4)).decode() or key
    except ValueError:
        return key


def size_text(item):
    size = (item.get("metadata") or {}).get("size") or 0
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    return f"{max(size / 1024, 0.1):.1f}KB"


def upload_time(item):
    """Storage 는 UTC 로 시각을 주므로 이 컴퓨터 시각으로 바꾼다"""
    created = item.get("created_at")
    if not created:
        return "날짜 모름"
    return f"{datetime.fromisoformat(created).astimezone():%Y-%m-%d %H:%M}"


st.title("문서 보관함")

# 올리고 다시 그린 뒤에 결과를 한 번 알려 준다
if "saved_message" in st.session_state:
    st.toast(st.session_state.pop("saved_message"), icon=":material/check:")

with st.form("upload", clear_on_submit=True):
    files = st.file_uploader("올릴 문서", type=DOC_TYPES, accept_multiple_files=True)
    submitted = st.form_submit_button("올리기", type="primary", width="stretch")

if submitted:
    if not files:
        st.warning("올릴 문서를 골라 주세요")
    else:
        done, failed = 0, []
        for f in files:
            try:
                bucket.upload(
                    new_name(f.name),
                    f.getvalue(),
                    {"content-type": f.type or "application/octet-stream"},
                )
            except Exception as e:
                failed.append(f"{f.name} ({e})")
            else:
                done += 1
        if failed:
            st.error("올리지 못한 문서가 있어요 : " + ", ".join(failed))
        if done:
            st.session_state.saved_message = f"문서 {done}개를 올렸어요"
            st.rerun()


@st.fragment(run_every=REFRESH_SECONDS)
def doc_list():
    # 최근에 올린 것부터. 폴더 자리표시 파일 등 문서가 아닌 것은 뺀다
    try:
        items = bucket.list(
            options={"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}}
        )
    except Exception as e:
        st.error(f"Supabase 에서 문서 목록을 받지 못했어요 : {e}")
        return

    items = [i for i in items if i["name"].rsplit(".", 1)[-1].lower() in DOC_TYPES]

    st.subheader(f"올라와 있는 문서 {len(items)}개")

    if not items:
        st.caption("아직 올린 문서가 없어요")
        return

    try:
        signed = bucket.create_signed_urls([i["name"] for i in items], URL_SECONDS)
    except Exception as e:
        st.error(f"Supabase 에서 내려받기 주소를 받지 못했어요 : {e}")
        return
    urls = {s["path"]: s["signedURL"] for s in signed if not s["error"]}

    closes_at = datetime.now() + timedelta(seconds=URL_SECONDS)
    st.caption(
        f"내려받기 링크는 {URL_SECONDS}초 동안만 열려요 ({closes_at:%H:%M:%S} 에 닫힘)."
        f" 화면은 {REFRESH_SECONDS}초마다 새 링크로 바뀌어요"
    )

    for item in items:
        name = original_name(item["name"])
        with st.container(border=True, horizontal=True, vertical_alignment="center"):
            with st.container(gap=None):
                st.markdown(f"**{name}**")
                st.caption(f"{upload_time(item)} · {size_text(item)}")
            if item["name"] in urls:
                # download 값을 붙이면 브라우저가 열지 않고 원래 이름으로 내려받는다
                url = urls[item["name"]] + "&" + urlencode({"download": name})
                st.link_button("내려받기", url, icon=":material/download:")
            else:
                st.caption("링크를 받지 못했어요")


doc_list()
