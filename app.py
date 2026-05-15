import os
import json
from fastapi import FastAPI, HTTPException
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

def get_all_context():
    """ডাটাবেজ ছাড়াই সরাসরি সব ফাইল এবং ওয়েবসাইট থেকে টেক্সট তুলে আনার লাইটওয়েট ফাংশন"""
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
                print(f"ফাইল {file} পড়তে সমস্যা: {e}")

    # ২. 🌐 ওয়েবসাইট লিঙ্ক রিড করা
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
            print(f"ওয়েবসাইট {url} পড়তে সমস্যা: {e}")
            
    # রেন্ডার ফ্রি সার্ভারের মেমোরি অনুযায়ী কনটেক্সট সাইজ একটু সীমিত রাখা হলো
    return context_text[:30000] 

@app.get("/")
def home():
    return {"status": "Running", "message": "BITAC Groq AI Chatbot is Live!"}

@app.post("/chat")
async def chat_with_bot(user_question: str):
    # ইউজার মেসেজ দিলে সরাসরি ফাইল ও ওয়েবসাইট থেকে তথ্য তুলে আনবে
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
        # আপনার কাঙ্ক্ষিত Groq API কল
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
    port = int(os.getenv("PORT", 8000)) 
    uvicorn.run(app, host="0.0.0.0", port=port)
