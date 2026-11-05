import os
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

st.set_page_config(page_title="구독 정리함")

COLUMNS = ["id", "name", "category", "monthly_fee", "last_used"]


@st.cache_resource
def get_client():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


supabase = get_client()

# 저장할 때마다 1씩 올려서 편집 표를 새로 그린다 (고치던 흔적이 남지 않게)
if "editor_version" not in st.session_state:
    st.session_state.editor_version = 0


def load_rows():
    # 요금이 비싼 것부터, 요금이 같으면 먼저 넣은 것부터
    rows = (
        supabase.table("subscriptions")
        .select(", ".join(COLUMNS))
        .order("monthly_fee", desc=True)
        .order("id")
        .execute()
        .data
    )
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["last_used"] = pd.to_datetime(df["last_used"]).dt.date
    return df


def clean(values):
    """편집 표에서 받은 한 줄을 Supabase 에 넣을 모양으로 바꾼다. 빠진 칸이 있으면 None"""
    row = {}
    if "name" in values:
        row["name"] = (values["name"] or "").strip()
    if "category" in values:
        row["category"] = (values["category"] or "").strip()
    if "monthly_fee" in values:
        row["monthly_fee"] = None if values["monthly_fee"] is None else int(values["monthly_fee"])
    if "last_used" in values:
        row["last_used"] = None if values["last_used"] is None else str(values["last_used"])[:10]
    if any(v in ("", None) for v in row.values()):
        return None
    return row


st.title("구독 정리함")

# 저장하고 다시 그린 뒤에 결과를 한 번 알려 준다
if "saved_message" in st.session_state:
    st.toast(st.session_state.pop("saved_message"), icon=":material/check:")

df = load_rows()

total = int(df["monthly_fee"].sum())
st.metric("한 달에 나가는 돈", f"{total:,}원", help=f"구독 {len(df)}개를 더한 값")

st.caption("칸을 눌러 고치고, 맨 아래 빈 줄에 더하고, 줄 왼쪽을 골라 지운 뒤 \"저장\" 을 누르세요")

editor_key = f"editor_{st.session_state.editor_version}"

with st.form("subs"):
    st.data_editor(
        df,
        key=editor_key,
        num_rows="dynamic",
        hide_index=True,
        disabled=["id"],
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("이름", required=True),
            "category": st.column_config.TextColumn("분류", required=True),
            "monthly_fee": st.column_config.NumberColumn(
                "한 달 요금", min_value=0, step=1, format="%d원", required=True
            ),
            "last_used": st.column_config.DateColumn(
                "마지막으로 쓴 날", format="YYYY-MM-DD", max_value=date.today(), required=True
            ),
        },
        alt="구독 목록",
    )
    saved = st.form_submit_button("저장", type="primary", width="stretch")

if saved:
    changes = st.session_state[editor_key]
    updates = {}
    inserts = []
    problem = False

    for i, values in changes["edited_rows"].items():
        if int(i) in changes["deleted_rows"]:
            continue
        row = clean(values)
        if row is None:
            problem = True
        elif row:
            updates[int(df.iloc[int(i)]["id"])] = row

    for values in changes["added_rows"]:
        if not values:
            continue
        row = clean({c: values.get(c) for c in COLUMNS if c != "id"})
        if row is None:
            problem = True
        else:
            inserts.append(row)

    delete_ids = [int(df.iloc[i]["id"]) for i in changes["deleted_rows"]]

    if problem:
        st.warning("비어 있는 칸이 있어요. 이름 · 분류 · 한 달 요금 · 마지막으로 쓴 날을 모두 채워 주세요")
    elif not (updates or inserts or delete_ids):
        st.info("바뀐 내용이 없어요")
    else:
        try:
            for row_id, row in updates.items():
                supabase.table("subscriptions").update(row).eq("id", row_id).execute()
            if inserts:
                supabase.table("subscriptions").insert(inserts).execute()
            if delete_ids:
                supabase.table("subscriptions").delete().in_("id", delete_ids).execute()
        except Exception as e:
            st.error(f"Supabase 에 저장하지 못했어요 : {e}")
        else:
            st.session_state.editor_version += 1
            st.session_state.saved_message = f"고침 {len(updates)} · 더함 {len(inserts)} · 지움 {len(delete_ids)}"
            st.rerun()
