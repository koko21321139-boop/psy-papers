# psy-papers（精神科 新着論文）

PubMed から精神科の新着論文を毎朝自動で集め、iPhone で一覧表示するアプリです。

## しくみ

```
毎朝 6:07（日本時間）
  GitHub Actions（.github/workflows/fetch.yml）が scripts/fetch.py を実行
    → PubMed で 5 テーマ × 研究デザインを検索
    → data/papers.json に保存してコミット
  GitHub Pages が index.html と data/papers.json を配信
    → iPhone のアプリで一覧表示
```

## ファイル

| パス | 役割 |
|---|---|
| `scripts/fetch.py` | PubMed から論文を集めるプログラム（Python・標準ライブラリのみ） |
| `.github/workflows/fetch.yml` | 毎朝 fetch.py を動かす自動実行の設定 |
| `data/papers.json` | 集めた論文の一覧（自動で更新される） |
| `index.html` | アプリの画面（テーマ・研究デザインで絞り込み、★・既読） |
| `sw.js`・`manifest.webmanifest`・`icons/` | ホーム画面に追加して圏外でも開くための設定 |

## テーマと曜日

アプリを開いた曜日のテーマが最初に表示されます（月・木＝統合失調症、火・金＝気分障害、水＝認知症、土＝発達障害、日＝その他）。

## 変更したいとき

- 検索語：`scripts/fetch.py` の `TOPICS`（テーマ）、`DESIGN`（研究デザイン）
- 主要誌の一覧：`scripts/fetch.py` の `MAJOR`
- 実行時刻：`.github/workflows/fetch.yml` の `cron`（UTC で指定。日本時間 − 9 時間）

## 注意

- 保存するのは書誌情報（タイトル・雑誌・日付・著者・DOI）だけで、抄録は保存しません。
- 研究デザインはタイトル等から自動判定しており、誤りを含むことがあります。診療に用いる前に原文を確認してください。
