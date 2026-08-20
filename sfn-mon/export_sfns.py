import json
import os
from pathlib import Path
import boto3

# SSL証明書パスの設定
os.environ["AWS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"

# 対象の AWS プロファイル名
PROFILES = ["dev-account-a"]


def sync_config():
    base_dir = Path(__file__).resolve().parent
    config_path = base_dir / "config.json"

    # 1. 既存の config.json を読み込み
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    else:
        print("config.json を新規作成。")
        config_data = {
            "google_chat_webhook_url": "YOUR_WEBHOOK_URL",
            "thread_name": "YOUR_THREAD_NAME",
            "state_machines": [],
        }

    existing_sfns = {
        item["arn"]: item for item in config_data.get("state_machines", [])
    }

    # 2. AWSから現在の Step Function 一覧を取得
    current_aws_sfns = {}
    for profile in PROFILES:
        print(f"プロファイル [{profile}] から一覧を取得中...")
        try:
            session = boto3.Session(profile_name=profile)
            sfn = session.client("stepfunctions")
            paginator = sfn.get_paginator("list_state_machines")

            for page in paginator.paginate():
                for item in page["stateMachines"]:
                    arn = item["stateMachineArn"]
                    current_aws_sfns[arn] = {
                        "name": item["name"],
                        "arn": arn,
                        "profile": profile,
                    }
        except Exception as e:
            print(f"[ERROR] プロファイル [{profile}] の取得失敗: {e}")

    # 3. 差分マージ処理
    updated_sfns = []
    new_count = 0
    retained_count = 0

    for arn, aws_info in current_aws_sfns.items():
        if arn in existing_sfns:
            existing_item = existing_sfns[arn]
            existing_item["name"] = aws_info["name"] 
            existing_item["profile"] = aws_info["profile"]
            updated_sfns.append(existing_item)
            retained_count += 1
        else:
            new_item = {
                "name": aws_info["name"],
                "arn": arn,
                "group": "unassigned",  #新規のSFn グループは一旦 "unassigned"（未割り当て）
                "profile": aws_info["profile"],
            }
            updated_sfns.append(new_item)
            new_count += 1
            print(
                f"✨ 新規検出: {aws_info['name']} (group: 'unassigned' で追加)"
            )

    # 削除されたSFnの検知（AWS上に無くなったものをconfigから除外）
    deleted_count = len(existing_sfns) - retained_count

    # 4. config.json の更新保存
    config_data["state_machines"] = updated_sfns

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    print("\n--- 同期完了 ---")
    print(f"・既存保持: {retained_count} 件")
    print(f"・新規追加: {new_count} 件（'unassigned' で追加されました）")
    print(f"・削除除外: {deleted_count} 件（AWS上から消えたため削除）")


if __name__ == "__main__":
    sync_config()


