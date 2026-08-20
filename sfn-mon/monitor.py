from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import urllib.request
import boto3
import jpholiday

# SSL証明書パスの設定
os.environ["AWS_CA_BUNDLE"] = "/home/okuhira/.cert/odx_awscli_cert.pem"
today = datetime.now().date()

def is_business_day():
    # 営業日判定
    if today.weekday() >= 5:
        print(f"本日（{today}）は土日のため処理をスキップ。")
        return False

    if jpholiday.is_holiday(today):
        holiday_name = jpholiday.is_holiday_name(today)
        print(
            f"本日（{today}）は祝日（{holiday_name}）のため処理をスキップ。"
        )
        return False

    return True


def load_config():
    base_dir = Path(__file__).resolve().parent
    config_path = base_dir / "config.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


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
            exec_time = start_date.astimezone(jst_tz).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            exec_time = "N/A"

        return status, name, exec_time
    except Exception as e:
        print(f"[ERROR detail] {state_machine_arn} の取得に失敗した:")
        print(f"  -> {e}")
        return "ERROR", str(e), "N/A"


def send_google_chat(webhook_url, message, thread_name=None):
    # Google Chatへの送信処理
    url = webhook_url
    payload = {"text": message}

    if thread_name:
        url += "&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        payload["thread"] = {"name": thread_name}

    headers = {"Content-Type": "application/json; charset=UTF-8"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST"
    )

    with urllib.request.urlopen(req) as response:
        return response.status


def main():
    if not is_business_day():
        return

    config = load_config()
    target_group = sys.argv[1] if len(sys.argv) > 1 else None

    lines = ["📊 *Step Functions 実行ステータス確認* 📊", ""]
    has_failure = False
    has_always_notify_target = False
    checked_count = 0

    for target in config["state_machines"]:
        if target_group and target.get("group") != target_group:
            continue

        checked_count += 1
        name = target["name"]
        arn = target["arn"]
        profile = target.get("profile")

        try:
            if profile:
                session = boto3.Session(profile_name=profile)
                sfn = session.client("stepfunctions")
            else:
                sfn = boto3.client("stepfunctions")
        except Exception as e:
            print(
                f"[PROFILE ERROR] プロファイル [{profile}] の読み込みに失敗: {e}"
            )
            lines.append(f"❌ *{name}*: `認証エラー (Profile: {profile})`")
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

    if checked_count == 0:
        print(
            f"{today}：対象のグループ [{target_group}] が見つからないか、対象関数がありませんでした。"
        )
        return

    should_send = has_failure or has_always_notify_target

    if not should_send:
        print(
            f"{today}：グループ [{target_group}] は全件正常終了かつ注視対象もないため、通知をスキップ。"
        )
        return

    if has_failure:
        lines.insert(1, "⚠️ *失敗している処理があります！*")

    message_text = "\n".join(lines)
    send_google_chat(
        config["google_chat_webhook_url"],
        message_text,
        config.get("thread_name"),
    )
    print(f"{today}：通知を送信しました。")


if __name__ == "__main__":
    main()