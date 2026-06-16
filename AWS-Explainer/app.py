from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import os
import json

load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)


@app.route("/")
def index():
    return app.send_static_file("index.html")


def detect_file_type(filename: str, content: str) -> str:
    """ファイルの種類を自動判別する"""
    ext = os.path.splitext(filename)[1].lower()

    # Lambdaコードファイル（拡張子で判別）
    if ext in [".py", ".js", ".ts"]:
        return "Lambda関数"

    # JSON/YAMLの場合は中身で判別
    if ext in [".json", ".yaml", ".yml"]:
        try:
            # YAMLはJSONとして読めないのでキーワードで判別
            if "StartAt" in content and "States" in content:
                return "Step Functions"
            if "AWSTemplateFormatVersion" in content or (
                "Resources" in content and "Type" in content
            ):
                return "CloudFormation"
        except Exception:
            pass

    # テキスト内容でも判別を試みる
    if "def lambda_handler" in content or "exports.handler" in content:
        return "Lambda関数"
    if "StartAt" in content and "States" in content:
        return "Step Functions"
    if "AWSTemplateFormatVersion" in content or "Resources" in content:
        return "CloudFormation"

    return "AWSリソース"


def build_multi_prompt(files: list) -> str:
    """複数ファイルを組み合わせたプロンプトを生成する"""
    sections = []
    for f in files:
        label = f["type"]
        name = f.get("path", f["filename"])  # パスがあればパスを使う
        content = f["content"]
        sections.append(f"## {label}（{name}）\n```\n{content}\n```")

    files_text = "\n\n".join(sections)

    return f"""以下の複数のAWSリソース定義ファイルを読み込み、**システム全体として何をするシステムなのか**を日本語でわかりやすく説明してください。

# 説明の方針
- 各ファイルを個別に解説するのではなく、ファイル同士がどのように連携しているかを中心に説明してください
- Lambda関数は「このシステムの中でどういう処理を担っているか」という観点で説明してください
- 以下の構成で説明してください：

1. **システム全体の目的**（このシステムは何をするためのものか）
2. **処理の流れ**（どのリソースがどの順番で動くか）
3. **各リソースの役割**（システム全体の中での位置づけ）
4. **連携のポイント**（リソース間でどのようにデータや制御が渡されるか）

# 読み込んだファイル

{files_text}"""


@app.route("/explain", methods=["POST"])
def explain():
    data = request.get_json()
    model = data.get("model", "gemini")

    # 複数ファイルモード
    files = data.get("files", [])
    if files:
        prompt = build_multi_prompt(files)
    else:
        # 単一ファイルモード（後方互換）
        definition = data.get("definition", "").strip()
        type_label = data.get("type_label", "AWS")
        if not definition:
            return jsonify({"error": "定義ファイルが空です"}), 400
        prompt = f"""以下の{type_label}定義ファイルを日本語でわかりやすく説明してください。

処理の流れ、各ステートやリソースの役割、全体の目的を構造的に説明してください。

```
{definition}
```"""

    try:
        if model == "gemini":
            result = call_gemini([{"role": "user", "content": prompt}])
        elif model == "claude":
            result = call_claude([{"role": "user", "content": prompt}])
        else:
            return jsonify({"error": "不明なモデルです"}), 400

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    messages = data.get("messages", [])
    model = data.get("model", "gemini")

    if not messages:
        return jsonify({"error": "メッセージが空です"}), 400

    try:
        if model == "gemini":
            result = call_gemini(messages)
        elif model == "claude":
            result = call_claude(messages)
        else:
            return jsonify({"error": "不明なモデルです"}), 400

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def call_gemini(messages: list) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が .env に設定されていません")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"

    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    res = requests.post(url, json={"contents": contents}, timeout=60)
    res.raise_for_status()

    data = res.json()
    if "error" in data:
        raise ValueError(data["error"]["message"])

    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_claude(messages: list) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が .env に設定されていません")

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "messages": messages,
    }

    res = requests.post(url, json=payload, headers=headers, timeout=60)
    res.raise_for_status()

    data = res.json()
    if "error" in data:
        raise ValueError(data["error"]["message"])

    return data["content"][0]["text"]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

