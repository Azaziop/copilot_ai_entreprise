import json
import os
import shutil
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database import (
    init_db,
    SessionLocal,
    ChatHistoryModel,
    ChatSession,
    DocumentRecord,
)
from rag import vector_store
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from evaluation import evaluate_response
from rag import retriever
from src.ingestion.tabular import load_tabular_documents
from streaming_chat import stream_chat

load_dotenv(override=True)

app = FastAPI(title="Enterprise Copilot Modular API", version="5.1")

# --- CONFIGURATION CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    session_id: int | None = None

class QueryResponse(BaseModel):
    answer: str
    route_pris: str
    history_id: int
    session_id: int | None = None


class SessionCreate(BaseModel):
    title: str | None = None


def _ensure_session(db: Session, session_id: int | None, first_question: str) -> ChatSession:
    if session_id is not None:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            return session
    title = (first_question or "Nouvelle discussion").strip()[:80] or "Nouvelle discussion"
    session = ChatSession(title=title, user_id=None)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _session_memory(db: Session, session_id: int | None) -> list[dict]:
    if not session_id:
        return []
    rows = (
        db.query(ChatHistoryModel)
        .filter(ChatHistoryModel.session_id == session_id)
        .order_by(ChatHistoryModel.id.asc())
        .all()
    )
    return [{"question": r.question, "answer": r.answer} for r in rows]


@app.get("/")
def home():
    return {"message": "API Enterprise Copilot modulaire en ligne."}


@app.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    rows = (
        db.query(ChatSession)
        .order_by(ChatSession.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "message_count": len(s.messages or []),
        }
        for s in rows
    ]


@app.post("/sessions")
def create_session(body: SessionCreate | None = None, db: Session = Depends(get_db)):
    title = (body.title if body and body.title else "Nouvelle discussion")[:100]
    session = ChatSession(title=title, user_id=None)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "message_count": 0,
    }


@app.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    messages = (
        db.query(ChatHistoryModel)
        .filter(ChatHistoryModel.session_id == session_id)
        .order_by(ChatHistoryModel.id.asc())
        .all()
    )
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "messages": [
            {
                "id": m.id,
                "question": m.question,
                "answer": m.answer,
                "route_pris": m.route_pris,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    db.delete(session)
    db.commit()
    return {"ok": True}


@app.post("/chat", response_model=QueryResponse)
def chat_endpoint(request: QueryRequest, db: Session = Depends(get_db)):
    """Compat non-stream (collecte le stream interne)."""
    try:
        session = _ensure_session(db, request.session_id, request.question)
        memory = _session_memory(db, session.id)
        answer = ""
        route_pris = "DIRECT"
        for event in stream_chat(request.question, history=memory):
            if event.get("type") == "token":
                answer += event.get("text") or ""
            elif event.get("type") == "done":
                answer = event.get("answer") or answer
                route_pris = event.get("route") or route_pris

        if session.title in (None, "", "Nouvelle discussion"):
            session.title = request.question.strip()[:80]

        db_item = ChatHistoryModel(
            session_id=session.id,
            question=request.question,
            answer=answer,
            route_pris=route_pris,
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        return {
            "answer": answer,
            "route_pris": route_pris,
            "history_id": db_item.id,
            "session_id": session.id,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
def chat_stream_endpoint(request: QueryRequest, db: Session = Depends(get_db)):
    """SSE stream: reasoning, route, sources, tokens, done (+ session memory)."""
    session = _ensure_session(db, request.session_id, request.question)
    memory = _session_memory(db, session.id)
    session_id = session.id

    def event_gen():
        answer = ""
        route_pris = "DIRECT"
        try:
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
            for event in stream_chat(request.question, history=memory):
                etype = event.get("type")
                if etype == "token":
                    answer += event.get("text") or ""
                elif etype == "done":
                    answer = event.get("answer") or answer
                    route_pris = event.get("route") or route_pris
                    sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                    if sess and sess.title in (None, "", "Nouvelle discussion"):
                        sess.title = request.question.strip()[:80]
                    db_item = ChatHistoryModel(
                        session_id=session_id,
                        question=request.question,
                        answer=answer,
                        route_pris=route_pris,
                    )
                    db.add(db_item)
                    db.commit()
                    db.refresh(db_item)
                    event = {
                        **event,
                        "history_id": db_item.id,
                        "session_id": session_id,
                    }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            db.rollback()
            err = {"type": "error", "text": str(exc)}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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