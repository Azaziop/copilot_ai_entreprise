import os
import shutil
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import init_db, SessionLocal, ChatHistoryModel, DocumentRecord
from agents import app_graph
from rag import vector_store
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from evaluation import evaluate_response
from rag import retriever
load_dotenv(override=True)
app = FastAPI(title="Enterprise Copilot Modular API", version="5.0")
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CONFIGURATION CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise toutes les origines (ou mets ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    route_pris: str
    history_id: int

@app.get("/")
def home():
    return {"message": "API Enterprise Copilot modulaire en ligne."}

@app.post("/chat", response_model=QueryResponse)
def chat_endpoint(request: QueryRequest, db: Session = Depends(get_db)):
    try:
        initial_state = {"question": request.question, "generation": "", "decision": ""}
        final_state = app_graph.invoke(initial_state)
        
        answer = final_state["generation"]
        route_pris = final_state["decision"]
        
        db_item = ChatHistoryModel(
            question=request.question,
            answer=answer,
            route_pris=route_pris
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        
        return {
            "answer": answer,
            "route_pris": route_pris,
            "history_id": db_item.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
class EvalRequest(BaseModel):
    question: str
    answer: str

@app.post("/evaluate")
def evaluate_endpoint(request: EvalRequest):
    try:
        # Récupérer le contexte associé via le retriever
        docs = retriever.invoke(request.question)
        context = "\n".join([doc.page_content for doc in docs])
        
        # Lancer l'évaluation
        evaluation_result = evaluate_response(request.question, context, request.answer)
        return {
            "evaluation": evaluation_result,
            "retrieved_context_snippet": context[:300]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    return db.query(ChatHistoryModel).all()

@app.post("/upload")
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        new_docs = []
        if file.filename.endswith(".pdf"):
            new_docs = PyPDFLoader(file_path).load()
        elif file.filename.endswith((".txt", ".md")):
            new_docs = TextLoader(file_path, encoding="utf-8").load()
            
        if new_docs:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = text_splitter.split_documents(new_docs)
            vector_store.add_documents(chunks)

        file_ext = file.filename.split(".")[-1]
        db_doc = DocumentRecord(filename=file.filename, file_type=file_ext)
        db.add(db_doc)
        db.commit()
        
        return {"message": f"Fichier {file.filename} indexé et enregistré.", "filename": file.filename}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))