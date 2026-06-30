#!/bin/bash

# ==========================================
# Google Chatのスペースリンクはスペース名 
# → アプリと統合 → Webhockを追加
# → 名前を付けて保存 → URLを取得
# ※機械が通知したものにしかツリー対応できないので、
#   ツリー対応にするなら一通飛ばす必要がある。
# ==========================================

WEB_URL="[Google Chatのスペースリンク]"

SPACE_ID="[Google ChatのスペースID]"
THREAD_ID="[Google ChatのthreadID]"
THREAD_NAME="spaces/${SPACE_ID}/threads/${THREAD_ID}"

MESSAGE="テスト01"
TARGET_DATE=${1:-$(date +%Y-%m-%d)}
LOG_FILE="./s3_debug.log"
# --- 通知実行 ---

# ==========================================
# 祝日判定
# HTTPのステータスコードで判定
# download_daily.shの祝日判定検証用
# ==========================================

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://holiday-jp.github.io/api/v1/date/${TARGET_DATE}.json")

if [ "$HTTP_STATUS" -eq 200 ]; then
    # 祝日の場合、一応名前を取得
    HOLIDAY_NAME=$(curl -s "https://holiday-jp.github.io/api/v1/date/${TARGET_DATE}.json")
    echo "$(date) [SKIP] 今日は祝日（${HOLIDAY_NAME}）のためスキップします" >> "$LOG_FILE"
    echo "祝日のためスキップします: ${HOLIDAY_NAME}"
    exit 0
else
    echo "平日（または祝日データなし）と判断し、続行します (Status: ${HTTP_STATUS})"
fi


curl -s -X POST -H 'Content-Type: application/json; charset=UTF-8' \
    -d "{
        \"text\": \"${MESSAGE}\",
        \"thread\": {\"name\": \"${THREAD_NAME}\"}
    }" \
    "${WEB_URL}"
