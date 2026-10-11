# 통합 마스터 하네스 (Unified Master Harness, V4)

**Claude Code·Codex·Antigravity가 함께 쓰는 작업 정책 하나, 워크플로 스킬 6개, 실제로 작동하는 안전 hook.**

저장소에 넣으면 어떤 에이전트를 쓰든 같은 규칙을 따릅니다. 작업 크기에 맞게 절차를 조절하고, 문제를 푸는 가장 작은 변경만 하고, 완료라고 말하기 전에 검증하고, 작업물을 날리거나 비밀을 새게 하는 명령은 실행하지 않습니다.
규칙은 평범한 파일이고, 안전 부분은 각 CLI가 실제로 실행하는 hook이 강제합니다. 아래 주장은 모두 실제 CLI로 측정했습니다([검증 보고서](docs/VERIFICATION-REPORT.md), 영어).

[English README](README.md)

## 들어 있는 것

- **`AGENTS.md`, 세 에이전트 공통 정책 하나** (49줄, 약 2,200토큰, 항상 로드): 작업 크기 분류(작음/중간/큼), 추측 대신 근거, 가장 작은 일관된 변경, 요청 없는 리팩터링 금지, 바뀌지 않은 파일 다시 읽지 않기, 완료 전 검증. Claude는 `CLAUDE.md`를 통해, Antigravity는 자동 생성된 사본을 통해 읽습니다.
- **필요할 때만 읽는 스킬 6개:** `project-context`, `dev-plan`(크거나 모호한 작업만), `dev-debug`, `dev-ui-verify`(변경 크기에 맞춘 깊이), `dev-verify`, `dev-review`.
- **세 CLI 모두에 안전 hook**, 판정은 공용 정책 하나(`agent-core/hooks/policy.py`):
  - 작업물을 날리는 명령: `git reset --hard`, `checkout -- .`, `restore .`, `stash clear`, `clean -f`, 강제 push, 홈·시스템 루트 `rm -rf`. `sh -c`, `sudo`, `env`, `xargs`, git 전역 옵션 뒤에 숨겨도 잡습니다.
  - 비밀 파일: `.env*`, 키, `.netrc`, 클라우드·컨테이너 인증 파일. 읽기·복사·인코딩 모두.
  - 외부 작업: `git push`, 패키지 배포, 릴리스, 배포, 인프라 적용, DB 삭제.
  - 하네스 자체를 고치는 쓰기.
  도구마다 강제할 수 있는 가장 강한 방식으로 대응합니다. Claude는 승인 요청 또는 거부, Codex와 Antigravity는 거부입니다(이 둘의 hook은 확인 창을 믿을 수 없게 띄웁니다).
- **Claude Code 전용 계층:** 권한 규칙을 OS 샌드박스에 합쳐 셸에서도 비밀 파일을 못 읽게 하고, 느슨한 샌드박스(쓰기는 프로젝트·임시 폴더·패키지 캐시만, 네트워크는 허용), 코드를 고치고 검증 없이 끝내면 경고, 문맥 압축 후에도 남는 작업 요약, 읽기 전용 리뷰 서브에이전트, 슬래시 명령 3개.
- **하네스가 제대로 작동하는지 확인하는 도구:** `doctor.py`(이 모든 걸 조용히 무력화하는 사용자 설정 찾기), `provider_smoke.py`(일회용 저장소에서 실제 CLI 실행), `codex_hook_probe.py`(계정 없이 Codex hook 확인), `run_evals.py`(에이전트가 맞는 스킬을 고르는지), 비밀 파일 커밋 차단 pre-commit, CI, 비밀값을 남기지 않는 차단 기록, 직접 고친 파일은 덮어쓰지 않는 `upgrade_harness.py`.

## 측정 결과 (V4.2.1)

| | Claude Code 2.1.296 | Antigravity 1.3.3 | Codex CLI 0.161.0 |
|---|---|---|---|
| 실제 CLI 안전 smoke | 6/6 + Claude 계층 8/8 | 6/6 | hook 런타임 PASS (모델 없는 검사) |
| 스킬 선택 12건 | 12/12 | 12/12 | 미실행 |

방법, 도중에 실패했던 것, 알려진 한계: [docs/VERIFICATION-REPORT.md](docs/VERIFICATION-REPORT.md)

