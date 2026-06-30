#!/bin/bash

# ==========================================
#
# Event Bridgeの定義を一括でDLする 
# 事前に mkdir -p eventbridge_rulesが必要
# ==========================================


# ルール名を一覧取得してループ処理
aws events list-rules --query 'Rules[*].Name' --output text | tr '\t' '\n' | while read rule_name; do
    if [ -n "$rule_name" ]; then
        echo "Downloading: $rule_name.yaml"

        # 1. ルールの詳細をYAML形式で保存
        aws events describe-rule --name "$rule_name" --output yaml > "eventbridge_rules/${rule_name}.yaml"

        # 2. そのルールの「ターゲット（実行先）」情報もYAML形式で追記
        echo "Targets:" >> "eventbridge_rules/${rule_name}.yaml"
        aws events list-targets-by-rule --rule "$rule_name" --output yaml >> "eventbridge_rules/${rule_name}.yaml"
    fi
done

echo "完了しました！ eventbridge_rules ディレクトリを確認してください。"