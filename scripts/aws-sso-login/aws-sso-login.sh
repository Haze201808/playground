#!/bin/bash

SCRIPT_DIR="\((cd "\)(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/config.env" ]; then
    source "${SCRIPT_DIR}/config.env"
else
    echo "エラー: config.env が見つかりません。config.env.example を参考に作成してください。"
    exit 1
fi

export BROWSER="${CHROME_PATH}"
export AWS_CA_BUNDLE="${AWS_CA_BUNDLE_PATH}"
export REQUESTS_CA_BUNDLE="${AWS_CA_BUNDLE_PATH}"

SUCCESS_LIST=()
FAILED_LIST=()

send_gchat_notification() {
    local message="$1"
    curl -s -X POST -H 'Content-Type: application/json; charset=UTF-8' \
        -d "{\"text\": \"\({message}\", \"thread\": {\"name\": \"\){THREAD_NAME}\"}}" \
        "${WEBHOOK_URL}" > /dev/null
}

for profile in "${PROFILES[@]}"; do
    echo "Logging in to: ${profile}..."
    
    aws sso login --profile "${profile}" &
    AWS_PID=$!

    sleep 6

    powershell.exe -Command "
        \$wshell = New-Object -ComObject wscript.shell;
        if (\$wshell.AppActivate('Google Chrome')) {
            # 1枚目: 確認をして続行
            Start-Sleep -m 1000;
            \$wshell.SendKeys('{TAB}');
            Start-Sleep -m 300;
            \$wshell.SendKeys('{ENTER}');

            # 2枚目: 許可
            Start-Sleep -m 2000;
            \$wshell.SendKeys('{TAB}');
            Start-Sleep -m 200;
            \$wshell.SendKeys('{TAB}');
            Start-Sleep -m 300;
            \$wshell.SendKeys('{ENTER}');

            # 作業の邪魔にならないようChromeを最小化 (Alt + Space -> n)
            Start-Sleep -m 500;
            \$wshell.SendKeys('% ');
            Start-Sleep -m 100;
            \$wshell.SendKeys('n');
        }
    "

    # ログイン結果の判定
    wait $AWS_PID
    if [ $? -eq 0 ]; then
        SUCCESS_LIST+=("${profile}")
    else
        FAILED_LIST+=("${profile}")
    fi
done

MSG="🤖 *AWS SSO 自動ログイン結果通知*\\n"

if [ ${#SUCCESS_LIST[@]} -gt 0 ]; then
    MSG="${MSG}\\n✅ *成功:*\\n"
    for p in "${SUCCESS_LIST[@]}"; do
        MSG="\({MSG}•\){p}\\n"
    done
fi

if [ ${#FAILED_LIST[@]} -gt 0 ]; then
    MSG="${MSG}\\n❌ *失敗:*\\n"
    for p in "${FAILED_LIST[@]}"; do
        MSG="\({MSG}•\){p}\\n"
    done
fi

send_gchat_notification "${MSG}"