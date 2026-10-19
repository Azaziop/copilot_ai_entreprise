import os
import asyncio
from typing import TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rag import get_rag_chain
from dotenv import load_dotenv

load_dotenv(override=True)

llm = ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),  
    model="deepseek/deepseek-chat",
    temperature=0
)

rag_chain = get_rag_chain()

async def call_mcp_tool(prompt_text: str) -> str:
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"], env=None)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            text_lower = prompt_text.lower()
            
            # Routage vers les différents outils du serveur MCP
            if "statut" in text_lower or "système" in text_lower:
                result = await session.call_tool("get_system_status", arguments={})
                return f"[MCP Réel - Exécuté] {result.content[0].text}"
                
            elif "livraison" in text_lower or "frais" in text_lower:
                result = await session.call_tool("calculate_shipping_cost", arguments={"weight_kg": 10.0, "zone": "EU"})
                return f"[MCP Réel - Exécuté] {result.content[0].text}"
                
            elif "liste" in text_lower or "documents" in text_lower or "fichiers" in text_lower:
                result = await session.call_tool("list_documents_from_db", arguments={})
                return f"[MCP Réel - Exécuté] {result.content[0].text}"
                
            elif "historique" in text_lower or "messages" in text_lower:
                result = await session.call_tool("get_recent_chat_history", arguments={"limit": 5})
                return f"[MCP Réel - Exécuté] {result.content[0].text}"
                
            elif "statistiques" in text_lower or "analytics" in text_lower or "bilan" in text_lower:
                result = await session.call_tool("get_activity_analytics", arguments={})
                return f"[MCP Réel - Exécuté] {result.content[0].text}"
                
            else:
                # Outil par défaut si la question est un outil sans correspondance précise
                result = await session.call_tool("get_system_status", arguments={})
                return f"[MCP Réel - Exécuté par défaut] {result.content[0].text}"

class AgentState(TypedDict):
    question: str
    generation: str
    decision: str

def router_node(state: AgentState):
    question = state['question']
    router_prompt = ChatPromptTemplate.from_template("""Analyse la question de l'utilisateur. 
- Réponds "RAG" si elle demande des documents internes.
- Réponds "TOOL" si elle demande d'interroger le système, de calculer des frais, de lister les documents ou d'obtenir des statistiques (via MCP).
- Réponds "DIRECT" pour le reste.

Question : {question}
Choix (RAG / TOOL / DIRECT) :""")
    
    chain = router_prompt | llm | StrOutputParser()
    decision = chain.invoke({"question": question}).strip().upper()
    
    if "RAG" in decision:
        decision = "RAG"
    elif "TOOL" in decision:
        decision = "TOOL"
    else:
        decision = "DIRECT"
        
    return {"decision": decision}

def rag_node(state: AgentState):
    question = state["question"]
    response = rag_chain.invoke(question)
    return {"generation": response}

def tool_node(state: AgentState):
    question = state["question"]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(call_mcp_tool(question))
    return {"generation": response}

def direct_node(state: AgentState):
    question = state["question"]
    direct_prompt = ChatPromptTemplate.from_template("Tu es un assistant professionnel serviable. Réponds à cette question générale : {question}")
    chain = direct_prompt | llm | StrOutputParser()
    response = chain.invoke({"question": question})
    return {"generation": response}

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("rag_agent", rag_node)
workflow.add_node("tool_agent", tool_node)
workflow.add_node("direct_agent", direct_node)

workflow.add_edge(START, "router")

def decide_next_node(state: AgentState) -> Literal["rag_agent", "tool_agent", "direct_agent"]:
    decision = state["decision"]
    if decision == "RAG":
        return "rag_agent"
    elif decision == "TOOL":
        return "tool_agent"
    return "direct_agent"

workflow.add_conditional_edges(
    "router",
    decide_next_node,
    {
        "rag_agent": "rag_agent",
        "tool_agent": "tool_agent",
        "direct_agent": "direct_agent",
    }
)

workflow.add_edge("rag_agent", END)
workflow.add_edge("tool_agent", END)
workflow.add_edge("direct_agent", END)

app_graph = workflow.compile()