import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI

# ============================
# FastAPI アプリ
# ============================
app = FastAPI()

# ============================
# Azure OpenAI クライアント
# ============================
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

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
# リクエストモデル
# ============================
class AssistRequest(BaseModel):
    text: str
    theme: str = "daily"


# ============================
# テーマ別 system prompt
# ============================
def get_system_prompt(theme: str) -> str:
    if theme == "travel":
        return """
You are an English conversation partner for travel situations.
Respond like a friendly person at airports, stations, shops, or sightseeing spots.
When the user speaks in Japanese, translate it into natural, simple English.
Keep sentences short and conversational.
Always return only the English sentence.
"""
    if theme == "restaurant":
        return """
You are an English conversation partner for restaurant situations.
Respond like a waiter or someone dining with the user.
When the user speaks in Japanese, translate it into natural, simple English.
Keep sentences short and conversational.
Always return only the English sentence.
"""
    if theme == "hotel":
        return """
You are an English conversation partner for hotel situations.
Respond like a hotel clerk or a guest.
When the user speaks in Japanese, translate it into natural, simple English.
Keep sentences short and conversational.
Always return only the English sentence.
"""
    if theme == "business":
        return """
You are an English conversation partner for simple business situations.
Respond politely and clearly, using short sentences.
When the user speaks in Japanese, translate it into natural, simple English.
Always return only the English sentence.
"""
    # daily（デフォルト）
    return """
You are an English conversation assistant for daily situations.
When the user speaks in Japanese, translate it into natural, simple English.
If the user speaks in English, reply naturally in English.
Keep sentences short and conversational.
Always return only the English sentence.
"""


# ============================
# UI（HTML + JS）
# ============================
@app.get("/", response_class=HTMLResponse)
def ui():
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI英会話アシスタント</title>
<style>
  body { font-family: sans-serif; padding: 16px; }
  #chat { height: 55vh; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-top: 12px; }
  .me { text-align: right; margin: 8px 0; }
  .ai { text-align: left; margin: 8px 0; }
  button { width: 100%; padding: 14px; font-size: 18px; margin-top: 8px; }
  input { width: 100%; padding: 12px; font-size: 18px; margin-top: 8px; }
  select { width: 100%; padding: 12px; font-size: 18px; margin-top: 8px; }
</style>
</head>
<body>

<h2>AI英会話アシスタント</h2>

<!-- テーマ選択 -->
<select id="theme">
  <option value="daily">日常会話</option>
  <option value="travel">旅行</option>
  <option value="restaurant">レストラン</option>
  <option value="hotel">ホテル</option>
  <option value="business">ビジネス</option>
</select>

<!-- テキスト入力欄 -->
<input id="jpInput" type="text" placeholder="日本語を入力…">

<!-- ボタン -->
<button id="inputBtn">テキスト入力で会話する</button>
<button id="talkBtn">会話する（音声）</button>

<div id="chat"></div>

<script>
let recognizer = null;
let recognizing = false;

// ===== 会話履歴に追加 =====
function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = who;
  div.textContent = text;
  document.getElementById("chat").appendChild(div);
  document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight;
}

// ===== 女性ボイス優先の英語読み上げ =====
function speakEnglish(text) {
  const voices = speechSynthesis.getVoices();

  const femaleVoice = voices.find(v =>
    v.lang.startsWith("en") &&
    (v.name.toLowerCase().includes("female") ||
     v.name.toLowerCase().includes("woman") ||
     v.name.toLowerCase().includes("girl") ||
     v.name.toLowerCase().includes("samantha") ||
     v.name.toLowerCase().includes("google"))
  );

  const uttr = new SpeechSynthesisUtterance(text);
  uttr.lang = "en-US";
  if (femaleVoice) uttr.voice = femaleVoice;

  speechSynthesis.speak(uttr);
}

// ===== AIに送信して英語で応答 =====
async function sendToAI(text) {
  const theme = document.getElementById("theme").value;

  addMessage(text, "me");

  const res = await fetch("/assist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, theme })
  });

  const data = await res.json();
  const english = data.reply;

  addMessage(english, "ai");
  speakEnglish(english);
}

// ===== テキスト入力で会話する =====
document.getElementById("inputBtn").onclick = () => {
  const text = document.getElementById("jpInput").value;
  if (!text) return;
  sendToAI(text);
  document.getElementById("jpInput").value = "";
};

// ===== 音声で会話する =====
document.getElementById("talkBtn").onclick = () => {
  if (!('webkitSpeechRecognition' in window)) {
    alert("このブラウザは音声認識に対応していません。");
    return;
  }

  if (!recognizer) {
    recognizer = new webkitSpeechRecognition();
    recognizer.lang = "ja-JP";
    recognizer.interimResults = false;

    recognizer.onresult = (e) => {
      recognizing = false;
      document.getElementById("talkBtn").textContent = "会話する（音声）";
      const text = e.results[0][0].transcript;
      sendToAI(text);
    };

    recognizer.onend = () => {
      recognizing = false;
      document.getElementById("talkBtn").textContent = "会話する（音声）";
    };
  }

  if (!recognizing) {
    recognizing = true;
    document.getElementById("talkBtn").textContent = "聞き取り中…";
    recognizer.start();
  } else {
    recognizing = false;
    document.getElementById("talkBtn").textContent = "会話する（音声）";
    recognizer.stop();
  }
};
</script>

</body>
</html>
"""


# ============================
# 英会話アシスト API
# ============================
@app.post("/assist")
async def assist(data: AssistRequest):
    system_prompt = get_system_prompt(data.theme)

    res = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": data.text}
        ],
        temperature=0.4,
        max_tokens=200
    )

    reply_text = res.choices[0].message.content.strip()
    return {"reply": reply_text}
