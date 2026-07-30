# sfn-mon (Step Functions Monitoring Tool)

AWS Step Functions の実行ステータス（成功・失敗・実行中）を定期的に監視し、  
Google Chat の指定スレッドへまとめて通知するローカル運用向け lightweight ツール。  
※開発環境で通知が来ないので作成。

---

## 🚀 主な機能

- **グループ化監視**: 実行時刻の近い複数の Step Functions を1つのグループにまとめ、1回の通知に集約。
- **営業日自動判定**: `jpholiday` を使用し、土日および日本の祝日は自動でスキップ。
- **スレッド通知**: Google Chat Webhook を使用し、指定のスレッド内に返信形式で結果を投稿。
- **AWS SSO対応**: ローカル環境（WSL等）の AWS SSO 認証情報を利用。

---

## 🛠 動作環境・依存関係

- **OS**: WSL (Windows Subsystem for Linux) / Linux
- **Python**: 3.10 以上（仮想環境 `uvenv` 推奨）
- **依存ライブラリ**:
  - `boto3`
  - `jpholiday`

---

## 📦 セットアップ

### 1. 依存ライブラリのインストール

仮想環境を有効化した状態で、以下のコマンドを実行。

```bash
python -m pip install --index-url [https://pypi.org/simple](https://pypi.org/simple) boto3 jpholiday
```

```
weztermなのでこっち
python -m pip install --index-url https://pypi.org/simple jpholiday
```

### 2. 設定ファイルの作成

プロジェクト直下に config.json.exampleをこぴーしてconfig.json を作成。  
監視対象の Step Functions や Webhook 情報を設定。

## 💻 使い方

手動実行

```
# 0000 グループのみチェック
python monitor.py 0000

# 1200 グループのみチェック
python monitor.py 1200
```

## ⏰ 定期実行設定 (crontab)

cron で自動実行する場合は、環境変数の不一致を防ぐために仮想環境内の Python フルパスを指定。

```
# 12:10 実行（12:00 グループ）
10 12 * * 1-5 /home/hogehoge/uvenv/py313/bin/python /home/hogehoge/sfn-mon/monitor.py 1200 >> /home/hogehoge/sfn-mon/cron.log 2>&1

```

Note: 月〜金（1-5）の cron スケジュールに加え、monitor.py 内部の jpholiday チェックにより、  
日本の祝日当日は通知送信処理を自動的にスキップするようにした。
