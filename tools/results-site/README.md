# ベンチマーク結果サイト生成

`results/<タイムスタンプ>/results.json` のうち**ディレクトリ名が辞書順で最大**のものを入力に、`index.html` を生成します。

## ローカル実行

```bash
python3 tools/results-site/generate_site.py --repo-root . --out ./_site
# ./_site/index.html をブラウザで開く
```

特定の JSON を指定する場合:

```bash
python3 tools/results-site/generate_site.py --repo-root . --input results/20260327152600/results.json --out ./_site
```

## GitHub Pages

`.github/workflows/results-pages.yml` が `workflow_dispatch` および `results/**/results.json` 等の変更 push 時にサイトをビルドして Pages にデプロイします。

リポジトリの **Settings → Pages → Build and deployment** でソースに **GitHub Actions** を選んでください。

## 表示内容

- メタデータ（名前、UUID、環境、時刻、並行レベルなど）
- フレームワークごとの `verify`（pass / warn / fail）
- `rawData` に数値がある場合はテスト種別ごとの概算 RPS 等（空の場合は注記のみ）
