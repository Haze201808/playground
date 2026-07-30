import json
import urllib.request
import boto3
import sys
import jpholiday
from datetime import datetime, timezone


def is_business_day():
    """今日が営業日（土日・祝日以外）かどうかを判定"""
    today = datetime.now().date()
    
    if today.weekday() >= 5:
        print(f"本日（{today}）は土日のため処理をスキップします。")
        return False
        
    if jpholiday.is_holiday(today):
        holiday_name = jpholiday.is_holiday_name(today)
        print(f"本日（{today}）は祝日（{holiday_name}）のため処理をスキップします。")
        return False
        
    return True

def load_config():
    with open("/home/hogehoge/sfn-mon/config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def get_latest_execution_status(sfn_client, state_machine_arn):
    """特定のStep Functionsの直近1件の実行結果を取得"""
    try:
        response = sfn_client.list_executions(
            stateMachineArn=state_machine_arn,
            maxResults=1
        )
        executions = response.get('executions', [])
        if not executions:
            return "実行履歴なし", "N/A"
        
        latest = executions[0]
        status = latest['status']  # 'SUCCEEDED', 'FAILED', 'RUNNING', 'TIMED_OUT' など
        name = latest['name']
        return status, name
    except Exception as e:
        print(f"[ERROR detail] {state_machine_arn} の取得に失敗しました:")
        print(f"  -> {e}")
        return "ERROR", str(e)

def send_google_chat(webhook_url, message, thread_name=None):
    """Google Chat Webhookへメッセージ送信"""
    url = webhook_url
    payload = {'text': message}
    
    # スレッド指定がある場合の処理
    if thread_name:
        # URLにスレッド投稿用のオプションを追加
        url += "&messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        # リクエストデータにスレッド情報を追加
        payload['thread'] = {'name': thread_name}
    
    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    with urllib.request.urlopen(req) as response:
        return response.status

def main():
    # 営業日チェック
    if not is_business_day():
        return
    
    config = load_config()
    sfn = boto3.client('stepfunctions')

    # config.jsonからグループ名を取得
    target_group = sys.argv[1] if len(sys.argv) > 1 else None
    
    lines = ["📊 *Step Functions 実行ステータス確認* 📊", ""]
    has_failure = False
    checked_count = 0

    for target in config["state_machines"]:
        if target_group and target.get("group") != target_group:
            continue
        
        checked_count += 1
        name = target["name"]
        arn = target["arn"]
        status, exec_name = get_latest_execution_status(sfn, arn)
        
        if status == "SUCCEEDED":
            icon = "✅"
        elif status == "RUNNING":
            icon = "⏳"
        else:
            icon = "❌"
            has_failure = True
            
        lines.append(f"{icon} *{name}*: `{status}`")
        lines.append(f"    └ 実行名: {exec_name}")

    if checked_count == 0:
        print(f"対象のグループ [{target_group}] が見つからないか、対象関数がありませんでした。")
        return

    if has_failure:
        lines.insert(1, "⚠️ *失敗している処理があります！*")
    
    # Google Chat へ送信
    message_text = "\n".join(lines)
    send_google_chat(
        config["google_chat_webhook_url"], 
        message_text, 
        config.get("thread_name")
    )
    print("通知を送信しました。")

if __name__ == "__main__":
    main()