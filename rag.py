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
from dotenv import load_dotenv
load_dotenv(override=True)
def init_rag():
    docs = []
    data_dir = "data"
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            if file.endswith(".pdf"):
                docs.extend(PyPDFLoader(file_path).load())
            elif file.endswith((".txt", ".md")):
                docs.extend(TextLoader(file_path, encoding="utf-8").load())
                
    if not docs:
        docs = [Document(page_content="Bienvenue dans l'assistant Enterprise Copilot.")]

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    return vector_store

# Instance globale du Vector Store pour l'ajout dynamique
vector_store = init_rag()
retriever = vector_store.as_retriever(search_kwargs={"k": 2})

def get_rag_chain():
    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),  # <-- Ajout crucial pour éviter l'erreur
        model="deepseek/deepseek-chat",
        temperature=0
    )
    
    template = """Tu es un assistant intelligent d'entreprise. Réponds en te basant uniquement sur ce contexte :
{context}
Question : {input}"""
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