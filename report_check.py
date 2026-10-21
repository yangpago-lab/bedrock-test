#!/usr/bin/env python3
"""run_check 결과를 Slack 코드블록에 바로 붙일 수 있는 평문으로 뽑는다."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main() -> int:
    env = dict(os.environ)
    deps = os.path.join(HERE, ".aside_deps")
    if os.path.isdir(deps):
        env["PYTHONPATH"] = deps + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "run_check.py"), *sys.argv[1:]],
        cwd=HERE, env=env, capture_output=True, text=True,
    )
    body = ANSI.sub("", (proc.stdout + proc.stderr)).strip()
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")

    print(f"STATUS={'PASS' if proc.returncode == 0 else 'FAIL'}")
    print(f"EXIT={proc.returncode}")
    print(f"TIME={now}")
    print("---")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
