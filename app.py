import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import docx
import openpyxl
import requests
from bs4 import BeautifulSoup
from groq import Groq

load_dotenv()

app = FastAPI()

# CORS পারমিশন
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY খুঁজে পাওয়া যায়নি! অনুগ্রহ করে রেন্ডার ড্যাশবোর্ডে সেট করুন।")

groq_client = Groq(api_key=GROQ_API_KEY)

# ব্রাউজারের ফেভিকন (Favicon 404) এরর দূর করার জন্য
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="", status_code=200)

def get_all_context():
    """ডাটাবেজ ছাড়াই সরাসরি সব ফাইল এবং ওয়েবসাইট থেকে টেক্সট তুলে আনার লাইটওয়েট ফাংশন"""
    context_text = ""
    data_dir = "./data"
    
    # ১. ফাইল রিড করা (PDF, DOCX, XLSX, JSON)
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            try:
                if file.endswith('.pdf'):
                    reader = PdfReader(file_path)
                    for page in reader.pages:
                        context_text += page.extract_text() or ""
                elif file.endswith('.docx'):
                    doc = docx.Document(file_path)
                    for para in doc.paragraphs:
                        context_text += para.text + "\n"
                elif file.endswith('.xlsx'):
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    for sheet in wb.sheetnames:
                        for row in wb[sheet].iter_rows(values_only=True):
                            context_text += " ".join([str(cell) for cell in row if cell is not None]) + "\n"
                elif file.endswith('.json'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        context_text += f.read() + "\n"
            except Exception as e:
                print(f"ফাইল {file} পড়তে সমস্যা: {e}")

    # ২. 🌐 ওয়েবসাইট লিঙ্ক রিড করা
    website_urls = [
        "https://www.bitac.gov.bd", 
        "https://www.bitac.gov.bd/site/page/89531ca1-a83d-4c31-9257-8fb6fc9ef444"
    ]
    
    for url in website_urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                context_text += soup.get_text() + "\n"
        except Exception as e:
            print(f"ওয়েবসাইট {url} পড়তে সমস্যা: {e}")
            
    return context_text[:30000] 

# হোম রাউটে সরাসরি চ্যাটবটের ইন্টারফেস (UI) দেখাবে
@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BITAC Tech-Bot</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .chat-container { width: 100%; max-width: 450px; height: 85vh; background: white; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); display: flex; flex-direction: column; overflow: hidden; }
            .chat-header { background: #006643; color: white; padding: 15px; text-align: center; font-weight: bold; font-size: 1.1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .chat-box { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background: #f9f9f9; }
            .message { padding: 10px 14px; border-radius: 8px; max-width: 75%; font-size: 0.95rem; line-height: 1.4; word-wrap: break-word; }
            .user-msg { background: #006643; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
            .bot-msg { background: #e4e6eb; color: #1c1e21; align-self: flex-start; border-bottom-left-radius: 2px; }
            .input-area { display: flex; padding: 12px; gap: 8px; background: white; border-top: 1px solid #eee; }
            .input-area input { flex: 1; padding: 12px; border: 1px solid #ccd0d5; border-radius: 20px; outline: none; font-size: 0.95rem; padding-left: 15px; }
            .input-area input:focus { border-color: #006643; }
            .input-area button { padding: 10px 20px; background: #006643; color: white; border: none; border-radius: 20px; cursor: pointer; font-weight: bold; transition: background 0.2s; }
            .input-area button:hover { background: #004d32; }
        </style>
    </head>
    <body>

    <div class="chat-container">
        <div class="chat-header">BITAC Groq AI Chatbot</div>
        <div class="chat-box" id="chatBox">
            <div class="message bot-msg">আসসালামু আলাইকুম! বিটাক এআই অ্যাসিস্ট্যান্ট-এ আপনাকে স্বাগতম। কীভাবে সাহায্য করতে পারি?</div>
        </div>
        <div class="input-area">
            <input type="text" id="userInput" placeholder="আপনার প্রশ্নটি এখানে লিখুন..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()">পাঠান</button>
        </div>
    </div>

    <script>
        const BACKEND_URL = window.location.origin + "/chat"; 

        async function sendMessage() {
            const inputField = document.getElementById("userInput");
            const chatBox = document.getElementById("chatBox");
            const query = inputField.value.trim();
            
            if (!query) return;

            // ইউজারের মেসেজ স্ক্রিনে দেখানো
            chatBox.innerHTML += `<div class="message user-msg">${query}</div>`;
            inputField.value = "";
            chatBox.scrollTop = chatBox.scrollHeight;

            // লোডিং মেসেজ
            const loadingId = "loading-" + Date.now();
            chatBox.innerHTML += `<div class="message bot-msg" id="${loadingId}"><i>উত্তর তৈরি হচ্ছে...</i></div>`;
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const response = await fetch(`${BACKEND_URL}?user_question=${encodeURIComponent(query)}`, {
                    method: "POST"
                });
                const data = await response.json();
                
                document.getElementById(loadingId).remove();
                chatBox.innerHTML += `<div class="message bot-msg">${data.response || "দুঃখিত, কোনো উত্তর পাওয়া যায়নি।"}</div>`;
            } catch (error) {
                document.getElementById(loadingId).remove();
                chatBox.innerHTML += `<div class="message bot-msg" style="color: red;">সার্ভারে সংযোগ করা যাচ্ছে না!</div>`;
                console.error("Error:", error);
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
    </script>

    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_with_bot(user_question: str):
    knowledge_context = get_all_context()
    
    system_prompt = f"""
    তুমি বিটাক (BITAC - Bangladesh Industrial Technical Assistance Center) এর একজন অফিসিয়াল এআই অ্যাসিস্ট্যান্ট। 
    নিচে দেওয়া 'কনটেক্সট তথ্য' থেকে ইউজারের প্রশ্নের সঠিক এবং পেশাদার উত্তর দাও। 
    যদি কনটেক্সটে উত্তর না থাকে, তবে নিজের মন থেকে ভুল বা বানিয়ে কোনো উত্তর দেবে না।
    সবসময় বাংলায় উত্তর দেবে।
    
    কনটেক্সট তথ্য:
    {knowledge_context}
    """
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ],
            model="llama3-8b-8192", 
            temperature=0.3 
        )
        return {"response": chat_completion.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # রেন্ডার সার্ভারের জন্য ডিফল্ট পোর্ট সরাসরি ১০০০০ (10000) সেট করা হলো
    port = int(os.getenv("PORT", 10000)) 
    uvicorn.run(app, host="0.0.0.0", port=port)
