import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from dotenv import load_dotenv
from groq import Groq  # Groq লাইব্রেরি
import PyPDF2
import pandas as pd
from docx import Document

# ১. এনভায়রনমেন্ট সেটআপ
load_dotenv()
# Render-এর Environment Variables-এ GROQ_API_KEY অবশ্যই যুক্ত করবেন
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI(title="BITAC AI Assistant (Groq Version)")

# --- ২. অটোমেটিক ফাইল রিডার ফাংশন ---
def load_all_data(folder="data"):
    text_data = ""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    actual_folder = os.path.join(base_dir, folder)
    
    if not os.path.exists(actual_folder):
        os.makedirs(actual_folder)
        return text_data
        
    for file in os.listdir(actual_folder):
        path = os.path.join(actual_folder, file)
        try:
            if file.endswith(".txt"):
                with open(path, "r", encoding="utf-8") as f: 
                    text_data += f"\n--- Source: {file} ---\n" + f.read()
            elif file.endswith(".pdf"):
                reader = PyPDF2.PdfReader(path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                text_data += f"\n--- Source: {file} ---\n" + text
            elif file.endswith(".xlsx") or file.endswith(".xls"):
                df = pd.read_excel(path)
                text_data += f"\n--- Source: {file} ---\n" + df.to_string()
            elif file.endswith(".docx"):
                doc = Document(path)
                text = "\n".join([p.text for p in doc.paragraphs])
                text_data += f"\n--- Source: {file} ---\n" + text
        except Exception as e:
            print(f"Error reading {file}: {e}")
            continue
    return text_data

KNOWLEDGE_BASE = load_all_data()
print(f"--- TOTAL KNOWLEDGE BASE LENGTH: {len(KNOWLEDGE_BASE)} characters ---")

# --- ৩. এআই প্রসেসিং ফাংশন (Groq মেথড) ---
# --- ৩. এআই প্রসেসিং ফাংশন (মডেল আপডেট) ---
def get_ai_response(user_query):
    try:
        # llama-3.1-70b-versatile এর বদলে llama-3.3-70b-versatile ব্যবহার করা হয়েছে
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[
                {
                    "role": "system",
                    "content": f"তুমি বিটিক (BITAC) এর একজন অভিজ্ঞ টেকনিক্যাল অ্যাসিস্ট্যান্ট। নিচের তথ্যগুলো ব্যবহার করে উত্তর দাও:\n\n{KNOWLEDGE_BASE}"
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ],
            temperature=0.7,
            max_tokens=1024
        )
        return completion.choices[0].message.content
            
    except Exception as e:
        # যদি উপরেরটি কাজ না করে, তবে আরও দ্রুততর মডেলটি ট্রাই করবে
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": user_query}]
            )
            return completion.choices[0].message.content
        except:
            print(f"Groq Final Error: {str(e)}")
            return "দুঃখিত, এআই সার্ভারে মডেলে সমস্যা হচ্ছে। অনুগ্রহ করে একটু পর চেষ্টা করুন।"
# --- ৪. রুট পাথ: চ্যাটবট ইন্টারফেস (UI) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    html_content = """
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BITAC AI Assistant</title>
        <link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;600&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Hind Siliguri', sans-serif; }
            body { background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; }
            #chat-window { width: 100%; max-width: 500px; height: 85vh; background-color: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
            header { background-color: #006643; color: white; padding: 15px; text-align: center; font-size: 1.1rem; font-weight: 600; }
            #chat-container { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background-color: #fdfdfd; }
            .message { max-width: 80%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; font-size: 0.95rem; word-wrap: break-word; white-space: pre-line; }
            .user-message { background-color: #006643; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
            .bot-message { background-color: #f1f0f0; color: #333; align-self: flex-start; border-bottom-left-radius: 2px; }
            #input-container { background: white; padding: 12px; display: flex; gap: 8px; border-top: 1px solid #eee; }
            #user-input { flex: 1; padding: 10px 15px; border: 1px solid #ddd; border-radius: 20px; outline: none; }
            #send-btn { background-color: #006643; color: white; border: none; padding: 0 20px; border-radius: 20px; cursor: pointer; font-weight: 600; }
        </style>
    </head>
    <body>
        <div id="chat-window">
            <header>BITAC AI Assistant (Groq Powered)</header>
            <div id="chat-container">
                <div class="message bot-message">আসসালামু আলাইকুম! আমি বিটিক (BITAC) টেকনিক্যাল অ্যাসিস্ট্যান্ট। কীভাবে সাহায্য করতে পারি?</div>
            </div>
            <div id="input-container">
                <input type="text" id="user-input" placeholder="আপনার প্রশ্নটি এখানে লিখুন..." autocomplete="off">
                <button id="send-btn" onclick="sendMessage()">পাঠান</button>
            </div>
        </div>
        <script>
            async function sendMessage() {
                const input = document.getElementById('user-input');
                const message = input.value.trim();
                if (!message) return;
                
                appendMsg(message, 'user-message');
                input.value = '';
                const loadingMsg = appendMsg('টাইপ করছে...', 'bot-message');

                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ msg: message })
                    });
                    const data = await response.json();
                    loadingMsg.remove();
                    appendMsg(data.reply, 'bot-message');
                } catch {
                    loadingMsg.remove();
                    appendMsg('সার্ভারে সমস্যা হয়েছে।', 'bot-message');
                }
            }
            function appendMsg(text, className) {
                const div = document.createElement('div');
                div.className = `message ${className}`;
                div.innerText = text;
                const container = document.getElementById('chat-container');
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
                return div;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- ৫. চ্যাট এন্ডপয়েন্ট ---
@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        reply = get_ai_response(data.get("msg"))
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"Error: {str(e)}"}

# --- ৬. সার্ভার রান করা ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
