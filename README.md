# bedrock-test

Amazon Bedrock 모델들이 실제로 호출되는지 한 번에 점검하는 스크립트.
모든 모델을 Converse API 하나로 호출하고, 텍스트 응답이 돌아왔는지로 PASS/FAIL을 판정한다.

## 점검 대상 모델

| 계열 | 모델 ID |
|---|---|
| Claude Sonnet 4.5 | `us.` / `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Claude Sonnet 4.6 | `us.` / `global.anthropic.claude-sonnet-4-6` |
| Claude Haiku 4.5 | `us.` / `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Nova Pro | `us.amazon.nova-pro-v1:0` |
| Nova 2 Lite | `us.` / `global.amazon.nova-2-lite-v1:0` |
| Nova Lite | `us.amazon.nova-lite-v1:0` |

목록은 `bedrock_check.py`의 `MODELS`에서 수정한다.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # AWS 자격증명 채우기
```

## 사용법

```bash
python run_check.py                # 전체 모델 (Converse)
python run_check.py --stream       # ConverseStream으로 확인
python run_check.py -m us.amazon.nova-lite-v1:0 -m global.anthropic.claude-sonnet-4-6
python run_check.py --prompt "1+1은?" --max-tokens 128
```

하나라도 실패하면 exit code 1, 자격증명이 없으면 2.

### 리포트용 출력

```bash
python report_check.py
```

`run_check.py` 결과에서 ANSI 색 코드를 지우고 맨 위에 헤더를 붙인다. Slack 같은 곳에 붙여넣기 좋은 평문이다.

```
STATUS=PASS
EXIT=0
TIME=2026-10-21 14:44 KST
---
region=us-east-1  mode=converse  models=10  prompt='Reply with exactly one word: OK'

PASS  us.anthropic.claude-sonnet-4-5-20250929-v1:0   1852ms in=14 out=4  'OK'
...
10/10 PASS
```

`.aside_deps/` 폴더가 있으면 PYTHONPATH에 자동으로 추가한다 (venv 없이 돌릴 때용).

### pytest

```bash
pytest -v              # 전체
pytest -v -k nova      # nova만
pytest -v -m stream    # 스트리밍 케이스만
```

## 파일 구성

| 파일 | 역할 |
|---|---|
| `bedrock_check.py` | 코어. 모델 목록, 클라이언트 생성, `invoke` / `invoke_stream` |
| `run_check.py` | CLI. 전체 모델 병렬 호출 후 PASS/FAIL 표 출력 |
| `report_check.py` | `run_check.py` 래퍼. 평문 리포트 출력 |
| `test_bedrock_models.py` | pytest 버전 |
| `.env.example` | 환경변수 템플릿 |

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | - | IAM 키 |
| `AWS_BEARER_TOKEN_BEDROCK` | - | Bedrock API 키 (IAM 키 대신) |
| `AWS_REGION` / `AWS_DEFAULT_REGION` | `us-east-1` | 리전 |
| `BEDROCK_TIMEOUT` | `60` | 읽기 타임아웃(초) |
| `BEDROCK_CONCURRENCY` | `4` | 동시 호출 수 |
