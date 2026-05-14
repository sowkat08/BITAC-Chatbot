import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
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

# --- ২. অটোমেটিক ফাইল রিডার ফাংশন ---
def load_all_data(folder="data"):
    text_data = ""
    # ফোল্ডার না থাকলে তৈরি করবে যাতে এরর না আসে
    if not os.path.exists(folder):
        os.makedirs(folder)
        return text_data
        
    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        try:
            # টেক্সট ফাইল
            if file.endswith(".txt"):
                with open(path, "r", encoding="utf-8") as f: 
                    text_data += f"\n--- Source: {file} ---\n" + f.read()
            
            # PDF ফাইল
            elif file.endswith(".pdf"):
                reader = PyPDF2.PdfReader(path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                text_data += f"\n--- Source: {file} ---\n" + text
            
            # Excel ফাইল
            elif file.endswith(".xlsx") or file.endswith(".xls"):
                df = pd.read_excel(path)
                text_data += f"\n--- Source: {file} ---\n" + df.to_string()
            
            # Word ফাইল
            elif file.endswith(".docx"):
                doc = Document(path)
                text = "\n".join([p.text for p in doc.paragraphs])
                text_data += f"\n--- Source: {file} ---\n" + text
        except Exception as e:
            print(f"Error reading {file}: {e}")
            continue
    return text_data

# বিটিকের নলেজ বেস একবার লোড করে রাখা
KNOWLEDGE_BASE = load_all_data()

# --- ৩. এআই প্রসেসিং ফাংশন ---
def get_ai_response(user_query):
    # gemini-1.5-flash মডেলটি দ্রুত এবং ভালো রেসপন্স দেয়
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # বিটিকের স্পেসিফিক প্রম্পট
    prompt = f"""
    তুমি বিটিক (BITAC) এর একজন অভিজ্ঞ টেকনিক্যাল অ্যাসিস্ট্যান্ট। 
    নিচের তথ্যগুলো ব্যবহার করে ইউজারের প্রশ্নের সঠিক এবং পেশাদার উত্তর দাও। 
    তথ্য না থাকলে বিনয়ের সাথে বলো যে তোমার কাছে এই মুহূর্তে তথ্যটি নেই।
    
    তথ্যসমূহ:
    {KNOWLEDGE_BASE}
    
    ইউজারের প্রশ্ন: {user_query}
    """
    response = model.generate_content(prompt)
    return response.text


# --- ৪. নতুন যোগ করা রুট: রুট পাথ (404 Error সমাধান করবে) ---
@app.get("/")
def read_root():
    return {
        "status": "Online",
        "bot_name": "BITAC AI Assistant",
        "message": "সার্ভার সফলভাবে কাজ করছে!",
        "api_docs": "/docs"
    }


# --- ৫. নতুন যোগ করা রুট: ফেভিকন এরর হ্যান্ডলার ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # কোনো ফেভিকন না থাকলে ব্ল্যাঙ্ক রেসপন্স দেবে যাতে লগে নোংরা এরর না আসে
    return JSONResponse(content={"status": "no favicon"}, status_code=200)


# --- ৬. ইউনিভার্সাল চ্যাট এন্ডপয়েন্ট (সব প্ল্যাটফর্মের জন্য) ---
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


# --- ৭. সার্ভার রান করা (Render ফ্রেন্ডলি) ---
if __name__ == "__main__":
    import uvicorn
    # Render নিজে থেকে পোর্ট অ্যাসাইন করে, তাই এটি প্রয়োজন
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)