import sys
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import urllib.request
import boto3
from dotenv import load_dotenv
import jpholiday

base_dir = Path(__file__).resolve().parent
load_dotenv(base_dir / ".env")

if os.getenv("AWS_CA_BUNDLE"):
    os.environ["AWS_CA_BUNDLE"] = os.getenv("AWS_CA_BUNDLE")

today = datetime.now().date()
ENVIRONMENTS = ["dev", "uat", "prod", "hp", "back_prod"]

def is_business_day():
    if today.weekday() >= 5:
        print(f"本日（{today}）は土日のため処理をスキップ。")
        return False
    if jpholiday.is_holiday(today):
        holiday_name = jpholiday.is_holiday_name(today)
        print(f"本日（{today}）は祝日（{holiday_name}）のため処理をスキップ。")
        return False
    return True


def get_latest_execution_status(sfn_client, state_machine_arn):
    try:
        response = sfn_client.list_executions(
            stateMachineArn=state_machine_arn, maxResults=1
        )
        executions = response.get("executions", [])
        if not executions:
            return "実行履歴なし", "N/A", "N/A"

        latest = executions[0]
        status = latest["status"]
        name = latest["name"]

        start_date = latest.get("startDate")
        if start_date:
            jst_tz = timezone(timedelta(hours=9))
            exec_time = start_date.astimezone(jst_tz).strftime("%Y-%m-%d %H:%M:%S")
        else:
            exec_time = "N/A"

        return status, name, exec_time
    except Exception as e:
        return "ERROR", str(e), "N/A"


def send_google_chat(webhook_url, message, thread_name=None):
    url = webhook_url
    payload = {"text": message}

    if thread_name:
        url += "&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        payload["thread"] = {"name": thread_name}

    headers = {"Content-Type": "application/json; charset=UTF-8"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    with urllib.request.urlopen(req) as response:
        return response.status


def process_environment(env, target_group):
    config_path = base_dir / f"{env}_config.json"
    if not config_path.exists():
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    webhook_url = config.get("google_chat_webhook_url")
    thread_name = config.get("thread_name")
    
    if not webhook_url:
        return

    lines = [f"📊 *Step Functions 実行ステータス確認 [{env.upper()}]* 📊", ""]
    has_failure = False
    has_always_notify_target = False
    checked_count = 0

    for target in config.get("state_machines", []):
        if target_group and target.get("group") != target_group:
            continue

        checked_count += 1
        name = target["name"]
        arn = target["arn"]
        profile = target.get("profile")

        try:
            session = boto3.Session(profile_name=profile)
            sfn = session.client("stepfunctions")
        except Exception as e:
            lines.append(f"❌ *{name}*: `認証エラー`")
            has_failure = True
            continue

        if target.get("notif") is True:
            has_always_notify_target = True

        status, exec_name, exec_time = get_latest_execution_status(sfn, arn)

        if status == "SUCCEEDED":
            icon = "✅"
        elif status == "RUNNING":
            icon = "⏳"
        else:
            icon = "❌"
            has_failure = True

        lines.append(f"{icon} *{name}*: `{status}`")
        lines.append(f"    ├ 実行name: {exec_name}")
        lines.append(f"    └ 実行日時: {exec_time}")

    # 対象がない場合はスキップ
    if checked_count == 0:
        return

    should_send = has_failure or has_always_notify_target
    if not should_send:
        print(f"{today}：グループ [{target_group}] ：[{env.upper()}] 全件正常終了(または注視対象なし)のため通知スキップ。")
        return

    if has_failure:
        lines.insert(1, "⚠️ *失敗している処理があります！*")

    message_text = "\n".join(lines)
    send_google_chat(webhook_url, message_text, thread_name)
    print(f"{today}：グループ [{target_group}] ：[{env.upper()}] 通知を送信しました。")


def main():
    if not is_business_day():
        return

    # cron実行用に、引数がない場合は None、ある場合は group と見なす
    target_group = sys.argv[1] if len(sys.argv) > 1 else None

    # 各環境の config を順番に処理
    for env in ENVIRONMENTS:
        process_environment(env, target_group)


if __name__ == "__main__":
    main()