# 아래 따옴표 세 개로 묶인 글은 이 파일이 무엇을 하는지 적은 설명문이다 (코드가 아니라 글이라 그 안에는 주석을 넣지 않았다)
# 설명문 1줄 : 이 파일의 이름 — 설치 확인 훅
# 설명문 3~5줄 : 설치 명령을 넣기 전에 "이대로 설치할까요?" 라고 묻지 않았으면 막고, 경고창을 띄우고, 이유를 돌려보낸다
# 설명문 6줄 : 이 훅을 만든 근거는 .claude/rules/tool.md 첫째 줄이다
"""설치 확인 훅.

AI 가 Bash/PowerShell 로 설치 명령을 넣으려 할 때, 바로 앞 AI 답에서
"이대로 설치할까요?" 라고 묻지 않았으면 막고, 경고창을 띄우고,
AI 에게 먼저 물어보라는 이유를 돌려보낸다. 다른 명령은 그대로 통과시킨다.
(근거 : .claude/rules/tool.md 첫째 줄)
"""
import json  # Claude Code 가 넘겨주는 글(JSON)을 읽고, 돌려보낼 글을 JSON 으로 만들 때 쓴다
import os  # 파일 위치를 다루고 파일이 있는지 확인할 때 쓴다
import subprocess  # 경고창을 따로 떨어진 프로그램으로 띄울 때 쓴다
import sys  # 입력(stdin)·출력(stdout)과 실행할 때 붙은 옵션을 다룰 때 쓴다

INSTALL_WORDS = (  # 명령 안에 이 낱말 중 하나라도 있으면 "설치 명령"으로 본다
    "pip install",  # 파이썬 꾸러미 설치
    "npm install",  # 노드 꾸러미 설치
    "npm i ",  # npm install 을 줄여 쓴 꼴 (뒤 빈칸은 "npm init" 같은 것과 헷갈리지 않으려고 붙였다)
    "yarn add",  # yarn 으로 꾸러미 설치
    "pnpm add",  # pnpm 으로 꾸러미 설치
    "winget install",  # 윈도우 프로그램 설치 (winget)
    "choco install",  # 윈도우 프로그램 설치 (초콜레티)
    "install-module",  # PowerShell 모듈 설치 (뒤에서 소문자로 바꿔 비교하므로 소문자로 적었다)
    "install-package",  # PowerShell 꾸러미 설치
)  # 설치 낱말 목록 끝
ASK_PHRASE = "이대로 설치할까요?"  # 앞선 AI 답에 이 말로 끝나는 줄이 있으면 "물어봤다"고 본다

TITLE = "설치 확인"  # 경고창 맨 위 제목
MESSAGE = "[설치하기 전에 물어보셨나요?]"  # 경고창 안에 보일 글
REASON = (  # 막을 때 AI 에게 돌려보내는 이유 (아래 두 줄이 한 문장으로 이어 붙는다)
    "설치하기 전에 도구 이름·쓰는 곳·설치 명령 한 줄을 보여 주고 "  # 이유 앞부분
    "'이대로 설치할까요?' 라고 물어 답을 받아라"  # 이유 뒷부분
)  # 이유 문장 끝

# 경고창 모양을 정하는 값들을 더한 것이다 : 확인 버튼 하나 · 느낌표 그림 · 다른 창보다 앞에 · 맨 위에 띄우기
# MB_OK | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
MB_FLAGS = 0x0 | 0x30 | 0x1000 | 0x10000 | 0x40000  # 위 다섯 값을 숫자로 적어 하나로 합친 것


def show_dialog():  # 경고창을 실제로 화면에 띄우는 함수
    """경고창만 띄우는 모드. 훅 본체가 따로 실행한다."""  # 이 함수 설명문
    import ctypes  # 윈도우 기본 기능(경고창)을 부를 때 쓴다
    import winsound  # 윈도우 알림 소리를 낼 때 쓴다
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # "띵" 하는 경고 소리를 낸다
    ctypes.windll.user32.MessageBoxW(None, MESSAGE, TITLE, MB_FLAGS)  # 제목·글·모양을 넣어 경고창을 띄운다 (확인을 누를 때까지 기다린다)


