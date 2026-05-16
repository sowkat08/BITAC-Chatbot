import os
import json
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
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

# রেন্ডার মেমোরি বাঁচানোর জন্য ফিক্সড ব্যাকআপ ডাটা
BITAC_FALLBACK_INFO = """
বাংলাদেশ ইন্ডাস্ট্রিয়াল টেকনিক্যাল অ্যাসিস্ট্যান্স সেন্টার (BITAC - বিটাক) শিল্প মন্ত্রণালয়ের অধীন একটি সরকারি স্বায়ত্তশাসিত কারিগরি প্রতিষ্ঠান।
প্রধান কাজ: শিল্প ক্ষেত্রে উৎপাদনশীলতা বৃদ্ধি, কারিগরি সহায়তা প্রদান, এবং খুচরা যন্ত্রপাতি (Spare Parts) তৈরি।
ট্রেনিং ও কোর্স: দেশের যুবসমাজকে দক্ষ করতে বিভিন্ন মেয়াদী (যেমন: ২ মাস বা ৩ মাস) কারিগরি ও বৃত্তিমূলক ট্রেডে প্রফেশনাল ও হাতে-কলমে প্রশিক্ষণ দেওয়া হয়। মহিলাদের জন্য বিশেষ আত্মকর্মসংস্থানমূলক কোর্স রয়েছে।
কেন্দ্রসমূহ: প্রধান কার্যালয় ঢাকার তেজগাঁওয়ে অবস্থিত। আঞ্চলিক কেন্দ্রসমূহ: চট্টগ্রাম, খুলনা, বগুড়া, চাঁদপুর ও রাঙ্গামাটি।
"""

GLOBAL_KNOWLEDGE_CONTEXT = BITAC_FALLBACK_INFO  # শুরুতে ডিফল্ট ডাটা সেট থাকবে

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="", status_code=200)

def load_all_context_once():
    """র্যাম সেভ করার জন্য অত্যন্ত লাইটওয়েট উপায়ে ওয়েবসাইট থেকে শুধু টেক্সটটুকু রিড করবে"""
    global GLOBAL_KNOWLEDGE_CONTEXT
    context_text = ""
    
    website_urls = [
        "https://www.bitac.gov.bd", 
        "https://www.bitac.gov.bd/site/page/89531ca1-a83d-4c31-9257-8fb6fc9ef444"
    ]
    
    for url in website_urls:
        try:
            response = requests.get(url, timeout=8, verify=False)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # মেমোরি অপ্টিমাইজেশন: অপ্রয়োজনীয় স্ক্রিপ্ট, স্টাইল ও মেনু আগেই ডিলেট করে র‍্যাম খালি করা
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.extract()
                    
                # শুধু আসল টেক্সটটুকু নেওয়া এবং অতিরিক্ত স্পেস মুছে ফেলা
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                clean_text = '\n'.join(chunk for chunk in chunks if chunk)
                
                context_text += clean_text + "\n"
        except Exception as e:
            print(f"⚠️ ওয়েবসাইট {url} পড়তে সমস্যা: {e}")
            
    cleaned_context = context_text.strip()
    if len(cleaned_context) > 200:
        # মেমোরি লিমিট ঠিক রাখতে সর্বোচ্চ ১৫,০০০ ক্যারেক্টার নেওয়া হলো (৫১২এমবি র‍্যামের জন্য নিরাপদ)
        GLOBAL_KNOWLEDGE_CONTEXT = BITAC_FALLBACK_INFO + "\n" + cleaned_context[:15000]
        print("✅ বিটাক লাইভ ডাটা মেমোরি ফ্রেন্ডলি উপায়ে লোড হয়েছে।")
    else:
        print("⚠️ লাইভ ডাটা পাওয়া যায়নি, ফলব্যাক ডাটা কার্যকর আছে।")

@app.on_event("startup")
async def startup_event():
    # রেন্ডার সার্ভার যেন সহজে স্টার্ট হতে পারে, তাই ডাটা লোড প্রসেসটি হালকা রাখা হলো
    try:
        load_all_context_once()
    except Exception as e:
        print(f"❌ স্টার্টআপে সমস্যা কিন্তু সার্ভার সচল থাকবে: {e}")

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
    global GLOBAL_KNOWLEDGE_CONTEXT
    
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY পাওয়া যায়নি। রেন্ডার এনভায়রনমেন্ট চেক করুন।")
        
    system_prompt = f"""
    তুমি বিটাক (BITAC) এর একজন অফিসিয়াল এআই অ্যাসিস্ট্যান্ট। 
    
    ১. যদি ইউজারের প্রশ্নটি বিটাক, বিটাকের ট্রেনিং, কোর্স বা কার্যক্রম সম্পর্কিত হয়, তবে অবশ্যই নিচে দেওয়া 'বিটাক নলেজ বেজ' থেকে উত্তর দেবে।
    ২. যদি ইউজারের প্রশ্নটি সাধারণ কোনো বিষয় (যেমন: বুয়েট কোথায়, সাধারণ জ্ঞান ইত্যাদি) নিয়ে হয়, তবে তোমার নিজস্ব নলেজ বেজ থেকে বাংলায় পেশাদার উত্তর দাও।
    
    সবসময় বাংলায় সুন্দর করে উত্তর দেবে।
    
    বিটাক নলেজ বেজ:
    {GLOBAL_KNOWLEDGE_CONTEXT}
    """
    
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
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
        print("❌ GROQ API CALL FAILED!")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000)) 
    uvicorn.run(app, host="0.0.0.0", port=port)
