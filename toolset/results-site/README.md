# ベンチマーク結果サイト生成

`results/<タイムスタンプ>/results.json` のうち**ディレクトリ名が辞書順で最大**のものを入力に、`index.html` を生成します。

## ローカル実行

```bash
python3 toolset/results-site/generate_site.py --repo-root . --out ./_site
# ./_site/index.html をブラウザで開く
```

特定の JSON を指定する場合:

```bash
python3 toolset/results-site/generate_site.py --repo-root . --input results/20260327152600/results.json --out ./_site
```

## Docker（ローカルで生成して手元で確認）

リポジトリルートでイメージをビルドし、ルートを読み取り専用でマウント、出力はホストの `./_site` に書き込みます。

# リポジトリルートで実行
```bash
docker build -t fb-results-site -f toolset/results-site/Dockerfile toolset/results-site

docker run --rm \
  -v "$(pwd):/workspace:ro" \
  -v "$(pwd)/_site:/out" \
  fb-results-site --repo-root /workspace --out /out
```

生成後、`./_site/index.html` をブラウザで開くか、次で簡易サーバを立てられます。

```bash
python3 -m http.server --directory _site 8765
# http://127.0.0.1:8765/
```

特定の `results.json` を使う場合（同様にビルド＋実行を1行）:

```bash
docker build -t fb-results-site -f toolset/results-site/Dockerfile toolset/results-site && docker run --rm -v "$(pwd):/workspace:ro" -v "$(pwd)/_site:/out" fb-results-site --repo-root /workspace --input /workspace/results/20260327152600/results.json --out /out
```

イメージが既に最新なら、`docker run` だけでも構いません。

## GitHub Pages

`.github/workflows/results-pages.yml` が `workflow_dispatch` および `results/**/results.json` 等の変更 push 時にサイトをビルドして Pages にデプロイします。

リポジトリの **Settings → Pages → Build and deployment** でソースに **GitHub Actions** を選んでください。

## 表示内容

- メタデータ（名前、UUID、環境、時刻、並行レベルなど）
- フレームワークごとの `verify`（pass / warn / fail）
- `rawData` に数値がある場合はテスト種別ごとの概算 RPS 等（空の場合は注記のみ）
