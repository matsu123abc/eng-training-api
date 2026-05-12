import os
import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI
import random

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
  select {
    width: 100%;
    padding: 12px;
    font-size: 18px;
    margin-top: 10px;
  }
</style>
</head>
<body>

<h2>瞬間英作文トレーナー</h2>

<!-- ★ テーマ選択を追加 ★ -->
<select id="theme">
    <option value="daily">日常</option>
    <option value="travel">旅行</option>
    <option value="restaurant">レストラン</option>
    <option value="hotel">ホテル</option>
    <option value="business">ビジネス</option>
</select>

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

// 英語音声再生（1回だけ）
function speakEnglish() {
    const utter = new SpeechSynthesisUtterance(currentEnglish);
    utter.lang = "en-US";
    speechSynthesis.speak(utter);
}

// 答えを表示
function showAnswer() {
    document.getElementById("en").style.display = "block";
}

// 次の問題を取得（テーマ付き）
async function nextQuestion() {
    document.getElementById("en").style.display = "none";
    document.getElementById("en").innerText = "";

    const theme = document.getElementById("theme").value;

    const res = await fetch("/generate_sentence?theme=" + theme, {
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

# ============================
# 英作文 API
# ============================
@app.post("/generate_sentence")
def generate_sentence(theme: str = "daily"):

    import random

    # --- シーン定義 ---
    travel_scenes = [
        "空港でのチェックイン",
        "空港での荷物トラブル",
        "飛行機内での会話",
        "ホテルのチェックイン",
        "ホテルの設備トラブル",
        "観光地での道案内",
        "観光地でのチケット購入",
        "レストランでの注文",
        "買い物での値段交渉",
        "交通機関（電車・バス）での質問",
        "トラブル（迷子・紛失・体調不良）",
        "天気や予定の相談"
    ]

    restaurant_scenes = [
        "おすすめ料理を聞く",
        "アレルギーの相談",
        "席の希望を伝える",
        "料理の味や辛さを聞く",
        "注文の変更",
        "飲み物の注文",
        "会計の依頼",
        "予約の変更",
        "料理が遅いと伝える",
        "料理が間違っていると伝える"
    ]

    hotel_scenes = [
        "チェックイン",
        "チェックアウト",
        "Wi-Fiの問題",
        "シャワーやエアコンのトラブル",
        "清掃の依頼",
        "荷物預かり",
        "周辺案内を聞く",
        "タクシーの手配",
        "予約の変更",
        "部屋の変更依頼"
    ]

    business_scenes = [
        "会議の予定調整",
        "資料の依頼",
        "説明を求める",
        "メールの確認",
        "プレゼンの準備",
        "トラブルの報告",
        "同僚への相談",
        "進捗の共有",
        "提案をする"
    ]

    daily_scenes = [
        "習慣の話",
        "今日の予定",
        "家事の話",
        "趣味の話",
        "健康の話",
        "友達との予定",
        "家族の話",
        "買い物の話",
        "学校や仕事の話",
        "天気の話"
    ]

    scene_map = {
        "travel": travel_scenes,
        "restaurant": restaurant_scenes,
        "hotel": hotel_scenes,
        "business": business_scenes,
        "daily": daily_scenes
    }

    # --- 文のタイプ（創造性を強制） ---
    sentence_styles = [
        "依頼文",
        "質問文",
        "理由を含む文",
        "条件文（if）",
        "比較を含む文",
        "目的を含む文（〜するために）",
        "経験を聞く文（〜したことがありますか）",
        "感情を含む文（困っている・嬉しいなど）",
        "説明文（状況説明）",
        "提案文（〜した方がいい）"
    ]

    # --- 文法構造（構文の多様性を強制） ---
    grammar_patterns = [
        "if を使う",
        "because を使う",
        "when を使う",
        "to不定詞を使う",
        "動名詞を使う",
        "比較級を使う",
        "最上級を使う",
        "助動詞（can, should, must）を使う",
        "現在完了を使う",
        "過去進行形を使う"
    ]

    # --- ランダム選択 ---
    selected_scene = random.choice(scene_map.get(theme, daily_scenes))
    selected_style = random.choice(sentence_styles)
    selected_grammar = random.choice(grammar_patterns)

    # --- AIに渡すプロンプト ---
    prompt = f"""
You are an English teacher.
Generate ONE Japanese sentence and its English translation.

Scene: {selected_scene}
Sentence style: {selected_style}
Grammar pattern: {selected_grammar}

RULES:
- The sentence MUST match the scene, style, and grammar pattern above.
- Never repeat similar sentence patterns.
- Use different verbs, subjects, and structures each time.
- Make the sentence practical, realistic, and creative.
- Keep grammar within junior high school level.

Output format:
Japanese: 〜〜〜
English: 〜〜〜
"""

    # --- Azure OpenAI 呼び出し ---
    res = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[{"role": "system", "content": prompt}],
        temperature=1.0,
        max_tokens=150
    )

    text = res.choices[0].message.content.strip()

    jp = ""
    en = ""

    for line in text.split("\n"):
        if line.startswith("Japanese:"):
            jp = line.replace("Japanese:", "").strip()
        elif line.startswith("English:"):
            en = line.replace("English:", "").strip()

    return {"japanese": jp, "english": en}
