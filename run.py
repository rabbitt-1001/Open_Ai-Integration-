from flask import Flask, request, Response, stream_with_context, json, jsonify
import requests
import sseclient
import re
import os

app = Flask(__name__)
from flask_cors import CORS

# Prefer environment variable for API key (safer) ---
OPEN_AI_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")

#Allow configuring model via env; default to a modern reasoning model.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# handle cors
CORS(app)


@app.route('/')
def index():
    return 'Hello World!'


# MINING-ONLY DOMAIN FILTER
# We consider "mining" in the industrial sense: methods, equipment, geology, safety,
# mineral processing, economics, regulations, automation, etc.

MINING_PHRASES = [
    "open pit", "open-pit", "underground mining", "block caving", "longwall",
    "room and pillar", "drill and blast", "drilling and blasting", "ventilation",
    "mine ventilation", "ground control", "geotechnical", "rock mechanics",
    "haul truck", "dump truck", "shovel", "excavator", "loader",
    "conveyor", "crusher", "jaw crusher", "cone crusher",
    "sag mill", "ball mill", "comminution",
    "flotation", "froth flotation", "leaching", "heap leach",
    "cyanidation", "bioleaching", "hydrometallurgy", "pyrometallurgy",
    "tailings", "tailings storage facility", "tsf",
    "thickener", "clarifier", "dewatering", "paste backfill",
    "ore", "orebody", "ore body", "ore grade", "cut-off grade",
    "strip ratio", "mine plan", "mine planning", "short-term plan", "long-term plan",
    "grade control", "blast design", "powder factor",
    "survey", "pit design", "slope stability", "pit slope",
    "mine closure", "reclamation", "environmental impact", "rehabilitation",
    "mineral processing", "metallurgy", "beneficiation",
    "exploration drilling", "core logging", "assay", "resource estimation",
    "reserve estimation", "jorc", "ni 43-101",
    "msha", "oHS", "safety", "dust control", "ventilation on demand",
    "autonomous haulage", "ahS", "dispatch", "fleet management", "predictive maintenance",
    "mine water", "acid mine drainage", "amd", "smelting", "refining",
    "underground ventilation", "secondary ventilation", "primary ventilation",
    "groundwater", "depressurization", "dewatering boreholes",
    "geology", "structural geology", "lithology", "alteration",
    "geometallurgy", "composite sampling", "variography", "kriging"
]

# Broader keyword list to quickly gate mining topics.
MINING_KEYWORDS = [
    "mining", "mine", "miner", "mineral", "ore", "pit", "shaft", "drift", "stope",
    "blast", "drill", "ventilation", "haul", "flotation", "tailings", "leach",
    "crusher", "mill", "metallurgy", "beneficiation", "geology", "geotech",
    "slope", "reclamation", "rehabilitation", "msha", "jorc", "ni 43-101",
    "tsf", "grade", "cut-off", "strip ratio", "dispatch", "autonomous haulage"
]

# Regex patterns to catch common mining terminology and structures.
MINING_PATTERNS = [
    re.compile(r"\b(open[\s-]?pit|underground|block\s+caving|longwall|room\s+and\s+pillar)\b", re.I),
    re.compile(r"\b(drill(ing)?\s+(and\s+)?blast(ing)?|blast\s+design|powder\s+factor)\b", re.I),
    re.compile(r"\b(haul\s+truck|shovel|excavator|conveyor|crusher|sag\s+mill|ball\s+mill)\b", re.I),
    re.compile(r"\b(flotation|leach(ing)?|cyanidation|hydrometallurgy|pyrometallurgy)\b", re.I),
    re.compile(r"\b(tailings(\s+storage\s+facility)?|tsf|thickener|dewatering|backfill)\b", re.I),
    re.compile(r"\b(cut-?off\s+grade|strip\s+ratio|grade\s+control|pit\s+design|slope\s+stability)\b", re.I),
    re.compile(r"\b(resource|reserve)\s+estimation\b", re.I),
    re.compile(r"\b(ventilation(\s+on\s+demand)?|ground\s+control|rock\s+mechanics)\b", re.I),
    re.compile(r"\b(jorc|ni\s*43-101|msha)\b", re.I),
    re.compile(r"\b(autonomous\s+haulage|predictive\s+maintenance|fleet\s+management)\b", re.I),
]

def is_mining_prompt(prompt: str) -> bool:
    """
    Heuristic Mining-domain filter:
    - Returns True if prompt looks mining-related by phrase/keyword/pattern.
    - Conservative: requires at least one indicator.
    """
    if not prompt:
        return False
    p = prompt.strip().lower()

    # Phrases (contains)
    for phrase in MINING_PHRASES:
        if phrase.lower() in p:
            return True

    # Keywords (contains at least one)
    for kw in MINING_KEYWORDS:
        if kw.lower() in p:
            return True

    # Regex patterns
    for pattern in MINING_PATTERNS:
        if pattern.search(prompt):
            return True

    return False
@app.route('/api/prompt', methods=['GET', 'POST'])
def prompt():
    if request.method == 'POST':
        user_prompt = request.json.get('prompt', '')

        # Check Mining scope BEFORE any LLM calls
        if not is_mining_prompt(user_prompt):
            print(f"[DENIED - OOS] Prompt blocked: {user_prompt}")
            return jsonify({
                "ok": False,
                "message": "Out of scope"
            }), 403

        def generate():
            url = 'https://api.openai.com/v1/chat/completions'
            headers = {
                'content-type': 'application/json; charset=utf-8',
                'Authorization': f"Bearer {OPEN_AI_KEY}"
            }

            # System prompt: Mining-only, Markdown, Out-of-scope on unrelated
            system_prompt = (
                "You are a Mining Domain AI Assistant.\n"
                "STRICT RULES:\n"
                "1) Only answer questions related to mining (methods, equipment, geology, mineral processing,\n"
                "   safety, environmental management, mine planning, economics, regulations/standards,\n"
                "   digital/automation in mining).\n"
                "2) If the user query is unrelated to mining, respond with exactly: Out of scope\n"
                "   (no extra text). Do not attempt to answer or infer unrelated content.\n"
                "3) Always respond in Markdown with clear technical detail (headings, bullet lists, formulas/equations\n"
                "   where helpful, short code/CLI snippets only if directly relevant to mining workflows).\n"
                "4) Be concise, accurate, and avoid hallucinations. If data is uncertain, state assumptions.\n"
            )

            data = {
                'model': OPENAI_MODEL,  
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                'temperature': 0.2,     
                'max_tokens': 1200,
                'stream': True,
            }

            response = requests.post(url, headers=headers, data=json.dumps(data), stream=True)
            client = sseclient.SSEClient(response)
            for event in client.events():
                if event.data != '[DONE]':
                    try:
                        payload = json.loads(event.data)
                        text = payload['choices'][0]['delta'].get('content', '')
                        # Stream raw token text
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

