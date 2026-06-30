#!/bin/bash

export HOME="/home/"
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH}"

# cron環境用に設定
export AWS_CA_BUNDLE="/home/.cert/hogehoge.pem"
export REQUESTS_CA_BUNDLE="/home/.cert/hogehoge.pem"

PROFILE="AWSのアカウントID"
BUCKET_ROOT="s3://[S3のバケット名]"
DEST_PAID="/mnt/g/[Gドライブのフォルダを指定]"


LOG_FILE="./s3_debug.log"
# 個人用スペース
WEB_URL="[Google Chatのスペースリンク]"
SPACE_ID="[Google ChatのスペースID]"
THREAD_ID="[Google ChatのthreadID]"
THREAD_NAME="spaces/${SPACE_ID}/threads/${THREAD_ID}"

TARGET_DATE=${1:-$(date +%Y-%m-%d)}
S3_PATH="${BUCKET_ROOT}/${TARGET_DATE}/"


# ==========================================
# マウント・チェック
# (Gドライブとの接続が切れている場合につなぎ直す)
# ==========================================
if ! mountpoint -q /mnt/g; then
    echo "Gドライブがマウントされていません。再接続を試みます..."
    sudo umount -l /mnt/g 2>>/s3_debug.log
    sudo mount -t drvfs G: /mnt/g
    
    # 再試行してもダメな場合は、チャットに投げて終了
    if ! mountpoint -q /mnt/g; then
        MESSAGE="🚨 【致命的エラー】\nWSLからGドライブ(/mnt/g)にアクセスできません。\nマウントを手動で確認してください。"
        curl -s -X POST -H 'Content-Type: application/json; charset=UTF-8' \
            -d "{\"text\": \"${MESSAGE}\", \"thread\": {\"name\": \"${THREAD_NAME}\"}}" \
            "${WEB_URL}" > /dev/null
        exit 1
    fi
fi

echo "--- 手動/テスト実行 ---"
echo "指定された日付: ${TARGET_DATE}"
echo "S3パスを確認します: ${S3_PATH}"

# ==========================================
# 祝日判定
# HTTPのステータスコードで判定
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

# S3にファイルがあるかを確認
S3_CHECK=$(aws s3 ls "${S3_PATH}" --profile "${PROFILE}" 2>>/s3_debug.log)

if [ -z "$S3_CHECK" ]; then
    # リストが空（ファイルがない）場合
    MESSAGE="<users/all> ⏳ 【S3未配置】\n対象日: ${TARGET_DATE}\nS3にファイルがまだ置かれていないようです。後ほど再試行してください。"
    # ここで通知して終了
    curl -s -X POST -H 'Content-Type: application/json; charset=UTF-8' \
        -d "{\"text\": \"${MESSAGE}\", \"thread\": {\"name\": \"${THREAD_NAME}\"}}" \
        "${WEB_URL}" > /dev/null
    exit 0
fi

echo echo "--- DL開始... ---"
# JSONをDL
aws s3 cp "${S3_PATH}" "${DEST_PAID}/" --recursive --exclude "*" --include "*.json" --profile "${PROFILE}"
RES_JSON=$?

# CSVをDL
aws s3 cp "${S3_PATH}" "${DEST_FREE}/" --recursive --exclude "*" --include "*.csv" --profile "${PROFILE}"
RES_CSV=$?

# ==========================================
# Chatへ通知
# ==========================================
if [ -n "$(ls -A "${DEST_PAID}"/*.json 2>>/s3_debug.log)" ] && [ -n "$(ls -A "${DEST_FREE}"/*.csv 2>>/s3_debug.log)" ]; then
    MESSAGE="<users/all> ✅ 【S3自動取込成功】\n対象日: ${TARGET_DATE}\n有償/無償フォルダへファイルを保存しました。"
else
    MESSAGE="<users/all> ⚠️  【S3自動取込エラー】\n対象日: ${TARGET_DATE}\nファイルが見つかりませんでした。セッション切れかパスを確認してください。"
fi

curl -s -X POST -H 'Content-Type: application/json; charset=UTF-8' \
    -d "{
        \"text\": \"${MESSAGE}\",
        \"thread\": {\"name\": \"${THREAD_NAME}\"}
    }" \
    "${WEB_URL}" > /dev/null

echo "処理完了（対象日: ${TARGET_DATE}）"

