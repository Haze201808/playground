#!/bin/bash

# ==========================================
#
# Step functionの定義を一括でDLする 
#
# ==========================================

OUTPUT_DIR="./sfn_definitions"
mkdir -p "$OUTPUT_DIR"

echo "全Step Functionsの定義を ${OUTPUT_DIR} にダウンロードします..."

for arn in $(aws stepfunctions list-state-machines --query "stateMachines[].stateMachineArn" --output text); do
    # ARNからステートマシン名（一番末尾の部分）を抽出してファイル名にする
    sfn_name=$(echo "$arn" | awk -F: '{print $NF}')

    echo "-> ダウンロード中: ${sfn_name}"

    # 定義をJSONファイルとして保存
    aws stepfunctions describe-state-machine --state-machine-arn "$arn" --query "definition" --output text > "${OUTPUT_DIR}/${sfn_name}.json" 2>/dev/null
done

echo "全てのダウンロードが完了しました！フォルダ [ ${OUTPUT_DIR} ] を確認してください。"