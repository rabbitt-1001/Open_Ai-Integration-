# run.py (updated)
from flask import Flask, request, Response, stream_with_context, json, jsonify
import requests
import sseclient
import re
import os

app = Flask(__name__)
from flask_cors import CORS

# --- Prefer environment variable for API key (safer) ---
OPEN_AI_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")

# handle cors
CORS(app)


@app.route('/')
def index():
    return 'Hello World!'


# ALLOWLIST 
ALLOWED_PHRASES = [
    "special-case: financials q1",
    "show me report x"
]

ALLOWED_KEYWORDS = [
    "report", "financials", "sales", "special-case"
]

ALLOWED_PATTERNS = [
    re.compile(r"\breport\s+\w+\b", re.I),           # e.g. "report sales"
    re.compile(r"special-case[:\s]*\w+", re.I)      # e.g. "special-case: financials"
]


def is_allowed_prompt(prompt: str) -> bool:
    """Return True if the prompt matches allowed phrases/keywords/patterns."""
    if not prompt:
        return False
    p = prompt.strip().lower()

    # Exact phrase match
    for phrase in ALLOWED_PHRASES:
        if p == phrase.lower():
            return True

    # Keyword match (simple - requires at least one keyword)
    for kw in ALLOWED_KEYWORDS:
        if kw.lower() in p:
            return True

    # Regex patterns
    for pattern in ALLOWED_PATTERNS:
        if pattern.search(prompt):
            return True

    return False


@app.route('/api/prompt', methods=['GET', 'POST'])
def prompt():
    if request.method == 'POST':
        prompt = request.json.get('prompt', '')

        # --- CHECK ALLOWLIST BEFORE DOING ANY LLM CALLS (NEW) ---
        if not is_allowed_prompt(prompt):
            # Log denied attempt (optional)
            print(f"[DENIED] Prompt blocked: {prompt}")

            # Return JSON denial so frontend can handle it explicitly
            return jsonify({
                "ok": False,
                "message": "Data can't be shown for this query."
            }), 403
        # --- END CHECK ---

        def generate():
            url = 'https://api.openai.com/v1/chat/completions'
            headers = {
                'content-type': 'application/json; charset=utf-8',
                'Authorization': f"Bearer {OPEN_AI_KEY}"
            }

            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are an AI assistant that answers questions about anything.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 1,
                'max_tokens': 1000,
                'stream': True,
            }

            response = requests.post(url, headers=headers, data=json.dumps(data), stream=True)
            client = sseclient.SSEClient(response)
            for event in client.events():
                if event.data != '[DONE]':
                    try:
                        text = json.loads(event.data)['choices'][0]['delta'].get('content', '')
                        # yield raw token text (what you did before)
                        yield text
                    except Exception:
                        # keep streaming even if a chunk can't be parsed
                        yield ''

        # return streamed text; keep mimetype explicit so client can use fetch().body
        return Response(stream_with_context(generate()), mimetype='text/plain')

    # optional: for GET show a small message
    return jsonify({"ok": True, "message": "Send POST with JSON {prompt: ...}"})


if __name__ == '__main__':
    # debug=True for development only
    app.run(port=4444, debug=True)

