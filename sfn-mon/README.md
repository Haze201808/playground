# sfn-monitor (Step Functions Monitoring Tool)

AWS Step Functions の実行ステータス（成功・失敗・実行中）を定期的に監視し、  
Google Chat の環境別スレッドへまとめて通知するローカル運用向け lightweight ツール。  
複数環境(dev,uat等)を横断し、実行時刻に基づいたグループ単位で一括監視・通知する。

---

## 🚀 主な機能

- **マルチ環境・複数アカウント対応**:dev,uat,prodなどの複数アカウントを一元管理。
- **スレッド個別通知**:環境毎に指定されたGoogle Chatスレッドへ個別に結果を通知。
- **グループ自動判定**: 直近の実行開始日時（JST）を自動取得し、  
  監視実行タイミングに応じたグループ（0000, 1510, 1640 等）へ自動分類。
- **営業日自動判定**: jpholiday を使用し、土日および祝日は監視処理を自動スキップ。
- **注視ターゲット通知 (notif)**: 全件正常終了時は通知がスキップされるが、 設定ファイルで "notif": true が付与されたジョブは常時通知。
- **.env による設定管理**: AWS プロファイル名やスレッド情報、認証証明書パスを環境変数ファイルで管理。

---

## 🛠 動作環境・依存関係

- **OS**: WSL (Windows Subsystem for Linux) / Linux
- **Python**: 3.10 以上（仮想環境 `uvenv` 推奨）
- **依存ライブラリ**:
  - `boto3`
  - `jpholiday`
  - `python-dotenv`

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

- プロジェクトルートに .env を作成し、プロファイル名と通知先スレッドを設定。  
  ※ .env.example参照

### 3. Step Functions 一覧の取得・グループ自動同期

ARN一括取得用のスクリプト、export_sfns.pyを実行し、各環境のAWSから  
Step Functionsの一覧と直近の実行開始日時(JST)を取得。  
dev,uatなどの環境別の設定ファイルを自動生成。

- グループ自動分類ルール:
  - 夜間・早朝 (00:00〜08:59 / 18:00〜23:59 開始): グループ 0000 に集約。
  - 日中 (09:00〜17:59 開始): ジョブ開始時刻の 10分後 のグループ名  
    （例: 15:00開始 → 1510、16:30開始 → 1640）を自動付与。

- 集計ログ: 実行完了時、cron 設定の目安となるグループ一覧と件数をターミナル上に表示。

## 💻 使い方

手動実行

```
# 0000 グループのみチェック
python monitor.py 0000

# 1200 グループのみチェック
python monitor.py 1200

# 引数なし（一括チェック）
python monitor.py
```

## ⏰ 定期実行設定 (crontab)

cron で自動実行する場合は、環境変数の不一致を防ぐために仮想環境内の Python フルパスを指定。

```
# 12:10 実行（12:00 グループ）
10 12 * * 1-5 /home/hogehoge/uvenv/py313/bin/python /home/hogehoge/sfn-mon/monitor.py 1200 >> /home/hogehoge/sfn-mon/cron.log 2>&1

```

Note: 月〜金（1-5）の cron スケジュールに加え、monitor.py 内部の jpholiday チェックにより、  
日本の祝日当日は通知送信処理を自動的にスキップするようにした。
