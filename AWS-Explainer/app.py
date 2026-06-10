from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import os

load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/explain", methods=["POST"])
def explain():
    data = request.get_json()
    definition = data.get("definition", "").strip()
    type_label = data.get("type_label", "AWS")
    model = data.get("model", "gemini")

    if not definition:
        return jsonify({"error": "定義ファイルが空です"}), 400

    prompt = f"""以下の{type_label}定義ファイルを日本語でわかりやすく説明してください。

処理の流れ、各ステートやリソースの役割、全体の目的を構造的に説明してください。

```
{definition}
```"""

    try:
        if model == "gemini":
            result = call_gemini(prompt)
        elif model == "claude":
            result = call_claude(prompt)
        else:
            return jsonify({"error": "不明なモデルです"}), 400

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が .env に設定されていません")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    res = requests.post(url, json=payload, timeout=30)
    res.raise_for_status()

    data = res.json()
    if "error" in data:
        raise ValueError(data["error"]["message"])

    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_claude(prompt: str) -> str:
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
        "model": "claude-sonnet-4-5",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }

    res = requests.post(url, json=payload, headers=headers, timeout=30)
    res.raise_for_status()

    data = res.json()
    if "error" in data:
        raise ValueError(data["error"]["message"])

    return data["content"][0]["text"]


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)