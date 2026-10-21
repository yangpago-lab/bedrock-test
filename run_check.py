#!/usr/bin/env python
"""모델 전체를 호출해서 PASS/FAIL 표로 뿌린다.

  python run_check.py              # 전체 모델 (Converse)
  python run_check.py --stream     # 스트리밍으로도 확인
  python run_check.py -m us.amazon.nova-lite-v1:0 -m global.anthropic.claude-sonnet-4-6
  python run_check.py --prompt "1+1은?" --max-tokens 128

하나라도 실패하면 exit code 1.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

from bedrock_check import (
    CONCURRENCY,
    MODELS,
    PROMPT,
    REGION,
    Result,
    credentials_missing,
    invoke,
    invoke_stream,
    make_client,
)

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def one_line(r: Result, width: int) -> str:
    mark = f"{GREEN}PASS{RESET}" if r.ok else f"{RED}FAIL{RESET}"
    usage = ""
    if r.usage:
        usage = f" {DIM}in={r.usage.get('inputTokens', '-')} out={r.usage.get('outputTokens', '-')}{RESET}"
    detail = repr(r.text[:60]) if r.ok else f"{r.error_code}: {r.error[:140]}"
    return f"{mark}  {r.model_id:<{width}}  {r.latency_ms:>6}ms{usage}  {detail}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", action="append", dest="models",
                    help="특정 모델만 검사 (반복 지정 가능)")
    ap.add_argument("--stream", action="store_true", help="ConverseStream 으로 호출")
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--region", default=REGION)
    args = ap.parse_args()

    if reason := credentials_missing():
        print(f"{RED}자격증명 없음{RESET} — {reason}", file=sys.stderr)
        return 2

    models = args.models or MODELS
    width = max(len(m) for m in models)
    client = make_client(args.region)
    call = invoke_stream if args.stream else invoke
    mode = "converse_stream" if args.stream else "converse"

    print(f"region={args.region}  mode={mode}  models={len(models)}  prompt={args.prompt!r}\n")

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(
            lambda m: call(m, client, args.prompt, args.max_tokens), models
        ))

    for r in results:
        print(one_line(r, width))

    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} PASS")
    if failed:
        print(f"{RED}실패:{RESET} " + ", ".join(r.model_id for r in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
