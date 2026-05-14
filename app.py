import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from dotenv import load_dotenv
import google.generativeai as genai
import PyPDF2
import pandas as pd
from docx import Document

# ১. এনভায়রনমেন্ট এবং এপিআই সেটআপ
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(
    title="BITAC AI Assistant API",
    description="বিটিক (BITAC) এর নলেজ বেস ভিত্তিক এআই অ্যাসিস্ট্যান্ট",
    version="1.0.0"
)

# --- ২. অটোমেটিক ফাইল রিডার ফাংশন (Render সার্ভারের জন্য ১০০% অপ্টিমাইজড) ---
def load_all_data(folder="data"):
    text_data = ""
    # Render-এর রুট ডিরেক্টরি নিশ্চিত করার জন্য absolute path ব্যবহার করা হলো
    base_dir = os.path.dirname(os.path.abspath(__file__))
    actual_folder = os.path.join(base_dir, folder)
    
    print(f"--- Looking for data folder at: {actual_folder} ---")
    
    if not os.path.exists(actual_folder):
        print(f"Warning: Folder '{actual_folder}' not found. Creating a new one.")
        os.makedirs(actual_folder)
        return text_data
        
    files = os.listdir(actual_folder)
    print(f"--- Files found in data folder: {files} ---")
        
    for file in files:
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
            print(f"Successfully loaded file: {file}")
        except Exception as e:
            print(f"Error reading {file}: {e}")
            continue
            
    return text_data

# বিটিকের নলেজ বেস একবার লোড করে রাখা
KNOWLEDGE_BASE = load_all_data()
print(f"--- TOTAL KNOWLEDGE BASE LENGTH: {len(KNOWLEDGE_BASE)} characters ---")

# --- ৩. এআই প্রসেসিং ফাংশন (API Version v1 ফিক্সড করা হয়েছে) ---
def get_ai_response(user_query):
    try:
        # আপনার নির্দেশনানুযায়ী এখানে গুগলের স্টেবিল v1 এপিআই সংস্করণ ব্যবহার করতে বাধ্য করা হয়েছে
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            api_version='v1'
        )
        
        prompt = f"""
        তুমি বিটিক (BITAC) এর একজন অভিজ্ঞ টেকনিক্যাল অ্যাসিস্ট্যান্ট। 
        নিচের তথ্যগুলো ব্যবহার করে ইউজারের প্রশ্নের সঠিক এবং পেশাদার উত্তর দাও। 
        তথ্য না থাকলে বিনয়ের সাথে বলো যে তোমার কাছে এই মুহূর্তে তথ্যটি নেই।
        
        তথ্যসমূহ:
        {KNOWLEDGE_BASE}
        
        ইউজারদের প্রশ্ন: {user_query}
        """
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text
        else:
            return "দুঃখিত, কোনো উত্তর জেনারেট করা যায়নি। এপিআই কী অথবা প্রম্পট চেক করুন।"
            
    except Exception as gemini_error:
        print(f"Gemini API Error: {gemini_error}")
        return f"এআই রেসপন্স তৈরিতে সমস্যা হয়েছে: {str(gemini_error)}"

# --- ৪. রুট পাথ: সরাসরি চ্যাটবট ইন্টারফেস (HTML UI) দেখাবে ---
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
            #chat-window { 
                width: 100%; 
                max-width: 500px; 
                height: 85vh; 
                background-color: white; 
                border-radius: 16px; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
                display: flex; 
                flex-direction: column; 
                overflow: hidden;
            }
            header { background-color: #006643; color: white; padding: 15px; text-align: center; font-size: 1.1rem; font-weight: 600; }
            #chat-container { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background-color: #fdfdfd; }
            .message { max-width: 80%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; font-size: 0.95rem; word-wrap: break-word; white-space: pre-line; }
            .user-message { background-color: #006643; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
            .bot-message { background-color: #f1f0f0; color: #333; align-self: flex-start; border-bottom-left-radius: 2px; }
            .loading { font-style: italic; color: #888; }
            #input-container { background: white; padding: 12px; display: flex; gap: 8px; border-top: 1px solid #eee; }
            #user-input { flex: 1; padding: 10px 15px; border: 1px solid #ddd; border-radius: 20px; outline: none; font-size: 0.95rem; }
            #user-input:focus { border-color: #006643; }
            #send-btn { background-color: #006643; color: white; border: none; padding: 0 20px; border-radius: 20px; cursor: pointer; font-size: 0.95rem; font-weight: 600; }
            #send-btn:hover { background-color: #004d32; }
            @media (max-width: 520px) {
                body { padding: 0; }
                #chat-window { max-width: 100%; height: 100vh; border-radius: 0; }
            }
        </style>
    </head>
    <body>
        <div id="chat-window">
            <header>BITAC AI Assistant (বিটিক এআই অ্যাসিস্ট্যান্ট)</header>
            <div id="chat-container">
                <div class="message bot-message">আসসালামু আলাইকুম! আমি বিটিক (BITAC) টেকনিক্যাল অ্যাসিস্ট্যান্ট। আপনাকে কীভাবে সাহায্য করতে পারি?</div>
            </div>
            <div id="input-container">
                <input type="text" id="user-input" placeholder="আপনার প্রশ্নটি এখানে লিখুন..." autocomplete="off">
                <button id="send-btn" onclick="sendMessage()">পাঠান</button>
            </div>
        </div>

        <script>
            const userInput = document.getElementById('user-input');
            const chatContainer = document.getElementById('chat-container');

            userInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendMessage();
            });

            async function sendMessage() {
                const messageText = userInput.value.trim();
                if (!messageText) return;

                appendMessage(messageText, 'user-message');
                userInput.value = '';

                const loadingDiv = appendMessage('টাইপ করছে...', 'bot-message loading');
                chatContainer.scrollTop = chatContainer.scrollHeight;

                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ msg: messageText })
                    });
                    const data = await response.json();
                    loadingDiv.remove();
                    appendMessage(data.reply, 'bot-message');
                } catch (error) {
                    loadingDiv.remove();
                    appendMessage('দুঃখিত, সার্ভারের সাথে যোগাযোগ করা যাচ্ছে না।', 'bot-message');
                }
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }

            function appendMessage(text, className) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${className}`;
                messageDiv.innerText = text;
                chatContainer.appendChild(messageDiv);
                return messageDiv;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# --- ৫. ফেভিকন এরর হ্যান্ডলার ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return JSONResponse(content={"status": "no favicon"}, status_code=200)

# --- ৬. ইউনিভার্সাল চ্যাট এন্ডপয়েন্ট ---
@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        message = data.get("msg") 
        if not message:
            return {"reply": "দুঃখিত, আমি কোনো প্রশ্ন খুঁজে পাইনি।"}
            
        reply = get_ai_response(message)
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"সার্ভারে একটি সমস্যা হয়েছে: {str(e)}"}

# --- ৭. সার্ভার রান করা ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
