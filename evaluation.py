import os
from dotenv import load_dotenv
from rag import get_rag_chain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv(override=True)
eval_llm = ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    model="deepseek/deepseek-chat",
    temperature=0
)

def evaluate_response(question: str, context: str, answer: str) -> dict:
    """Évalue si la réponse est fidèle au contexte fourni et répond bien à la question."""
    eval_prompt = ChatPromptTemplate.from_template("""Tu es un évaluateur expert d'un système RAG d'entreprise.
Analyse les éléments suivants et réponds strictement sous format JSON avec deux scores entre 0 et 1 :
- faithfulness : La réponse est-elle strictement basée sur le contexte sans hallucination ? (0 ou 1)
- relevance : La réponse répond-elle précisément à la question posée ? (0 ou 1)

Contexte : {context}
Question : {question}
Réponse : {answer}

Format attendu : {{"faithfulness": score, "relevance": score}}""")

    chain = eval_prompt | eval_llm | StrOutputParser()
    result = chain.invoke({"context": context, "question": question, "answer": answer})
    return result