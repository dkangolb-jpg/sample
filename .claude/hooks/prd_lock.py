"""PRD.md 자물쇠 훅.

AI 가 Write/Edit 로 PRD.md 를 건드리려 하면 막고, 경고창을 띄우고,
AI 에게 "제안만 하라" 는 이유를 돌려보낸다. 다른 파일은 그대로 통과시킨다.
명령 창(Bash/PowerShell)은 명령 안에 PRD.md 가 들어 있기만 해도 막는다.
(읽기와 고치기를 명령 글자만으로 가려낼 수 없어서다. 읽기는 Read 로 한다)
"""
import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRD_PATH = os.path.normcase(os.path.join(PROJECT_DIR, "PRD.md"))

TITLE = "PRD 자물쇠"
MESSAGE = "[건들기 전에 생각하셨나요?]"
REASON = "PRD.md 는 잠겨 있으니 고치지 말고 바꿀 내용을 제안만 하라"

# MB_OK | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
MB_FLAGS = 0x0 | 0x30 | 0x1000 | 0x10000 | 0x40000


def show_dialog():
    """경고창만 띄우는 모드. 훅 본체가 따로 실행한다."""
    import ctypes
    import winsound
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    ctypes.windll.user32.MessageBoxW(None, MESSAGE, TITLE, MB_FLAGS)


def launch_dialog():
    """경고창을 별도 실행으로 띄워, 훅이 '확인' 클릭을 기다리지 않게 한다."""
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw
    subprocess.Popen(
        [exe, os.path.abspath(__file__), "--dialog"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def is_prd(file_path):
    if not file_path:
        return False
    path = file_path
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_DIR, path)
    return os.path.normcase(os.path.abspath(path)) == PRD_PATH


def mentions_prd(command):
    return "prd.md" in (command or "").lower()


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    tool_input = data.get("tool_input") or {}
    if data.get("tool_name") in ("Bash", "PowerShell"):
        locked = mentions_prd(tool_input.get("command", ""))
    else:
        locked = is_prd(tool_input.get("file_path", ""))
    if not locked:
        return

    try:
        launch_dialog()
    except Exception:
        pass  # 경고창이 실패해도 막는 것은 그대로 한다

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    if "--dialog" in sys.argv:
        show_dialog()
    else:
        main()
