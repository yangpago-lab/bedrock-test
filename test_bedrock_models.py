"""pytest 버전. 모델마다 테스트 케이스가 하나씩 생긴다.

  pytest -v                      # 전체
  pytest -v -k nova              # nova 만
  pytest -v -m stream            # 스트리밍 케이스만
"""

from __future__ import annotations

import pytest

from bedrock_check import MODELS, credentials_missing, invoke, invoke_stream, make_client

pytestmark = pytest.mark.skipif(
    credentials_missing() is not None,
    reason=credentials_missing() or "",
)


@pytest.fixture(scope="session")
def client():
    return make_client()


@pytest.mark.parametrize("model_id", MODELS)
def test_converse_returns_text(model_id, client):
    r = invoke(model_id, client)
    assert r.ok, f"{model_id} 실패 [{r.error_code}] {r.error}"
    assert r.text, f"{model_id} 응답 텍스트가 비어 있다"
    assert r.usage.get("outputTokens", 0) > 0, f"{model_id} outputTokens 가 0"
    print(f"\n{model_id}: {r.latency_ms}ms {r.text[:60]!r} usage={r.usage}")


@pytest.mark.stream
@pytest.mark.parametrize("model_id", MODELS)
def test_converse_stream_returns_deltas(model_id, client):
    r = invoke_stream(model_id, client)
    assert r.ok, f"{model_id} 스트리밍 실패 [{r.error_code}] {r.error}"
    print(f"\n{model_id}(stream): {r.latency_ms}ms {r.text[:60]!r}")
