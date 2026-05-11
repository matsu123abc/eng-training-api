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
# Serper Search (3件)
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

    return results[:3]


# ============================
# UI
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
  #chat { height: 40vh; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-top: 12px; }
  .me { text-align: right; margin: 8px 0; }
  .ai { text-align: left; margin: 8px 0; }
  button { width: 100%; padding: 14px; font-size: 18px; margin-top: 8px; }
  input, select { width: 100%; padding: 12px; font-size: 18px; margin-top: 8px; }
</style>
</head>
<body>

<h2>AI英会話アシスタント</h2>

<!-- モード選択 -->
<select id="mode" onchange="toggleThemeUI()">
    <option value="translate">翻訳モード</option>
    <option value="conversation">会話モード</option>
</select>

<!-- テーマ選択（会話モードのときだけ表示） -->
<div id="theme-area" style="margin-top:10px;">
    <select id="theme">
        <option value="daily">日常</option>
        <option value="travel">旅行</option>
        <option value="restaurant">レストラン</option>
        <option value="hotel">ホテル</option>
        <option value="business">ビジネス</option>
    </select>
</div>

<input id="jpInput" type="text" placeholder="日本語を入力…">

<label style="display:flex; align-items:center; margin-top:10px;">
  <input type="checkbox" id="slowMode" style="margin-right:8px;">
  スロー再生
</label>

<button id="inputBtn">テキスト入力で会話する</button>
<button id="talkBtn">会話する（音声）</button>

<button onclick="location.href='/trainer'">瞬間英作文トレーナー</button>

<div id="chat"></div>

<h3>検索結果</h3>
<div id="searchBox" style="
  border: 1px solid #ccc;
  padding: 10px;
  height: 25vh;
  overflow-y: auto;
  margin-top: 10px;
  background: #fafafa;
"></div>

<script>
let recognizer = null;
let recognizing = false;

function toggleThemeUI() {
    const mode = document.getElementById("mode").value;
    const themeArea = document.getElementById("theme-area");

    if (mode === "conversation") {
        themeArea.style.display = "block";
    } else {
        themeArea.style.display = "none";
    }
}

// 初期状態（会話モードならテーマ表示）
toggleThemeUI();

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = who;
  div.innerHTML = text;   // ← これに変更
  const chat = document.getElementById("chat");
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

// 翻訳モードの文例をタップで音声再生
function formatTranslation(text) {
  return text
    .split("\\n")
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .map(line => `
      <div 
        class="translation-line" 
        style="margin-bottom:10px; padding:6px; border-radius:6px; background:#f0f0f0; cursor:pointer;"
        onclick="speakEnglish('${line.replace(/'/g, "\\'")}')"
      >
        ${line}
      </div>
    `)
    .join("");
}

function showSearchResults(items) {
  const box = document.getElementById("searchBox");
  box.innerHTML = "";

  if (!items || items.length === 0) {
    box.innerHTML = "<p>検索結果はありません。</p>";
    return;
  }

  items.forEach(item => {
    const div = document.createElement("div");
    div.style.marginBottom = "12px";

    div.innerHTML = `
      <strong>${item.title}</strong><br>
      <small>${item.snippet}</small><br>
      <a href="${item.link}" target="_blank">リンクを開く</a>
      <hr>
    `;

    box.appendChild(div);
  });
}

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

  // ★ スロー再生チェックボックスの状態を反映
  const slow = document.getElementById("slowMode").checked;
  uttr.rate = slow ? 0.7 : 1.0;

  speechSynthesis.speak(uttr);
}

async function sendToAI(text) {
  const mode = document.getElementById("mode").value;
  const theme = document.getElementById("theme").value;

  addMessage(text, "me");

  // 翻訳（ユーザー発話の英語化）
  const trans = await fetch("/assist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, mode: "translate", theme })
  });
  const transData = await trans.json();

  const userEnglish = formatTranslation(transData.reply);
  addMessage(userEnglish, "me");

  // 会話 or 検索
  const res = await fetch("/assist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, mode, theme })
  });

  const data = await res.json();

  if (data.results) {
    showSearchResults(data.results);
  }

  const english = data.reply;
  addMessage(english, "ai");
  speakEnglish(english);
}

