"""화면 파일들이 쓰는 키를 읽어 os.environ 에 넣는다.

- 내 컴퓨터 : 지금처럼 .env 에서 읽는다
- Streamlit Community Cloud : .env 가 없으니 배포 설정의 Secrets 에서 같은 이름으로 읽는다

.env 에 이미 있는 키는 그대로 두고, 빠진 키만 Secrets 에서 채운다.
Secrets 파일이 없으면(내 컴퓨터) 조용히 넘어가서 화면은 그대로 뜬다.
"""

import os

import streamlit as st
from dotenv import load_dotenv

# 화면 파일들이 os.environ 에서 꺼내 쓰는 키 이름
# GEMINI_API_KEY 는 genai.Client() 가 os.environ 에서 알아서 읽는다
KEY_NAMES = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "KAKAO_REST_API_KEY", "GEMINI_API_KEY")


def load_keys():
    load_dotenv()
    local = {name: os.environ[name] for name in KEY_NAMES if os.environ.get(name, "").strip()}
    missing = [name for name in KEY_NAMES if name not in local]
    if not missing:
        return
    try:
        found = {name: st.secrets.get(name) for name in missing}
    except Exception:
        # Secrets 파일이 없거나 읽을 수 없을 때 : .env 에서 읽은 것만 쓴다
        found = {}
    # Streamlit 은 Secrets 를 처음 읽을 때 같은 이름의 os.environ 값을 덮어쓰므로 .env 값을 되돌린다
    os.environ.update(local)
    for name, value in found.items():
        if isinstance(value, str) and value.strip():
            os.environ[name] = value
