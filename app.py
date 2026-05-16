import os
import json
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import docx
import openpyxl
import requests
from groq import Groq
import urllib3

# SSL ওয়ার্নিং বন্ধ করার জন্য
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# ডিফল্ট ব্যাকআপ ডাটা (যদি ফাইল বা লিঙ্ক কোনোটিই কাজ না করে)
BITAC_FALLBACK_INFO = """
বাংলাদেশ ইন্ডাস্ট্রিয়াল টেকনিক্যাল অ্যাসিস্ট্যান্স সেন্টার (BITAC - বিটাক) শিল্প মন্ত্রণালয়ের অধীন একটি সরকারি স্বায়ত্তশাসিত কারিগরি প্রতিষ্ঠান।
প্রধান কাজ: শিল্প ক্ষেত্রে উৎপাদনশীলতা বৃদ্ধি, কারিগরি সহায়তা প্রদান, এবং খুচরা যন্ত্রপাতি (Spare Parts) তৈরি।
প্রধান কার্যালয় ঢাকার তেজগাঁওয়ে অবস্থিত। আঞ্চলিক কেন্দ্রসমূহ: চট্টগ্রাম, খুলনা, বগুড়া, চাঁদপুর ও রাঙ্গামাটি।
"""

GLOBAL_KNOWLEDGE_CONTEXT = BITAC_FALLBACK_INFO

@app.head("/")
async def head_home():
    return HTMLResponse(content="", status_code=200)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="", status_code=200)

def load_all_combined_context():
    """Jina AI লিঙ্ক এবং লোকাল data ফোল্ডারের ফাইল থেকে ডাটা একসাথে মেমোরিতে লোড করার মাস্টার ফাংশন"""
    global GLOBAL_KNOWLEDGE_CONTEXT
    combined_text = ""
    
    # === অংশ ১: লোকাল ফাইল রিড করা (PDF, DOCX, XLSX, TXT) ===
    data_dir = "./data"
    if os.path.exists(data_dir):
        print("📁 'data' ফোল্ডার পাওয়া গেছে। ফাইল স্ক্যান করা হচ্ছে...")
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            try:
                if file.lower().endswith('.pdf'):
                    print(f"📖 PDF রিড হচ্ছে: {file}")
                    reader = PdfReader(file_path)
                    for page in reader.pages:
                        combined_text += page.extract_text() or ""
                elif file.lower().endswith('.docx'):
                    print(f"📖 DOCX রিড হচ্ছে: {file}")
                    doc = docx.Document(file_path)
                    for para in doc.paragraphs:
                        if para.text.strip():
                            combined_text += para.text + "\n"
                elif file.lower().endswith('.xlsx'):
                    print(f"📖 XLSX রিড হচ্ছে: {file}")
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    for sheet in wb.sheetnames:
                        for row in wb[sheet].iter_rows(values_only=True):
                            row_text = " ".join([str(cell) for cell in row if cell is not None])
                            if row_text.strip():
                                combined_text += row_text + "\n"
                elif file.lower().endswith(('.txt', '.json')):
                    print(f"📖 টেক্সট ফাইল রিড হচ্ছে: {file}")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        combined_text += f.read() + "\n"
            except Exception as e:
                print(f"⚠️ ফাইল {file} পড়তে সমস্যা: {e}")
    else:
        print("ℹ️ 'data' ফোল্ডার পাওয়া যায়নি। শুধু লিঙ্ক স্ক্র্যাপার কার্যকর থাকবে।")
                
    # === অংশ ২: Jina AI দিয়ে লাইভ ওয়েবসাইট লিঙ্ক স্ক্র্যাপ করা ===
    target_urls = [
        "https://www.bitac.gov.bd", 
        "https://www.bitac.gov.bd/site/page/89531ca1-a83d-4c31-9257-8fb6fc9ef444"
    ]
    print("🌐 Jina AI এর মাধ্যমে লাইভ ওয়েবসাইট স্ক্র্যাপ করা হচ্ছে...")
    for url in target_urls:
        try:
            jina_proxy_url = f"https://r.jina.ai/{url}"
            response = requests.get(jina_proxy_url, timeout=12)
            if response.status_code == 200 and len(response.text.strip()) > 100:
                combined_text += "\n" + response.text.strip() + "\n"
                print(f"✅ লিঙ্ক থেকে ডাটা এসেছে: {url}")
        except Exception as e:
            print(f"⚠️ লিঙ্ক স্ক্র্যাপ করতে সমস্যা: {url} -> {e}")

    # === অংশ ৩: মেমোরি লিমিট ও ফলব্যাক হ্যান্ডেল করা ===
    final_text = combined_text.strip()
    if len(final_text) > 100:
        # রেন্ডার সার্ভারের র‍্যাম সেইফ রাখতে সর্বোচ্চ ১৮,০০০ ক্যারেক্টার ট্রিম করা হলো
        GLOBAL_KNOWLEDGE_CONTEXT = final_text[:18000]
        print(f"🎉 সাফল্য! ফাইল ও লিঙ্ক মিলিয়ে মোট {len(GLOBAL_KNOWLEDGE_CONTEXT)} ক্যারেক্টার ডাটা সেট হয়েছে।")
    else:
        GLOBAL_KNOWLEDGE_CONTEXT = BITAC_FALLBACK_INFO
        print("⚠️ কোনো ডাটা পাওয়া যায়নি, ফলব্যাক ডাটা সক্রিয় আছে।")

