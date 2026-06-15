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
uv run python -m nami_ai.cli "明後日の鵠沼どう？"
uv run python -m nami_ai.cli "2026/06/20の茅ヶ崎どう？"
```

対応ポイント:

- 鵠沼
- 辻堂
- 茅ヶ崎
- 七里ガ浜
- 由比ガ浜

対応している日付表現:

- 今日
- 明日
- 明後日 / あさって
- `YYYY-MM-DD`
- `YYYY/MM/DD`

CLI 出力にはスコア、入る価値、波・風、推奨時間、一言コメントに加えて、判断理由を箇条書きで表示します。

## FastAPI

```bash
uv run uvicorn nami_ai.api.main:app --reload
```

確認:

```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/forecast?query=明日の鵠沼どう？"
curl -X POST http://127.0.0.1:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"query":"明後日の辻堂どう？"}'
```

`/forecast` は `SurfForecast` JSON を返します。主なフィールド:

- `score`: 1〜5 の総合スコア
- `rideable`: ライダープロファイル的に入る価値があるか
- `wave_size`: 湘南の体感サイズ
- `best_windows`: 潮の動きやサンセットを考慮した推奨時間
- `reasons`: 判断理由の配列
- `summary`: サーファー目線の一言
- `caution`: 注意点。なければ `null`

未対応ポイントなど、入力が仕様に合わない場合は `400 Bad Request` を返します。
外部 API や Gemini が失敗した場合は、可能な範囲で明確なエラーまたはローカル判定フォールバックを返します。

## テスト

`tests/test_tools.py` は Open-Meteo と tide736 の実 API を叩きます。

```bash
uv run pytest
```

現在のテスト範囲:

- CLI の表示整形と実行経路
- FastAPI `/health` / `/forecast`
- Open-Meteo / tide736 の実 API パース
- 外部 API 失敗時のエラー変換
- Gemini 失敗時のローカル判定 fallback
- 自然言語の日付・ポイント解釈
- ローカル判定の rideable / score / reasons

## データソース

- Open-Meteo Marine API: 波高・波向・周期・うねり
- Open-Meteo Weather API: 風・気温・日の出・日の入り
- tide736 API: 江ノ島基準の満潮・干潮・潮名
