import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from dotenv import load_dotenv
import PyPDF2
import pandas as pd
from docx import Document

# ১. এনভায়রনমেন্ট সেটআপ
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="BITAC AI Assistant (Stable Version)")

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

# --- ৩. এআই প্রসেসিং ফাংশন (Direct HTTP Request পদ্ধতি) ---
def get_ai_response(user_query):
    try:
        # সরাসরি স্টেবিল v1 URL ব্যবহার
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        headers = {'Content-Type': 'application/json'}
        
        prompt = f"""
        তুমি বিটিক (BITAC) এর একজন অভিজ্ঞ টেকনিক্যাল অ্যাসিস্ট্যান্ট। 
        নিচের তথ্যগুলো ব্যবহার করে ইউজারের প্রশ্নের উত্তর দাও।
        
        তথ্যসমূহ:
        {KNOWLEDGE_BASE}
        
        ইউজার প্রশ্ন: {user_query}
        """
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        # গুগল লাইব্রেরি ছাড়াই সরাসরি রিকোয়েস্ট পাঠানো
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"Error Log: {response.text}")
            return "দুঃখিত, এআই এই মুহূর্তে উত্তর দিতে পারছে না।"
            
    except Exception as e:
        return f"সার্ভার এরর: {str(e)}"

# --- ৪. রুট পাথ এবং চ্যাট ইন্টারফেস ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    # আগের সুন্দর সবুজ HTML কোডটি এখানে থাকবে (সংক্ষেপ করা হলো)
    return HTMLResponse(content="<h1>BITAC AI Stable Server is Running!</h1>")

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_msg = data.get("msg")
    reply = get_ai_response(user_msg)
    return {"reply": reply}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
