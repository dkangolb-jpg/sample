import os
import uuid
from datetime import datetime

import streamlit as st
from env_keys import load_keys
from supabase import create_client

load_keys()

st.set_page_config(page_title="사진 보관함")

BUCKET = "photos"
IMAGE_TYPES = ["png", "jpg", "jpeg", "gif", "webp"]
# photos 버킷은 공개가 아니라서, 그림을 보여 줄 때마다 1시간짜리 열람 주소를 새로 받는다
URL_SECONDS = 60 * 60
# 목록에서는 그림을 작게 줄여 한 줄로 나란히 보여 준다
THUMB_WIDTH = 140


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


supabase = get_client()
bucket = supabase.storage.from_(BUCKET)


def new_name(file_name):
    """한글·띄어쓰기가 든 이름은 Storage 가 거부할 수 있고, 덮어쓰기 허용 규칙도 없으므로 겹치지 않는 영문 이름을 새로 붙인다"""
    ext = file_name.rsplit(".", 1)[-1].lower()
    return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.{ext}"


st.title("사진 보관함")

# 올리고 다시 그린 뒤에 결과를 한 번 알려 준다
if "saved_message" in st.session_state:
    st.toast(st.session_state.pop("saved_message"), icon=":material/check:")

with st.form("upload", clear_on_submit=True):
    files = st.file_uploader(
        "올릴 그림", type=IMAGE_TYPES, accept_multiple_files=True
    )
    submitted = st.form_submit_button("올리기", type="primary", width="stretch")

if submitted:
    if not files:
        st.warning("올릴 그림을 골라 주세요")
    else:
        done, failed = 0, []
        for f in files:
            try:
                bucket.upload(new_name(f.name), f.getvalue(), {"content-type": f.type})
            except Exception as e:
                failed.append(f"{f.name} ({e})")
            else:
                done += 1
        if failed:
            st.error("올리지 못한 그림이 있어요 : " + ", ".join(failed))
        if done:
            st.session_state.saved_message = f"그림 {done}장을 올렸어요"
            st.rerun()

# 최근에 올린 것부터. 폴더 자리표시 파일 등 그림이 아닌 것은 뺀다
try:
    items = bucket.list(
        options={"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}}
    )
except Exception as e:
    st.error(f"Supabase 에서 그림 목록을 받지 못했어요 : {e}")
    st.stop()

items = [i for i in items if i["name"].rsplit(".", 1)[-1].lower() in IMAGE_TYPES]

st.subheader(f"올라와 있는 그림 {len(items)}장")

if not items:
    st.caption("아직 올린 그림이 없어요")
    st.stop()

signed = bucket.create_signed_urls([i["name"] for i in items], URL_SECONDS)
urls = {s["path"]: s["signedURL"] for s in signed if not s["error"]}


def upload_day(item):
    """Storage 는 UTC 로 시각을 주므로 이 컴퓨터 시각으로 바꿔 날짜만 남긴다"""
    created = item.get("created_at")
    if not created:
        return "날짜 모름"
    return f"{datetime.fromisoformat(created).astimezone():%Y-%m-%d}"


# 같은 날 올린 그림끼리 테두리 하나에 한 줄로 늘어놓고, 날짜는 테두리 오른쪽 아래에 한 번만 적는다
days = {}
for item in items:
    days.setdefault(upload_day(item), []).append(item)

for day, day_items in days.items():
    with st.container(border=True):
        # 칸이 모자라면 줄을 바꾸지 않고 옆으로 밀어서 본다
        with st.container(horizontal=True, wrap=False):
            for item in day_items:
                if item["name"] in urls:
                    st.image(urls[item["name"]], width=THUMB_WIDTH, alt=f"올린 그림 {item['name']}")
                else:
                    st.caption("그림 주소를 받지 못했어요", width=THUMB_WIDTH)
        st.caption(day, text_alignment="right")
