# START HERE — 통합 마스터 하네스 (V4)

이 저장소에서는 Claude Code·Codex·Antigravity가 같은 작업 정책(`AGENTS.md`), 같은 스킬 6개, 같은 안전 hook을 씁니다.
사람은 **의도, 수용 기준, 위험한 결정, 병합**을 맡고, 구현 세부는 에이전트가 맡습니다. (English: `START-HERE.md`)

## 1. 처음 설정 (저장소마다 한 번)

```bash
python3 agent-core/scripts/bootstrap_project.py --write   # 저장소 사실(명령·포트 등)을 근거로만 기록
python3 agent-core/scripts/install_git_hooks.py           # 비밀 파일 커밋 차단 + 하네스 검사
python3 agent-core/scripts/doctor.py                      # 전역 설정이 하네스를 무력화하는지 점검
```

doctor 결과의 `RISK`는 먼저 해결하고, `WARN`은 읽고 판단하세요. doctor는 아무것도 바꾸지 않습니다.

각 도구에서 이 폴더를 한 번 신뢰해야 프로젝트 설정이 적용됩니다.

- **Codex:** 이 폴더에서 `codex`를 열어 프로젝트를 신뢰하고, `/hooks`에서 V4 hook을 검토·신뢰합니다. 그 뒤 `.codex/config.toml`(workspace-write 샌드박스)이 적용됩니다.
- **Antigravity:** 처음 `agy`를 열면 나오는 workspace trust 질문에 승인합니다.
- **Claude Code:** 별도 신뢰 단계는 없습니다. `.claude/settings.json`의 hook과 승인 규칙이 바로 적용됩니다.

마지막으로 도구들이 정말로 정책을 읽고 hook으로 막는지 확인합니다. 몇 분 걸리고 각 도구의 사용량을 조금 씁니다.

```bash
python3 agent-core/scripts/provider_smoke.py
python3 agent-core/scripts/codex_hook_probe.py   # Codex hook만, 계정·사용량 없이
```

실제 작업을 시작하면 `templates/PROJECT.md`를 참고해 `PROJECT.md`를 채웁니다. 제품 목적·사용자·꼭 지킬 것이 있어야 에이전트가 제품 기준으로 판단합니다.

## 2. Claude Code에서 달라지는 점

`.claude/settings.json`이 Claude Code에만 있는 강제 장치를 켭니다.

- **권한(널널한 설정):** 샌드박스는 기본으로 꺼져 있고, 셸 명령·파일 편집·웹 도구는 묻지 않고 실행됩니다. push/publish와 하네스 파일 수정은 여전히 승인을 묻고,
  작업을 날리는 명령은 hook이 막습니다. 셸 쓰기를 프로젝트 안으로 묶고 싶으면 `sandbox.enabled`를 `true`로 바꾸세요.
- **비밀 파일:** Claude는 `.env`, 키 파일 등을 읽을 수 없습니다(셸의 `cat .env`는 hook이 승인을 물음). `.env.example`은 읽을 수 있습니다. 비밀값이 필요하면 직접 열어 보세요.
- **하네스 보호:** `AGENTS.md`, `CLAUDE.md`, `agent-core/hooks·scripts·evals`, `.codex`, `.agents`는 Claude가 고치려 하면 승인을 묻고, 셸로는 아예 못 고칩니다.
  그래서 하네스 관리 명령(`sync_agent_config.py`, `upgrade_harness.py`, `install_git_hooks.py`)은 **직접 터미널에서** 실행하세요.
- **검증 경고:** 코드를 고친 뒤 테스트·빌드·실행 확인 없이 Claude가 작업을 끝내면 "V4 verification warning"이 뜹니다. 막지는 않습니다. 경고가 보이면 검증을 요청하세요.
- **긴 작업:** 문맥이 압축되기 직전에 요청·수정 파일·검증 기록이 자동 저장되고, 압축 직후 Claude에게 다시 전달됩니다.
- **명령:** `/harness-check`(점검), `/retro`(하네스 회고), `/smoke`(도구 실측). 위험도 높은 변경의 독립 리뷰는 `dev-reviewer` 서브에이전트가 맡습니다.

