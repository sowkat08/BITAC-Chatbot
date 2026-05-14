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
                    text_data += f"\n{f.read()}"
            elif file.endswith(".pdf"):
                reader = PyPDF2.PdfReader(path)
                for page in reader.pages:
                    text_data += page.extract_text() or ""
            elif file.endswith(".xlsx") or file.endswith(".xls"):
                df = pd.read_excel(path)
                text_data += f"\n{df.to_string()}"
            elif file.endswith(".docx"):
                doc = Document(path)
                text_data += "\n".join([p.text for p in doc.paragraphs])
        except Exception: continue
    return text_data

KNOWLEDGE_BASE = load_all_data()

# --- ৩. এআই প্রসেসিং ফাংশন (Groq মেথড) ---
def get_ai_response(user_query):
    try:
        # এখানে Llama 3 মডেল ব্যবহার করা হচ্ছে যা অত্যন্ত শক্তিশালী
        completion = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
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
        print(f"Groq Error: {str(e)}")
        return "দুঃখিত, এআই সার্ভারে সমস্যা হচ্ছে। অনুগ্রহ করে কিছুক্ষণ পর চেষ্টা করুন।"

# --- ৪. HTML UI এবং এন্ডপয়েন্ট (আগের মতোই) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    # এখানে আপনার আগের সুন্দর সবুজ ইন্টারফেসের HTML কোডটি থাকবে
    return HTMLResponse(content="<h1>BITAC AI (Groq) is Running!</h1>")

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    reply = get_ai_response(data.get("msg"))
    return {"reply": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))