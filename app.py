import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader, WebBaseLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from groq import Groq

# এনভায়রনমেন্ট ভেরিয়েবল লোড করা
load_dotenv()

app = FastAPI()

# CORS ক্লায়েন্ট পারমিশন
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Groq ক্লায়েন্ট ইনিশিয়ালাইজ করা
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY খুঁজে পাওয়া যায়নি! অনুগ্রহ করে রেন্ডার ড্যাশবোর্ডে সেট করুন।")

groq_client = Groq(api_key=GROQ_API_KEY)

# বৈশ্বিক ভেরিয়েবল (Global Retriever)
retriever = None

def init_knowledge_base():
    """সব ফাইল এবং ওয়েবসাইট লিঙ্ক থেকে নলেজ বেস তৈরি করার ফাংশন"""
    global retriever
    documents = []
    data_dir = "./data" # এই ফোল্ডারে আপনার সব ফাইল থাকবে
    
    # ১. ফোল্ডারের ভেতরের সব ফাইল (PDF, DOCX, XLSX, JSON) রিড করা
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            try:
                if file.endswith('.pdf'):
                    documents.extend(PyPDFLoader(file_path).load())
                elif file.endswith('.docx') or file.endswith('.doc'):
                    documents.extend(Docx2txtLoader(file_path).load())
                elif file.endswith('.xlsx') or file.endswith('.xls'):
                    documents.extend(UnstructuredExcelLoader(file_path).load())
                elif file.endswith('.json'):
                    # JSON ফাইল রিড করার সহজ লজিক
                    with open(file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                        json_string = json.dumps(json_data, ensure_ascii=False)
                        documents.append(Document(page_content=json_string, metadata={"source": file}))
            except Exception as e:
                print(f"ফাইল {file} পড়তে সমস্যা হয়েছে: {e}")
                
    # ২. 🌐 একাধিক ওয়েবসাইট লিঙ্ক থেকে নলেজ নেওয়া
    website_urls = [
        "https://www.bitac.gov.bd", 
        "https://www.bitac.gov.bd/site/page/89531ca1-a83d-4c31-9257-8fb6fc9ef444"
    ]
    
    for url in website_urls:
        try:
            web_loader = WebBaseLoader(url)
            documents.extend(web_loader.load())
        except Exception as e:
            print(f"ওয়েবসাইট {url} থেকে তথ্য নিতে সমস্যা হয়েছে: {e}")
    
    if not documents:
        print("সতর্কতা: কোনো ডকুমেন্ট বা ওয়েবসাইট লিঙ্ক থেকে তথ্য পাওয়া যায়নি!")
        return None

    # ৩. টেক্সটগুলোকে ছোট টুকরো করা (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)
    
    # ৪. ফ্রি এম্বেডিং মডেল ও ভেক্টর ডাটাবেজ তৈরি (ChromaDB)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3}) 
    print("✅ নলেজ বেস সফলভাবে তৈরি হয়েছে!")

# সার্ভার চালু হওয়ার সময় নলেজ বেস তৈরি হবে
@app.on_event("startup")
def startup_event():
    init_knowledge_base()

@app.get("/")
def home():
    return {"status": "Running", "message": "BITAC AI Chatbot API is Live!"}

@app.post("/chat")
async def chat_with_bot(user_question: str):
    global retriever
    
    context = ""
    if retriever:
        relevant_docs = retriever.get_relevant_documents(user_question)
        context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    system_prompt = f"""
    তুমি বিটাক (BITAC - Bangladesh Industrial Technical Assistance Center) এর একজন অফিসিয়াল এআই অ্যাসিস্ট্যান্ট। 
    নিচে দেওয়া 'কনটেক্সট তথ্য' থেকে ইউজারের প্রশ্নের সঠিক এবং পেশাদার উত্তর দাও। 
    যদি কনটেক্সটে উত্তর না থাকে, তবে বিনয়ের সাথে বলো যে এই মুহূর্তে তথ্যটি তোমার কাছে নেই, ভুল বা বানিয়ে কোনো উত্তর দেবে না।
    সবসময় বাংলায় উত্তর দেবে।
    
    কনটেক্সট তথ্য (Knowledge Base):
    {context}
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
    # রেন্ডার সার্ভার যে পোর্ট দেবে সেটি নেবে, না পেলে ডিফল্ট ৮০০০ পোর্টে চলবে
    port = int(os.getenv("PORT", 8000)) 
    uvicorn.run(app, host="0.0.0.0", port=port)
