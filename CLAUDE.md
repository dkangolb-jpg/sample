# CLAUDE.md

## 절대 규칙

1. 작업을 시작하기 전에 PRD.md 를 읽고 tasks.md 가 있으면 함께 읽은 뒤, 답 첫 줄에 이번 작업이 채우는 PRD.md 5장 수용 기준 한 줄을 그대로 옮겨 적는다 (채우는 수용 기준이 없으면 "수용 기준 없음" 이라고 적는다)
2. 답에 PRD.md 와 tasks.md 에 나오지 않는 낱말을 쓰면 그 자리 바로 뒤 괄호 안에 뜻을 한 줄로 적고, 답 끝 서명 줄 바로 위에 "풀어 쓴 말 : ○○, ○○" 처럼 모아 적는다 (없으면 "풀어 쓴 말 : 없음")
3. 모든 답의 맨 마지막 줄에 "이상입니다, SIMON" 을 적는다

## 갈 곳을 아직 못 정한 줄 (지우지 말 것)

- PRD.md 3장 비목표에 적힌 5가지는 만들지 않는다. 요청받으면 만들지 말고 "비목표입니다" 라고 먼저 답한다
- 빌드·린트·테스트 도구가 없는 개인 작업 폴더다. 서로 상관없는 두 갈래(매출 데이터, 제품 아이디어)가 섞여 있다.
- `01_docs/` — 매출 원본 CSV(`sales-2026-messy.csv`), 월별 CSV, 점포 기준 정보(`branch-info.csv`)
- `02_output/` — 정리된 매출 엑셀, 담당자별 엑셀(`by-manager/`), 워크숍정산 엑셀
- `03_report/` — 워크숍 비용 정산의 원본 문서(PDF·docx·xlsx)
- `dashboard/index.html` — 워크숍정산 합계를 보여 주는 정적 HTML 한 장. 숫자는 `02_output/워크숍정산.xlsx` 에서 손으로 옮겨 적는다
- `memo.md` — 정산·대시보드에서 내린 결정과 남은 할 일 메모. 그쪽을 고치기 전에 먼저 본다
- `idea/` — PRD 이전 단계 문서(problems → ideas → shortlist → topic → scope)와 `wireframe.png`
- `PRD.md` — "대동맛지도" 의 기준 문서(문제, 페르소나, 범위, 화면, 수용 기준)
- `tasks.md` — `PRD.md` 에서 뽑은 할 일 체크리스트. `PRD.md` 가 바뀌면 다시 뽑는다

## 상황별 규칙 (목차 — 규칙은 .claude/rules/ 에 있음)

- 화면을 만들 때 → .claude/rules/screen.md
- 도구를 새로 설치하거나 연결할 때 → .claude/rules/tool.md
- 안내 문구를 쓸 때 → .claude/rules/writing.md
- 파일을 고치는 작업을 마치고 확인까지 끝냈을 때 → commit-push 스킬을 써서 바로 커밋하고 푸시한다 (.claude/skills/commit-push/SKILL.md)

## 우선순위

CLAUDE.md 의 절대 규칙이 rules 파일보다 항상 우선한다.