def launch_dialog():  # 경고창을 따로 떨어진 프로그램으로 띄우는 함수
    """경고창을 별도 실행으로 띄워, 훅이 '확인' 클릭을 기다리지 않게 한다."""  # 이 함수 설명문
    exe = sys.executable  # 지금 이 파일을 돌리고 있는 python 프로그램 위치
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")  # 같은 폴더의 pythonw.exe(검은 창 없이 도는 python) 위치
    if os.path.exists(pythonw):  # pythonw.exe 가 있으면
        exe = pythonw  # 그것으로 바꿔 써서 검은 창이 뜨지 않게 한다
    subprocess.Popen(  # 새 프로그램을 띄우고 끝나기를 기다리지 않는다
        [exe, os.path.abspath(__file__), "--dialog"],  # 이 파일을 "--dialog" 옵션을 붙여 다시 실행한다 (= show_dialog 만 돈다)
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,  # 훅과 완전히 떨어진 프로그램으로 띄운다
        stdin=subprocess.DEVNULL,  # 입력은 받지 않는다
        stdout=subprocess.DEVNULL,  # 출력은 버린다 (훅의 답과 섞이지 않게)
        stderr=subprocess.DEVNULL,  # 오류 출력도 버린다
        close_fds=True,  # 훅이 열어 둔 파일 등을 새 프로그램에 넘기지 않는다
    )  # 새 프로그램 띄우기 끝


def is_install(command):  # 명령이 설치 명령인지 알아보는 함수
    text = (command or "").lower() + " "  # 명령을 소문자로 바꾸고 끝에 빈칸 하나를 붙인다 (끝이 "npm i" 인 경우도 잡으려고)
    return any(word in text for word in INSTALL_WORDS)  # 설치 낱말 중 하나라도 들어 있으면 참


def texts_of(content):  # 메시지 내용에서 글자만 뽑아 목록으로 돌려주는 함수
    """메시지 내용에서 글자 부분만 꺼낸다."""  # 이 함수 설명문
    if isinstance(content, str):  # 내용이 그냥 글 한 덩어리면
        return [content]  # 그대로 목록에 담아 돌려준다
    out = []  # 뽑은 글을 모을 빈 목록
    for block in content or []:  # 내용이 여러 조각이면 조각마다 살펴본다 (내용이 없으면 건너뛴다)
        if isinstance(block, dict) and block.get("type") == "text":  # 글 조각이면 (도구 사용 조각 등은 빼고)
            out.append(block.get("text", ""))  # 그 글을 목록에 넣는다
    return out  # 모은 글 목록을 돌려준다


def is_real_user_message(entry):  # 대화 기록 한 줄이 사람이 직접 쓴 글인지 알아보는 함수
    """사람이 직접 보낸 글인가 (도구 결과·시스템 글은 빼고)."""  # 이 함수 설명문
    if entry.get("type") != "user" or entry.get("isMeta"):  # 사람 쪽 기록이 아니거나, 시스템이 끼워 넣은 글이면
        return False  # 사람 글이 아니다
    content = (entry.get("message") or {}).get("content")  # 그 기록의 내용을 꺼낸다
    if isinstance(content, str):  # 내용이 그냥 글이면
        return True  # 사람이 쓴 글이다
    return any(isinstance(b, dict) and b.get("type") == "text" for b in content or [])  # 조각 중 글 조각이 하나라도 있으면 사람 글 (도구 결과만 있으면 아니다)


def has_ask_line(text):  # 글 안에 "이대로 설치할까요?" 로 끝나는 줄이 있는지 알아보는 함수
    """'이대로 설치할까요?' 로 끝나는 줄이 있나 (문장 안에서 인용만 한 것은 빼려고)."""  # 이 함수 설명문
    return any(line.strip().endswith(ASK_PHRASE) for line in text.splitlines())  # 줄마다 앞뒤 빈칸을 떼고, 그 말로 끝나는 줄이 하나라도 있으면 참