# FastAPI সার্ভার চালু হওয়ার সময় এই ইভেন্টটি ব্যাকগ্রাউন্ডে একবারই রান করবে
@app.on_event("startup")
async def startup_event():
    try:
        load_all_combined_context()
    except Exception as e:
        print(f"❌ স্টার্টআপ প্রসেসে সমস্যা: {e}")

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
            chatBox.innerHTML += `<div class="message user-msg">${query}</div>`;
            inputField.value = "";
            chatBox.scrollTop = chatBox.scrollHeight;
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
                chatBox.innerHTML += `<div class="message bot-msg" style="color: red;">দুঃখিত, উত্তর তৈরিতে সমস্যা হয়েছে।</div>`;
                console.error("Error:", error);
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        function handleKeyPress(event) {
            if (event.key === 'Enter') { sendMessage(); }
        }
    </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/chat")
async def chat_with_bot(user_question: str):
    global GLOBAL_KNOWLEDGE_CONTEXT
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY পাওয়া যায়নি। রেন্ডার এনভায়রনমেন্ট চেক করুন।")
        
    system_prompt = f"""
    তুমি বিটাক (BITAC) এর একজন অফিসিয়াল এআই অ্যাসিস্ট্যান্ট। 
    
    ১. যদি ইউজারের প্রশ্নটি বিটাক, বিটাকের প্রশিক্ষণ (Training), কোনো কোর্স, ফি, সুযোগ-সুবিধা বা কার্যক্রম সম্পর্কিত হয়, তবে অবশ্যই নিচে দেওয়া 'বিটাক ফাইল ও লাইভ নলেজ বেজ' থেকে বিস্তারিত এবং সঠিক উত্তর দেবে। বানিয়ে বা ভুল কিছু বলবে না।
    ২. যদি ইউজারের প্রশ্নটি সাধারণ কোনো বিষয় (যেমন: বুয়েট কোথায়, বাংলাদেশ সম্পর্কে বলো, কেমন আছো ইত্যাদি) নিয়ে হয়, তবে তোমার নিজস্ব নলেজ বেজ থেকে বাংলায় পেশাদার উত্তর দাও।
    
    সবসময় বাংলায় সুন্দর, গোছানো ও সাবলীলভাবে উত্তর দেবে।
    
    বিটাক ফাইল ও লাইভ নলেজ বেজ:
    {GLOBAL_KNOWLEDGE_CONTEXT}
    """
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ],
            # Groq এর বর্তমান সচল ও দ্রুতগতির মডেল
            model="llama-3.1-8b-instant", 
            temperature=0.3
        )
        return {"response": chat_completion.choices[0].message.content}
    except Exception as e:
        print("❌ GROQ API CALL FAILED!")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000)) 
    uvicorn.run(app, host="0.0.0.0", port=port)
