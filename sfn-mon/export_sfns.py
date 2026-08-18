import json
import os
from pathlib import Path
import boto3

# ★ 対象の AWS プロファイル名を指定
PROFILES = ["dev-account-a"]


def export_state_machines():
    # SSL エラー対策
    os.environ["AWS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"

    all_sfns = []

    for profile in PROFILES:
        print(f"プロファイル [{profile}] から Step Functions 一覧を取得中...")
        try:
            session = boto3.Session(profile_name=profile)
            sfn = session.client("stepfunctions")

            # ページネーション対応
            paginator = sfn.get_paginator("list_state_machines")
            for page in paginator.paginate():
                for item in page["stateMachines"]:
                    all_sfns.append(
                        {
                            "name": item["name"],
                            "arn": item["stateMachineArn"],
                            "group": "1530",  # 仮でグループ名を指定
                            "profile": profile,
                            # "notify_on_success": True # 開発中のものだけ後で有効化
                        }
                    )
        except Exception as e:
            print(f"プロファイル [{profile}] の取得に失敗しました: {e}")

    # config.json の雛形データを作成
    draft_config = {
        "google_chat_webhook_url": "MY_WEBHOOK_URL",
        "thread_name": "MY_THREAD_NAME",
        "state_machines": all_sfns,
    }

    base_dir = Path(__file__).resolve().parent
    output_path = base_dir / "config_draft.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(draft_config, f, ensure_ascii=False, indent=2)

    print(f"\n完了！合計 {len(all_sfns)} 件を取得し、{output_path.name} に保存しました。")


if __name__ == "__main__":
    export_state_machines()