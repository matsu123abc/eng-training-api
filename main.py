import os
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI

app = FastAPI()

# ============================
# Azure OpenAI
# ============================
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# ============================
# Serper API
# ============================
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# ============================
# CORS
# ============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# Request Model
# ============================
class AssistRequest(BaseModel):
    text: str
    mode: str
    theme: str


# ============================
# Conversation Prompts
# ============================
def get_conversation_prompt(theme: str) -> str:
    if theme == "travel":
        return """
You are a friendly travel conversation partner.
Respond naturally in English as if talking in real travel situations.
Do NOT translate Japanese. Reply as a conversation partner.
Keep sentences short and conversational.
"""
    if theme == "restaurant":
        return """
You are a restaurant conversation partner.
Respond like a waiter or someone dining with the user.
Do NOT translate Japanese. Reply naturally in English.
Keep sentences short.
"""
    if theme == "hotel":
        return """
You are a hotel conversation partner.
Respond like a hotel clerk or a guest.
Do NOT translate Japanese. Reply naturally in English.
Keep sentences short.
"""
    if theme == "business":
        return """
You are a business English conversation partner.
Respond politely and clearly.
Do NOT translate Japanese. Reply naturally in English.
Keep sentences short.
"""
    return """
You are a daily English conversation partner.
Do NOT translate Japanese. Reply naturally in English.
Keep sentences short and conversational.
"""


# ============================
# Serper Search
# ============================
def serper_search(query: str):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPER_API_KEY,
        "num": 5
    }

    res = requests.get(url, params=params)
    data = res.json()

    results = []

    def safe(v):
        return v if v else ""

    for item in data.get("organic_results", []):
        results.append({
            "title": safe(item.get("title")),
            "snippet": safe(item.get("snippet")),
            "link": safe(item.get("link"))
        })

    for item in data.get("news_results", []):
        results.append({
            "title": safe(item.get("title")),
            "snippet": safe(item.get("snippet")),
            "link": safe(item.get("link"))
        })

    return results[:5]


# ============================
# UI
# ============================
@app.get("/", response_class=HTMLResponse)
def ui():
    return """
（※ ここは前回の UI コードをそのまま使用できます。省略）
"""


# ============================
# Assist API
# ============================
@app.post("/assist")
async def assist(data: AssistRequest):

    # ============================
    # ① 翻訳モード
    # ============================
    if data.mode == "translate":
        system_prompt = """
Translate the user's Japanese into natural, simple English.
Return only the English translation.
"""
        res = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data.text}
            ],
            temperature=0.3,
            max_tokens=200
        )
        return {"reply": res.choices[0].message.content.strip()}

    # ============================
    # ② 会話モード：検索判定
    # ============================
    if "検索して" in data.text:
        # Serper 検索
        results = serper_search(data.text.replace("検索して", "").strip())

        # AI に自然な英語でまとめさせる
        summary_prompt = """
Summarize the following search results in natural English.
Keep it short and conversational.
"""

        res = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": str(results)}
            ],
            temperature=0.4,
            max_tokens=250
        )

        return {"reply": res.choices[0].message.content.strip()}

    # ============================
    # ③ 会話モード：通常会話
    # ============================
    system_prompt = get_conversation_prompt(data.theme)

    res = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": data.text}
        ],
        temperature=0.4,
        max_tokens=200
    )

    return {"reply": res.choices[0].message.content.strip()}