document.getElementById("inputBtn").onclick = () => {
  const text = document.getElementById("jpInput").value;
  if (!text) return;
  sendToAI(text);
  document.getElementById("jpInput").value = "";
};

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
# 瞬間英作文トレーナー UI
# ============================
@app.get("/trainer", response_class=HTMLResponse)
def trainer_ui():
    return """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>瞬間英作文トレーナー</title>

<style>
  body { font-family: sans-serif; padding: 16px; }
  #jp { font-size: 22px; margin-top: 20px; }
  #en { 
    font-size: 22px; 
    margin-top: 20px; 
    display: none; 
    background: #f0f0f0; 
    padding: 10px; 
    border-radius: 6px;
  }
  button { 
    width: 100%; 
    padding: 14px; 
    font-size: 18px; 
    margin-top: 12px; 
  }
</style>
</head>
<body>

<h2>瞬間英作文トレーナー</h2>

<div id="jp">日本語文がここに表示されます</div>

<div id="en" style="
    font-size:22px;
    margin-top:20px;
    display:none;
    background:#f0f0f0;
    padding:10px;
    border-radius:6px;
"></div>

<button onclick="speakEnglish()">🔊 英語を再生</button>
<button onclick="showAnswer()">答えを見る</button>
<button onclick="nextQuestion()">次の問題</button>

<script>
let currentEnglish = "";

// 英語音声再生
function speakEnglish() {
    const utter = new SpeechSynthesisUtterance(currentEnglish);
    utter.lang = "en-US";
    speechSynthesis.speak(utter);
}

// 答えを表示
function showAnswer() {
    document.getElementById("en").style.display = "block";
}

// 次の問題を取得
async function nextQuestion() {
    document.getElementById("en").style.display = "none";
    document.getElementById("en").innerText = "";

    const res = await fetch("/generate_sentence", {
        method: "POST"
    });

    const data = await res.json();

    document.getElementById("jp").innerText = data.japanese;
    document.getElementById("en").innerText = data.english;
    currentEnglish = data.english;
}

// 初回ロード時に問題を取得
nextQuestion();
</script>

</body>
</html>
"""



# ============================
# Assist API
# ============================
@app.post("/assist")
async def assist(data: AssistRequest):

    # 翻訳モード（5文例）
    if data.mode == "translate":
        system_prompt = """
You are an English rewriting assistant.
When the user inputs Japanese, output 5 English versions:

1. Casual English
2. Simple English that Japanese learners can say easily
3. Natural native English
4. Travel English version
5. Polite / business English

Keep each version short.
Do NOT add explanations.
Return only the English sentences.
"""
        res = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data.text}
            ],
            temperature=0.4,
            max_tokens=300
        )
        return {"reply": res.choices[0].message.content.strip(), "results": None}
  
    # 会話モード：検索トリガー（日本語 + 英語 + カタカナ）
    if (
        "検索" in data.text or
        "調べ" in data.text or
        "サーチ" in data.text or
        "さーち" in data.text or
        "look up" in data.text.lower() or
        "ルックアップ" in data.text or
        "るっくあっぷ" in data.text or
        "search" in data.text.lower()
    ):
        query = data.text

        # 不要語を削除
        for k in [
            "検索して", "検索", "調べて", "調べる",
            "サーチ", "さーち",
            "look up", "ルックアップ", "るっくあっぷ",
            "search"
        ]:
            query = query.replace(k, "")

        query = query.strip()

        results = serper_search(query)

        summary_prompt = """
You are an assistant that summarizes web search results.

Rules:
- Ignore URLs and link descriptions completely.
- Do NOT mention website names unless necessary.
- Focus only on the main information (place, rating, features).
- Keep the summary short, natural, and conversational.
- Output 2–3 sentences in simple English.
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

        return {
            "reply": res.choices[0].message.content.strip(),
            "results": results
        }

    # 会話モード：通常会話
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

    return {"reply": res.choices[0].message.content.strip(), "results": None}

@app.post("/generate_sentence")
def generate_sentence():
    
    prompt = """
You are an English teacher.
Generate ONE Japanese sentence and its English translation.
Difficulty: Junior high school level, but slightly challenging.
Use grammar such as:
- conjunctions (because, when, if)
- comparative/superlative
- infinitive and gerund
- simple relative pronouns
- two-part sentences
- natural daily expressions

Output format:
Japanese: 〜〜〜
English: 〜〜〜
"""

    res = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=120
    )

    text = res.choices[0].message.content.strip()

    jp = ""
    en = ""

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Japanese:"):
            jp = line.replace("Japanese:", "").strip()
        elif line.startswith("English:"):
            en = line.replace("English:", "").strip()

    return {
        "japanese": jp,
        "english": en
    }