def asked_before(transcript_path):  # 바로 앞 AI 답에서 설치를 물어봤는지 알아보는 함수
    """마지막 사람 글 바로 앞의 AI 답에 '이대로 설치할까요?' 로 끝나는 줄이 있었나."""  # 이 함수 설명문
    try:  # 아래에서 문제가 생기면 except 로 간다
        with open(transcript_path, encoding="utf-8") as f:  # 대화 기록 파일을 연다
            entries = [json.loads(line) for line in f if line.strip()]  # 빈 줄을 빼고 한 줄씩 읽어 목록으로 만든다
    except Exception:  # 파일이 없거나 읽다가 문제가 생기면
        return False  # 물어보지 않은 것으로 본다 (막는 쪽으로)

    user_idx = [i for i, e in enumerate(entries) if is_real_user_message(e)]  # 사람이 직접 쓴 글이 몇 번째 줄인지 모두 모은다
    if not user_idx:  # 사람 글이 하나도 없으면
        return False  # 물어보지 않은 것으로 본다
    last = user_idx[-1]  # 마지막 사람 글의 자리 (지금 요청)
    prev = user_idx[-2] if len(user_idx) > 1 else -1  # 그 바로 앞 사람 글의 자리 (없으면 맨 앞보다 하나 앞인 -1)

    for entry in entries[prev + 1:last]:  # 두 사람 글 사이의 기록(= 바로 앞 AI 답)을 하나씩 본다
        if entry.get("type") != "assistant":  # AI 답이 아니면
            continue  # 건너뛴다
        for text in texts_of((entry.get("message") or {}).get("content")):  # 그 AI 답의 글 조각마다
            if has_ask_line(text):  # "이대로 설치할까요?" 로 끝나는 줄이 있으면
                return True  # 물어본 것이다
    return False  # 끝까지 없으면 물어보지 않은 것이다


def main():  # 훅 본체 : Claude Code 가 도구를 쓰기 직전에 이 함수가 돈다
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")  # Claude Code 가 넘겨준 정보를 utf-8 로 읽어 풀어 놓는다 (비어 있으면 빈 값)
    if data.get("tool_name") not in ("Bash", "PowerShell"):  # 쓰려는 도구가 Bash 나 PowerShell 이 아니면
        return  # 아무것도 하지 않고 통과시킨다
    command = (data.get("tool_input") or {}).get("command", "")  # 넣으려는 명령 글을 꺼낸다
    if not is_install(command):  # 설치 명령이 아니면
        return  # 통과시킨다
    if asked_before(data.get("transcript_path", "")):  # 바로 앞 AI 답에서 이미 물어봤으면
        return  # 통과시킨다

    try:  # 경고창 띄우기를 시도한다
        launch_dialog()  # 경고창을 따로 떨어진 프로그램으로 띄운다
    except Exception:  # 띄우다 문제가 생겨도
        pass  # 경고창이 실패해도 막는 것은 그대로 한다

    out = {  # Claude Code 에 돌려보낼 답을 만든다
        "hookSpecificOutput": {  # 훅 종류별 답을 넣는 칸
            "hookEventName": "PreToolUse",  # 도구를 쓰기 직전에 도는 훅이라는 표시
            "permissionDecision": "deny",  # 이 도구 사용을 막는다
            "permissionDecisionReason": REASON,  # 막은 이유 (AI 에게 보인다)
        }  # 훅 종류별 답 끝
    }  # 돌려보낼 답 끝
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))  # 답을 JSON 글로 바꿔 utf-8 로 내보낸다 (한글이 깨지지 않게)


if __name__ == "__main__":  # 이 파일을 직접 실행했을 때만 아래가 돈다
    if "--dialog" in sys.argv:  # "--dialog" 옵션이 붙어 실행됐으면 (launch_dialog 가 띄운 경우)
        show_dialog()  # 경고창만 띄운다
    else:  # 그렇지 않으면 (Claude Code 가 훅으로 실행한 경우)
        main()  # 훅 본체를 돌린다
