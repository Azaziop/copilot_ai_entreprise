import os
import shutil
from datetime import datetime

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
from src.ingestion.tabular import load_tabular_documents
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

@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(DocumentRecord).order_by(DocumentRecord.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in docs
    ]


@app.post("/upload")
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nom de fichier manquant.")

        data_dir = "data/raw"
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        name = file.filename.lower()
        new_docs = []
        if name.endswith(".pdf"):
            new_docs = PyPDFLoader(file_path).load()
        elif name.endswith((".txt", ".md")):
            new_docs = TextLoader(file_path, encoding="utf-8").load()
        elif name.endswith((".csv", ".xlsx", ".xls")):
            new_docs = load_tabular_documents(file_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="Formats supportés: PDF, TXT, MD, CSV, XLSX.",
            )

        if not new_docs:
            raise HTTPException(
                status_code=400,
                detail="Aucun contenu extractible depuis ce fichier.",
            )

        # CSV/XLSX are already row-chunked; still split long text rows safely
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
        chunks = text_splitter.split_documents(new_docs)
        vector_store.add_documents(chunks)

        file_ext = file.filename.rsplit(".", 1)[-1]
        existing = (
            db.query(DocumentRecord)
            .filter(DocumentRecord.filename == file.filename)
            .first()
        )
        if existing:
            existing.file_type = file_ext
            existing.uploaded_at = datetime.utcnow()
            action = "ré-indexé"
        else:
            db.add(DocumentRecord(filename=file.filename, file_type=file_ext))
            action = "indexé et enregistré"

        db.commit()
        return {
            "message": f"Fichier {file.filename} {action}.",
            "filename": file.filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))