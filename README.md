# nami-ai

湘南エリアの波・風・潮・日照データから、サーファー目線でコンディションを判定する Phase 1-2 バックエンドです。

## セットアップ

```bash
uv sync
cp .env.example .env
```

`.env` に Gemini の API キーを設定します。

```bash
GOOGLE_API_KEY=your_google_api_key
```

`GOOGLE_API_KEY` がある場合は、LangChain の Tool Agent でデータ収集し、Gemini の structured output で `SurfForecast` を生成します。キーが未設定の場合も CLI 検証用に同じ実データからローカル判定フォールバックを返します。

## CLI

```bash
uv run python -m nami_ai.cli "明日の辻堂どう？"
```

対応ポイント:

- 鵠沼
- 辻堂
- 茅ヶ崎
- 七里ガ浜
- 由比ガ浜

## FastAPI

```bash
uv run uvicorn nami_ai.api.main:app --reload
```

確認:

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/forecast?query=明日の鵠沼どう？"
```

## テスト

`tests/test_tools.py` は Open-Meteo と tide736 の実 API を叩きます。

```bash
uv run pytest
```

## データソース

- Open-Meteo Marine API: 波高・波向・周期・うねり
- Open-Meteo Weather API: 風・気温・日の出・日の入り
- tide736 API: 江ノ島基準の満潮・干潮・潮名
