"""PlatformIO 빌드 전 훅 — 생성물이 소스와 어긋나면 빌드를 세운다.

`pio test -e native` 는 팀원 누구나 항상 돌린다. 가드를 여기 붙이면 CI 를 기다릴 것도 없이
로컬에서 즉시 걸린다.

왜 필요한가 — 이슈 #12 에서 실제로 터졌다:
  templates.py 를 16/32px 로 고쳤는데 templates.h 재생성을 잊었다.
  서버는 max_bytes 54B 로 막고 펌웨어는 60B 로 알고, 제목을 24px 로 렌더해 글자가 잘렸다.
  **아무 테스트도 깨지지 않았다.** 사람이 생성기를 수동으로 돌려보고서야 찾았다.

golden_vectors.h 쪽이 더 조용하고 위험하다. 서버 프로토콜이 바뀌었는데 재생성을 안 하면
C++ 테스트가 옛 바이트에 대고 통과하면서 와이어 포맷 불일치를 못 잡는다 — 상호 검증의
근거 자체가 썩는다.

두 생성기 모두 표준 라이브러리만 쓴다(app/protocol 은 dataclass·순수 함수뿐) — 서버 의존성
설치 없이 돈다.
"""

import subprocess
import sys
from pathlib import Path

Import("env")  # noqa: F821  (PlatformIO 가 주입)

ROOT = Path(env.subst("$PROJECT_DIR")).parent  # noqa: F821

CHECKS = [
    ("templates.h  == templates.py", ROOT / "tools" / "gen_templates.py"),
    ("golden_vectors.h == app/protocol", ROOT / "tools" / "gen_test_vectors.py"),
]


def main() -> None:
    failed = []
    for label, script in CHECKS:
        if not script.exists():
            continue
        r = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if r.returncode != 0:
            failed.append(f"{label}\n    {(r.stdout + r.stderr).strip()}")

    if not failed:
        return

    # PlatformIO 는 pre 스크립트의 stdout 을 삼킨다 — 이유를 못 보면 가드가 쓸모없다.
    # stderr 로 직접 쓰고 flush 한 뒤, SystemExit 에 메시지를 실어 한 번 더 남긴다.
    banner = "\n".join(
        [
            "",
            "=" * 78,
            "[drift] 생성물이 소스와 어긋납니다 — 빌드를 세웁니다.",
            "=" * 78,
            *(f"  {f}" for f in failed),
            "=" * 78,
            "",
        ]
    )
    sys.stderr.write(banner)
    sys.stderr.flush()
    raise SystemExit(banner)


main()
