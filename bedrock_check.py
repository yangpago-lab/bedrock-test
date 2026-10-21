"""Bedrock 모델 호출 점검 코어.

모든 모델을 Converse API 하나로 때린다. Anthropic/Nova 페이로드를 따로
만들 필요가 없고, 응답 파싱도 동일하다.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

MODELS: list[str] = [
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "us.anthropic.claude-sonnet-4-6",
    "global.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-pro-v1:0",
    "us.amazon.nova-2-lite-v1:0",
    "global.amazon.nova-2-lite-v1:0",
    "us.amazon.nova-lite-v1:0",
]

PROMPT = "Reply with exactly one word: OK"
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
TIMEOUT = int(os.getenv("BEDROCK_TIMEOUT", "60"))
CONCURRENCY = int(os.getenv("BEDROCK_CONCURRENCY", "4"))


def _blank(name: str) -> bool:
    return not (os.getenv(name) or "").strip()


def credentials_missing() -> str | None:
    """자격증명이 하나도 안 채워졌으면 사유 문자열, 정상이면 None."""
    if not _blank("AWS_BEARER_TOKEN_BEDROCK"):
        return None
    if _blank("AWS_ACCESS_KEY_ID") or _blank("AWS_SECRET_ACCESS_KEY"):
        return (
            ".env 에 AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY 또는 "
            "AWS_BEARER_TOKEN_BEDROCK 중 하나를 채워야 한다"
        )
    return None


def make_client(region: str = REGION):
    # 빈 문자열이 실제 자격증명으로 잡히면 서명이 깨지므로 걸러낸다.
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "AWS_BEARER_TOKEN_BEDROCK"):
        if _blank(key):
            os.environ.pop(key, None)

    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            read_timeout=TIMEOUT,
            connect_timeout=10,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


@dataclass
class Result:
    model_id: str
    ok: bool
    latency_ms: int = 0
    text: str = ""
    stop_reason: str = ""
    usage: dict = field(default_factory=dict)
    error_code: str = ""
    error: str = ""

    @property
    def status(self) -> str:
        return "PASS" if self.ok else "FAIL"


def invoke(model_id: str, client=None, prompt: str = PROMPT, max_tokens: int = 64) -> Result:
    """모델 하나를 Converse 로 호출하고 실제 텍스트가 돌아왔는지 판정한다."""
    client = client or make_client()
    started = time.perf_counter()
    try:
        resp = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
        )
    except ClientError as exc:
        return Result(
            model_id=model_id,
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code=exc.response.get("Error", {}).get("Code", "ClientError"),
            error=exc.response.get("Error", {}).get("Message", str(exc)),
        )
    except BotoCoreError as exc:
        return Result(
            model_id=model_id,
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code=type(exc).__name__,
            error=str(exc),
        )

    latency = int((time.perf_counter() - started) * 1000)
    blocks = resp.get("output", {}).get("message", {}).get("content", [])
    text = "".join(b.get("text", "") for b in blocks).strip()
    usage = resp.get("usage", {}) or {}

    if not text:
        return Result(
            model_id=model_id,
            ok=False,
            latency_ms=latency,
            stop_reason=resp.get("stopReason", ""),
            usage=usage,
            error_code="EmptyResponse",
            error="200 은 왔지만 텍스트 블록이 비어 있다",
        )

    return Result(
        model_id=model_id,
        ok=True,
        latency_ms=latency,
        text=text,
        stop_reason=resp.get("stopReason", ""),
        usage=usage,
    )


def invoke_stream(model_id: str, client=None, prompt: str = PROMPT, max_tokens: int = 64) -> Result:
    """스트리밍(ConverseStream)으로도 델타가 실제로 흘러오는지 확인한다."""
    client = client or make_client()
    started = time.perf_counter()
    try:
        resp = client.converse_stream(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
        )
        chunks, stop_reason, usage = [], "", {}
        for event in resp["stream"]:
            if "contentBlockDelta" in event:
                chunks.append(event["contentBlockDelta"]["delta"].get("text", ""))
            elif "messageStop" in event:
                stop_reason = event["messageStop"].get("stopReason", "")
            elif "metadata" in event:
                usage = event["metadata"].get("usage", {}) or {}
    except (ClientError, BotoCoreError) as exc:
        code = (
            exc.response.get("Error", {}).get("Code", "ClientError")
            if isinstance(exc, ClientError)
            else type(exc).__name__
        )
        return Result(
            model_id=model_id,
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code=code,
            error=str(exc),
        )

    text = "".join(chunks).strip()
    return Result(
        model_id=model_id,
        ok=bool(text),
        latency_ms=int((time.perf_counter() - started) * 1000),
        text=text,
        stop_reason=stop_reason,
        usage=usage,
        error_code="" if text else "EmptyStream",
        error="" if text else "스트림에 델타가 하나도 없다",
    )
