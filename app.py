import os
import json
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests
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

# ১. ফলব্যাক ডাটা (যদি কোনো কারণে Jina AI ডাউন থাকে বা ইন্টারনেট ইস্যু হয়, তবে এটি কাজ করবে)
BITAC_FALLBACK_INFO = """
বাংলাদেশ ইন্ডাস্ট্রিয়াল টেকনিক্যাল অ্যাসিস্ট্যান্স সেন্টার (BITAC - বিটাক) শিল্প মন্ত্রণালয়ের অধীন একটি সরকারি কারিগরি প্রতিষ্ঠান।
প্রধান কাজ: শিল্প ক্ষেত্রে উৎপাদনশীলতা বৃদ্ধি, কারিগরি সহায়তা প্রদান, খুচরা যন্ত্রপাতি তৈরি এবং দক্ষ জনশক্তি তৈরি করা।
প্রধান কার্যালয় ঢাকার তেজগাঁওয়ে অবস্থিত। এছাড়া চট্টগ্রাম, খুলনা, বগুড়া, চাঁদপুর ও রাঙ্গামাটিতে এর আঞ্চলিক কেন্দ্র রয়েছে।
এখানে বিভিন্ন মেয়াদী (যেমন: ২ মাস বা ৩ মাস) কারিগরি ও বৃত্তিমূলক ট্রেডে প্রফেশনাল ও হাতে-কলমে প্রশিক্ষণ দেওয়া হয়।
"""

GLOBAL_KNOWLEDGE_CONTEXT = BITAC_FALLBACK_INFO  # শুরুতে ফলব্যাক দিয়ে ইনিশিয়ালাইজ করা হলো

@app.head("/")
async def head_home():
    return HTMLResponse(content="", status_code=200)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return HTMLResponse(content="", status_code=200)

def load_context_via_jina():
    """Jina AI Proxy Scraper ব্যবহার করে বিটাক ওয়েবসাইট থেকে ডায়নামিক ডাটা রিড করার ফাংশন"""
    global GLOBAL_KNOWLEDGE_CONTEXT
    combined_text = ""
    
    # বিটাকের যে লিঙ্কগুলো আপনি রিড করাতে চান
    target_urls = [
        "https://www.bitac.gov.bd", 
        "https://www.bitac.gov.bd/site/page/89531ca1-a83d-4c31-9257-8fb6fc9ef444"
    ]
    
    print("🌐 Jina AI এর মাধ্যমে বিটাক ওয়েবসাইট থেকে লাইভ ডাটা সংগ্রহের চেষ্টা করা হচ্ছে...")
    
    for url in target_urls:
        try:
            # আসল লিঙ্কের শুরুতে r.jina.ai যুক্ত করা হয়েছে
            jina_proxy_url = f"https://r.jina.ai/{url}"
            
            # Jina AI কে রিকোয়েস্ট পাঠানো (টাইমআউট ১৫ সেকেন্ড রাখা হয়েছে যাতে বড় পেজও লোড হতে পারে)
            response = requests.get(jina_proxy_url, timeout=15)
            
            if response.status_code == 200:
                page_data = response.text.strip()
                if len(page_data) > 100:
                    combined_text += page_data + "\n\n"
                    print(f"✅ সফলভাবে ডাটা রিড হয়েছে: {url}")
                else:
                    print(f"⚠️ লিঙ্ক থেকে পর্যাপ্ত টেক্সট পাওয়া যায়নি: {url}")
            else:
                print(f"❌ Jina AI এরর কোড দিয়েছে ({response.status_code}) এই লিঙ্কের জন্য: {url}")
                
        except Exception as e:
            print(f"⚠️ Jina AI এর মাধ্যমে {url} স্ক্র্যাপ করতে সমস্যা হয়েছে: {e}")
            
    # সংগৃহীত ডাটা ফিল্টার ও মেমোরি সাইজ কন্ট্রোল করা
    final_text = combined_text.strip()
    if len(final_text) > 300:
        # রেন্ডার র‍্যাম সেইফ রাখতে সর্বোচ্চ ১৫,০০০ ক্যারেক্টার নেওয়া হলো
        GLOBAL_KNOWLEDGE_CONTEXT = final_text[:15000]
        print(f"🎉 চমৎকার! ওয়েবসাইট থেকে মোট {len(GLOBAL_KNOWLEDGE_CONTEXT)} ক্যারেক্টার লাইভ ডাটা মেমোরিতে সেট করা হয়েছে।")
    else:
        GLOBAL_KNOWLEDGE_CONTEXT = BITAC_FALLBACK_INFO
        print("⚠️ লাইভ ডাটা লোড করা যায়নি। সেফটির জন্য ডিফল্ট ফলব্যাক ডাটা কার্যকর করা হলো।")

# FastAPI সার্ভার চালু হওয়ার সময় এই ইভেন্টটি রান করবে
@app.on_event("startup")
async def startup_event():
    try:
        load_context_via_jina()
    except Exception as e:
        print(f"❌ স্টার্টআপ প্রসেসে সমস্যা কিন্তু সার্ভার সচল থাকবে: {e}")

@app.get("/", response_class=HTMLResponse)
def home():
    # ফ্রন্টএন্ড চ্যাট ইন্টারফেস (আগের মতোই থাকবে)
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
        raise HTTPException(status_code=500, detail="GROQ_API_KEY পাওয়া যায়নি।")
        
    system_prompt = f"""
    তুমি বিটাক (BITAC) এর একজন অফিসিয়াল এআই অ্যাসিস্ট্যান্ট। 
    
    ১. যদি ইউজারের প্রশ্নটি বিটাক, বিটাকের ট্রেনিং, কোনো কোর্স, সুযোগ-সুবিধা বা কার্যক্রম সম্পর্কিত হয়, তবে অবশ্যই নিচে দেওয়া 'বিটাক লাইভ নলেজ বেজ' থেকে বিস্তারিত এবং সঠিক উত্তর দেবে। বানিয়ে বা ভুল কিছু বলবে না।
    ২. যদি ইউজারের প্রশ্নটি সাধারণ কোনো বিষয় (যেমন: বুয়েট কোথায়, বাংলাদেশ সম্পর্কে বলো ইত্যাদি) নিয়ে হয়, তবে তোমার নিজস্ব নলেজ বেজ থেকে বাংলায় পেশাদার উত্তর দাও।
    
    সবসময় বাংলায় সুন্দর ও সাবলীলভাবে উত্তর দেবে।
    
    বিটাক লাইভ নলেজ বেজ:
    {GLOBAL_KNOWLEDGE_CONTEXT}
    """
    
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ],
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