## 3. 평소 사용

요청은 결과 중심으로 하면 됩니다. 크기에 따라 절차가 자동으로 달라집니다(작은 일은 바로 수정, 큰 일은 `dev-plan`으로 수용 기준부터).
큰 작업은 `templates/TASK-REQUEST.md` 형식을 쓰면 빠짐없이 전달됩니다.
에이전트가 PR을 만들면 `templates/PR-BODY.md` 형식의 요약(무엇이 바뀌었나, 무엇을 확인했나, 위험)을 보고 의도·동작·증거·위험만 판단하면 됩니다.

## 4. 정기 점검

| 언제 | 명령 | 목적 |
|---|---|---|
| 의미 있는 작업 3~5개마다 | `python3 agent-core/scripts/growth_engine.py ingest-hooks` 후 `candidates` | hook 차단 기록에서 반복 마찰·오탐을 관찰로 쌓고, 개선 후보 확인 |
| 같은 때 | `python3 agent-core/scripts/growth_engine.py hook-stats` | 최근 차단 현황 |
| 에이전트 CLI를 업데이트한 뒤 | `python3 agent-core/scripts/provider_smoke.py` | 업데이트로 hook 동작이 바뀌지 않았는지 확인 |
| Codex를 업데이트한 뒤 (계정 없이도 됨) | `python3 agent-core/scripts/codex_hook_probe.py` | Codex가 안전 hook을 실제로 실행하는지 확인 (사용량 0) |
| 스킬·정책을 바꾼 뒤 | `python3 agent-core/scripts/run_evals.py --provider claude` | 스킬 선택이 나빠지지 않았는지 측정 (사례마다 모델 호출 1회) |
| 언제든 | `python3 agent-core/scripts/doctor.py` | 전역 설정·비밀 파일 점검 |

개선 후보를 실제로 반영할지는 사람이 정합니다. 정책·안전 hook·권한 변경은 반드시 사람이 검토합니다(`docs/agent/GROWTH-ENGINE.md`).

## 5. 하네스 업그레이드

새 하네스를 `/경로/unified-master-harness`에 받은 뒤, 이 저장소에서:

```bash
python3 agent-core/scripts/upgrade_harness.py --from /경로/unified-master-harness          # 미리보기
python3 agent-core/scripts/upgrade_harness.py --from /경로/unified-master-harness --apply  # 적용 (백업 자동)
```

이 저장소에서 직접 고친 하네스 파일은 덮어쓰지 않고 `파일.v4-new`로 옆에 둡니다. 둘을 합친 뒤 `.v4-new`를 지우고 `check_agent_config.py`를 다시 돌리세요.
`PROJECT.md`, 프로젝트 프로필, 성장 기록은 건드리지 않습니다.

## 6. 하지 말 것

- `git commit --no-verify`로 pre-commit 검사 우회 (에이전트에게도 허락하지 마세요)
- 에이전트에게 `AGENTS.md`·안전 hook·권한 설정을 스스로 고치게 하기
- 전역 자동 승인(Claude `bypassPermissions`, Codex `approval_policy = "never"` + `danger-full-access`, Antigravity `always-proceed`)을 이 프로젝트의 기본으로 쓰기 — doctor가 경고합니다
- 비밀값을 저장소 안의 `.env`에 두고 에이전트에게 맡기기 — 가능하면 키체인·비밀 관리 도구에서 실행 시점에 주입

## 7. 문서 지도

- `AGENTS.md` — 세 도구 공통 작업 정책 (항상 로드)
- `PROJECT.md` — 제품 기준 (직접 작성)
- `docs/agent/ARCHITECTURE.md` — 구조와 안전 판정 표
- `docs/agent/OPERATING-GUIDE.md` — 사람과 AI의 역할 분담
- `docs/agent/GROWTH-ENGINE.md` — 하네스 개선 절차
- `docs/agent/VERIFICATION.md` — 배포 전 검증 항목
- `agent-core/evals/provider-smoke.md` — 도구별 실측 메모
