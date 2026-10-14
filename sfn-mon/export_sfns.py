import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter
import boto3
from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent
load_dotenv(base_dir / ".env")

if os.getenv("AWS_CA_BUNDLE"):
    os.environ["AWS_CA_BUNDLE"] = os.getenv("AWS_CA_BUNDLE")

ENVIRONMENTS = ["dev", "uat", "prod", "back_prod"]
JST = timezone(timedelta(hours=9))

# 既に手動でグループ設定したものを維持したい場合は False、全件再計算したい場合は True
FORCE_OVERWRITE_GROUP = False


def determine_group(last_started_at: str) -> str:
    """開始時刻からグループ名を自動判定"""
    if not last_started_at or last_started_at in ["N/A", "実行履歴なし"] or last_started_at.startswith("取得失敗"):
        return "unassigned"

    try:
        dt = datetime.strptime(last_started_at, "%Y-%m-%d %H:%M:%S")
        hour = dt.hour

        # 1. 0時～9時未満 (0:00〜8:59) または 18時～24時未満 (18:00〜23:59)
        if (0 <= hour < 9) or (18 <= hour < 24):
            return "0000"

        # 2. 9時～18時未満 (9:00〜17:59)
        # 秒のズレを切り捨てたうえで +10分 を計算 (例: 15:00:25 -> 15:10 -> "1510")
        if 9 <= hour < 18:
            base_time = dt.replace(second=0, microsecond=0)
            target_time = base_time + timedelta(minutes=10)
            return target_time.strftime("%H%M")

        return "unassigned"
    except Exception:
        return "unassigned"


def get_latest_start_time(sfn_client, sfn_arn):
    """最新の実行開始時刻 (JST) を取得"""
    try:
        response = sfn_client.list_executions(
            stateMachineArn=sfn_arn,
            maxResults=1
        )
        executions = response.get("executions", [])
        if not executions:
            return "実行履歴なし"

        start_date = executions[0].get("startDate")
        if start_date:
            return start_date.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")
        return "N/A"
    except Exception as e:
        return f"取得失敗: {e}"


def sync_config():
    webhook_url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "YOUR_WEBHOOK_URL")

    for env in ENVIRONMENTS:
        profile = os.getenv(f"PROFILE_{env.upper()}")
        thread_name = os.getenv(f"THREAD_{env.upper()}", f"THREAD_{env.upper()}")
        config_path = base_dir / f"{env}_config.json"

        if not profile:
            continue

        print(f"\n{'='*50}")
        print(f"🔄 [{env.upper()}] 環境の同期を開始 (Profile: {profile})")
        print(f"{'='*50}")

        # 1. 既存 config の読み込み
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        else:
            config_data = {
                "env": env,
                "google_chat_webhook_url": webhook_url,
                "thread_name": thread_name,
                "state_machines": []
            }

        existing_sfns = {item["arn"]: item for item in config_data.get("state_machines", [])}

        # 2. AWSから一覧と直近の実行時間を取得
        current_aws_sfns = {}
        try:
            session = boto3.Session(profile_name=profile)
            sfn = session.client("stepfunctions")

            paginator = sfn.get_paginator("list_state_machines")
            for page in paginator.paginate():
                for item in page["stateMachines"]:
                    arn = item["stateMachineArn"]
                    latest_time = get_latest_start_time(sfn, arn)

                    current_aws_sfns[arn] = {
                        "name": item["name"],
                        "arn": arn,
                        "last_started_at": latest_time
                    }
        except Exception as e:
            print(f"[ERROR] {env} (Profile: {profile}) の取得失敗: {e}")
            continue

        # 3. 差分マージ ＆ グループ自動割り当て
        updated_sfns = []
        new_count, retained_count = 0, 0

        for arn, aws_info in current_aws_sfns.items():
            calc_group = determine_group(aws_info["last_started_at"])

            if arn in existing_sfns:
                existing_item = existing_sfns[arn]
                existing_item["name"] = aws_info["name"]
                existing_item["last_started_at"] = aws_info["last_started_at"]
                existing_item["profile"] = profile

                # グループの自動判定（未設定の場合、または強制上書きの場合）
                current_group = existing_item.get("group")
                if FORCE_OVERWRITE_GROUP or current_group in [None, "unassigned", ""]:
                    existing_item["group"] = calc_group

                updated_sfns.append(existing_item)
                retained_count += 1
            else:
                new_item = {
                    "name": aws_info["name"],
                    "arn": arn,
                    "group": calc_group,
                    "last_started_at": aws_info["last_started_at"],
                    "profile": profile
                }
                updated_sfns.append(new_item)
                new_count += 1
                print(f"  ✨ 新規: {aws_info['name']} -> Group: [{calc_group}]")

        config_data["google_chat_webhook_url"] = webhook_url
        config_data["thread_name"] = thread_name
        config_data["state_machines"] = updated_sfns

        # 4. config 保存
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        # 5. グループ集計ログの出力
        group_counts = Counter(item.get("group", "unassigned") for item in updated_sfns)
        sorted_groups = sorted(group_counts.keys())

        print(f"\n📊 [{env.upper()}] グループ集計結果 (全 {len(updated_sfns)} 件)")
        print(f"・作成されたグループ一覧 (Cron設定の目安):")
        print(f"  {sorted_groups}")
        print("・各グループの内訳:")
        for grp in sorted_groups:
            print(f"    - グループ [{grp}]: {group_counts[grp]:>2} 件")


if __name__ == "__main__":
    sync_config()