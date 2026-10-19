import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_core.documents import Document
from src.ingestion.tabular import load_tabular_documents
from dotenv import load_dotenv
load_dotenv(override=True)
def init_rag():
    docs = []
    data_dirs = ["data/raw", "data"]
    for data_dir in data_dirs:
        if not os.path.isdir(data_dir):
            continue
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            if not os.path.isfile(file_path):
                continue
            lower = file.lower()
            if lower.endswith(".pdf"):
                docs.extend(PyPDFLoader(file_path).load())
            elif lower.endswith((".txt", ".md")):
                docs.extend(TextLoader(file_path, encoding="utf-8").load())
            elif lower.endswith((".csv", ".xlsx", ".xls")):
                docs.extend(load_tabular_documents(file_path))
                

    if not docs:
        docs = [Document(page_content="Bienvenue dans l'assistant Enterprise Copilot.")]

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    chunks = text_splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    persist_directory = "./chroma_db"

    # Réutilise l'index persistant s'il existe déjà (évite de tout écraser)
    if os.path.isdir(persist_directory) and os.listdir(persist_directory):
        vector_store = Chroma(
            embedding_function=embeddings,
            persist_directory=persist_directory,
        )
        if chunks:
            vector_store.add_documents(chunks)
        return vector_store

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory,
    )
    return vector_store

# Instance globale du Vector Store pour l'ajout dynamique
vector_store = init_rag()
retriever = vector_store.as_retriever(search_kwargs={"k": 10})

def get_rag_chain():
    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),  # <-- Ajout crucial pour éviter l'erreur
        model="deepseek/deepseek-chat",
        temperature=0
    )
    
    template = """Tu es un analyste documentaire senior. Réponds UNIQUEMENT à partir du contexte.
Si le contexte contient des chiffres (capitaux propres, bilan, IFRS, années), cite-les explicitement avec l'unité et l'année.
Si l'information n'est pas dans le contexte, dis-le clairement sans inventer.
Réponds en markdown structuré (titres, listes, tableaux si utile).

Contexte:
{context}

Question: {input}"""
    prompt = ChatPromptTemplate.from_template(template)

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    rag_chain = (
        {"context": retriever | format_docs, "input": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain