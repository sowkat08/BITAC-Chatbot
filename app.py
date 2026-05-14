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

# এপিআই ভার্সন নিয়ে আর যেন ঝামেলা না হয়, তাই এখানে গ্লোবালি সেট করা হলো
genai.configure(
    api_key=os.getenv("GEMINI_API_KEY"),
    transport='rest' # অনেক সময় gRPC ব্লকিং থাকলে REST এটি সমাধান করে
)

app = FastAPI(
    title="BITAC AI Assistant API",
    version="1.0.0"
)

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

# --- ৩. এআই প্রসেসিং ফাংশন (সব ধরণের এরর প্রুফ) ---
def get_ai_response(user_query):
    try:
        # মডেলের নাম এবং রিজিওনাল ইস্যু এড়াতে models/ পাথ ব্যবহার করা হলো
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        
        prompt = f"তথ্যসমূহ: {KNOWLEDGE_BASE}\nইউজারদের প্রশ্ন: {user_query}"
        
        # জেনারেশন কনফিগ দিয়ে রেসপন্স নিশ্চিত করা
        response = model.generate_content(prompt)
        
        return response.text if response.text else "দুঃখিত, কোনো উত্তর পাওয়া যায়নি।"
            
    except Exception as e:
        # আসল এররটি এখানে প্রিন্ট হবে যা আপনি Render লগে দেখতে পাবেন
        print(f"DEBUG: {str(e)}")
        return "এআই এই মুহূর্তে কাজ করছে না। অনুগ্রহ করে কিছুক্ষণ পর চেষ্টা করুন।"

# --- ৪. HTML UI এবং চ্যাট এন্ডপয়েন্ট (বাকি অংশ আগের মতোই) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    # এখানে আপনার আগের HTML কোডটি থাকবে...
    return HTMLResponse(content="<h1>BITAC AI Server is Running!</h1><p>Please use the UI or API to chat.</p>")

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    reply = get_ai_response(data.get("msg"))
    return {"reply": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
