# aurora-table-diff

Auroraの複数テーブルについて、1日1回スナップショットを取得し、前回との差分を記録するCLIツール。  
A5と同じ「DB直接接続」方式（AWS API/Secrets Managerを経由しない）。

## 動作の流れ

コマンドを実行するたびに、`config.json`の`tables`に書いた各テーブルについて以下を行う。

1. 今回分のデータを取得（B）
2. `snapshots/<テーブル名>.json` に前回分（A）があれば、AとBを比較してdiffを
   `diffs/<今日の日付>_<テーブル名>.json` に保存する（**差分の有無に関わらず必ず保存**）
3. Aは `archive/<Aが取得された日付>_<テーブル名>.json` に移動する
4. Bを `snapshots/<テーブル名>.json` として保存する

結果として、1日の実行が終わると `snapshots/` には常に「最新1件」だけが残り、  
過去分は `archive/日付/` に、その日の差分は `diffs/日付/` に積み上げる。

初回実行時（`snapshots/<テーブル名>.json`がまだ無い時）はdiffは作られず、今回分がそのままsnapshotとして保存する。

## セットアップ

```bash
cd aurora-table-diff
go mod tidy   # github.com経由でlib/pqを取得（社内プロキシ等があれば適宜設定）
cp config.example.json config.json
```

`config.json` を編集（`tables` に監視したいテーブルを追加する）:

```jsonc
{
  "host": "your-aurora-endpoint...rds.amazonaws.com", // A5の接続設定と同じホスト
  "port": 5432,
  "user": "your_db_user",
  "password": "your_db_password",
  "dbname": "your_db_name",
  "sslmode": "require",
  "tables": [
    {
      "name": "schema_name.table_a",
      "order_by": "id", // 差分比較のキーにするカラム（主キー推奨）
      "columns": [], // 空ならSELECT *
    },
    {
      "name": "schema_name.table_b",
      "order_by": "id",
      "columns": ["id", "status", "updated_at"], // 特定カラムだけ見たい場合
    },
  ],
}
```

## 使い方

```bash
go run . run
```

これを1日1回実行する（Windowsタスクスケジューラ等から定期実行する想定）。

## diff結果をCSVで見たいとき

```bash
go run . csv              # 当日分のdiffをCSV化
go run . csv 20260710     # 指定日付分をCSV化
```

`diffs/<日付>_<テーブル名>.json` の隣に `diffs/<日付>_<テーブル名>.csv` が作られる。
列は `type,key,field,before,after` で、1行が「どの行(key)のどのカラム(field)が
追加(added)/削除(removed)/変更(changed)されたか」を表す。  
Excelで開いてそのまま人に見せたいときに使用予定（対象のdiff jsonが無い日はスキップされる）。

## 出力ファイル

- `snapshots/<テーブル名>.json` — 最新1件のスナップショット。`{"date": "20260716", "rows": [...]}`という形式
- `archive/<日付>_<テーブル名>.json` — 過去のスナップショット（上と同じ形式）
- `diffs/<日付>_<テーブル名>.json` — その日の差分結果。形式:

```jsonc
{
  "table": "schema_name.table_a",
  "before_date": "20260715",
  "after_date": "20260716",
  "added": [
    /* 追加された行 */
  ],
  "removed": [
    /* 削除された行 */
  ],
  "changed": [
    {
      "id": 123, // order_byで指定したカラムの値
      "fields": {
        "status": { "before": "pending", "after": "done" },
      },
    },
  ],
}
```

差分が無い日でも `added`/`removed`/`changed` が空配列のファイルとして保存。

## Windowsタスクスケジューラでの定期実行例

サインアウト状態でも動かしたい場合、タスクの設定で「ユーザーがログオンしているかどうかにかかわらず実行する」にチェックし、  
アクションに以下のように指定。

```
プログラム: wsl.exe
引数: -d Ubuntu -e bash -c "cd /home/youruser/aurora-table-diff && go run . run"
```

事前に一度ビルドしておいた `go build -o tracker .` の実行ファイルを直接叩く形にすると起動が速く、
毎回のgoモジュール解決も走らないのでおすすめ。

```
引数: -d Ubuntu -e bash -c "cd /home/youruser/aurora-table-diff && ./tracker run"
```

## cronでの定期実行例

`go build -o tracker .`しておく

```
0 9 * * * cd /home/youruser/aurora-table-diff && ./tracker run >> cron.log 2>&1
```

## 注意点

- `order_by` に指定したカラムは行の同一性判定に使うので、主キー（一意な値）を指定する。
- `changed`の差分は各カラムの値を文字列化して単純比較しているので、`timestamp`型やJSON型カラムのフォーマット差分も検知。  
   見たくない場合は`columns`で対象を絞る。
- スキーマが分かれている場合は`name`に`スキーマ名.テーブル名`の形で指定。