**비용.** 작은 작업 4개를 하네스 없이/있이 Claude Code로 24회 돌렸더니, 하네스 쪽이 **약 20% 더** 들었고 정답률은 양쪽 모두 100%였습니다. 요즘 모델은 쉬운 작업을 원래 최소 변경으로 고치기 때문에, 하네스가 코드를 더 짧게 만들지는 않습니다.
늘어난 비용은 대부분 고정 문맥입니다(턴마다 입력 약 4,800토큰, 그중 절반은 Claude Code 자체의 샌드박스 설명). 그 대가로 얻는 것은 안전 계층과, 끝내기 전 스스로 확인하는 습관의 일관성입니다. 전체 수치와 비용을 줄이는 방법: [docs/BENCHMARK.md](docs/BENCHMARK.md)

## 요구 사항

- macOS 또는 Linux (Windows는 WSL 사용, 네이티브 Windows는 검증 안 됨)
- Python 3.10 이상, git. 다른 의존성 없음.
- Claude Code, Codex CLI, Antigravity CLI 중 하나 이상.

## 설치

```bash
git clone https://github.com/egoxx1/unified-master-harness.git
python3 unified-master-harness/install/apply.py --target /경로/내-저장소            # 미리보기
python3 unified-master-harness/install/apply.py --target /경로/내-저장소 --apply --create-project-template
```

그다음 내 저장소의 `START-HERE.ko.md`를 따르세요(명령 3개, Codex·Antigravity에서 폴더 신뢰 한 번).

- **이미 `AGENTS.md`, `CLAUDE.md`, 에이전트 설정이 있는 저장소:** 설치 프로그램이 덮어쓰지 않고 멈춥니다(종료 코드 2, 아무것도 쓰지 않음). [install/INSTALLATION-PROMPT.md](install/INSTALLATION-PROMPT.md)를 에이전트에게 주면 의미 단위로 합쳐 줍니다.
- **업그레이드:** 내 저장소에서 `python3 agent-core/scripts/upgrade_harness.py --from /경로/unified-master-harness`. 직접 고친 파일은 유지되고, 새 버전은 옆에 `.v4-new`로 생깁니다.
- 내 `README.md`, 제품 코드, `PROJECT.md`는 절대 건드리지 않습니다.

## 구조

```
PROJECT.md             제품이 무엇인지 (직접 작성)
AGENTS.md              에이전트 작업 방식 (공통 정책)
.agents/skills/        필요할 때 읽는 절차 (원본, .claude/skills/로 복제)
agent-core/hooks/      policy.py + CLI별 작은 어댑터
.claude/  .codex/  .agents/hooks.json   도구별 연결
agent-core/scripts/    결정적 도구: doctor, smoke, evals, upgrade, sync, 검사
.agent-state/          로컬 작업 상태와 차단 기록 (gitignore)
```

자세히: [START-HERE.ko.md](START-HERE.ko.md), [docs/agent/ARCHITECTURE.md](docs/agent/ARCHITECTURE.md)

## 한계

명령 정책은 좁은 가드이지 셸 방화벽이 아닙니다. 변수로 출력하는 비밀값, 표준입력으로 넘기는 대상, 변수로 만든 경로는 보지 못합니다.
코드가 맞는지는 여전히 테스트와 에이전트의 검증·리뷰에 달려 있고, 이것도 놓칠 수 있습니다. 하네스는 검증을 건너뛰는 것을 불가능하게 만드는 게 아니라 드러나게 만듭니다. 전체 목록은 보고서를 보세요.

## 기여, 보안, 라이선스

- [CONTRIBUTING.md](CONTRIBUTING.md): 정책 변경에는 차단 테스트와 허용 테스트가 둘 다 필요하고, 스킬 변경에는 전후 eval 점수가 필요합니다.
- [SECURITY.md](SECURITY.md): 우회 방법은 비공개로 신고해 주세요.
- [MIT 라이선스](LICENSE). openai/codex, openai/openai-agents-python, vercel/next.js, obra/superpowers, addyosmani/agent-skills, multica-ai/andrej-karpathy-skills, jbarbier/CLAUDE.md의 아이디어를 참고했고, 참고한 버전은 `agent-core/sources.lock.json`에 있습니다.
