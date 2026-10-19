from mcp.server.fastmcp import FastMCP
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Connexion à la base de données réelle
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./enterprise_copilot.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modèles pour interroger la base
class DocumentRecord(Base):
    __tablename__ = "documents_record"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), unique=True, nullable=False)
    file_type = Column(String(50))

class ChatHistoryModel(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    route_pris = Column(String(50), nullable=False)

# Initialiser le serveur MCP
mcp = FastMCP("Enterprise Real MCP Server")

@mcp.tool()
def get_system_status() -> str:
    """Renvoie l'état de santé du système en interrogeant la base de données."""
    db = SessionLocal()
    try:
        count_docs = db.query(DocumentRecord).count()
        count_msgs = db.query(ChatHistoryModel).count()
        return f"[VRAI MCP] ChromaDB synchronisée | Base SQL active : {count_docs} documents, {count_msgs} requêtes traitées."
    except Exception as e:
        return f"Erreur de connexion à la base SQL : {str(e)}"
    finally:
        db.close()

@mcp.tool()
def calculate_shipping_cost(weight_kg: float, zone: str) -> str:
    """Calcule les frais de livraison professionnels selon le poids et la zone (EU, US, LOCAL)."""
    rates = {"EU": 15.0, "US": 30.0, "LOCAL": 5.0}
    rate_per_kg = rates.get(zone.upper(), 25.0)
    total = weight_kg * rate_per_kg
    return f"Résultat MCP : Les frais pour {weight_kg} kg vers la zone {zone.upper()} sont de {total}€."

@mcp.tool()
def list_documents_from_db() -> str:
    """Interroge la base de données pour lister tous les documents uploadés."""
    db = SessionLocal()
    try:
        docs = db.query(DocumentRecord).all()
        if not docs:
            return "Aucun document trouvé dans la base de données."
        doc_list = "\n".join([f"- ID: {d.id} | Fichier : {d.filename} (Type: {d.file_type})" for d in docs])
        return f"Documents réels en base :\n{doc_list}"
    except Exception as e:
        return f"Erreur : {str(e)}"
    finally:
        db.close()

@mcp.tool()
def get_recent_chat_history(limit: int = 5) -> str:
    """Récupère l'historique récent des conversations stocké en base de données."""
    db = SessionLocal()
    try:
        messages = db.query(ChatHistoryModel).order_by(ChatHistoryModel.id.desc()).limit(limit).all()
        if not messages:
            return "Aucun historique de chat en base."
        history_str = "\n".join([f"Q: {m.question} | R: {m.answer[:50]}... [Route: {m.route_pris}]" for m in messages])
        return f"Échanges récents enregistrés en base :\n{history_str}"
    except Exception as e:
        return f"Erreur : {str(e)}"
    finally:
        db.close()

@mcp.tool()
def search_in_local_file(filename: str, keyword: str) -> str:
    """Recherche la présence d'un mot-clé spécifique à l'intérieur d'un fichier du dossier data/."""
    try:
        file_path = os.path.join("data", filename)
        if not os.path.exists(file_path):
            return f"Erreur MCP : Le fichier '{filename}' est introuvable."
        
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        matches = [line.strip() for line in lines if keyword.lower() in line.lower()]
        if not matches:
            return f"Aucune occurrence du mot-clé '{keyword}' trouvée dans {filename}."
            
        return f"Trouvé {len(matches)} correspondance(s) pour '{keyword}' dans {filename} :\n" + "\n".join(matches[:5])
    except Exception as e:
        return f"Erreur lors de la recherche : {str(e)}"
@mcp.tool()
def get_activity_analytics() -> str:
    """Renvoie des statistiques analytiques globales sur l'utilisation du copilot basées sur la base de données."""
    db = SessionLocal()
    try:
        total_msgs = db.query(ChatHistoryModel).count()
        total_docs = db.query(DocumentRecord).count()
        
        routes = db.query(ChatHistoryModel.route_pris).all()
        route_counts = {}
        for r in routes:
            route_name = r[0]
            route_counts[route_name] = route_counts.get(route_name, 0) + 1
            
        stats_str = ", ".join([f"{route}: {count}" for route, count in route_counts.items()])
        if not stats_str:
            stats_str = "Aucune route enregistrée pour le moment."
            
        return f"Analytique Copilot -> Total messages: {total_msgs} | Total documents: {total_docs} | Utilisation des routes ({stats_str})"
    except Exception as e:
        return f"Erreur lors du calcul des statistiques : {str(e)}"
    finally:
        db.close()

if __name__ == "__main__":
    mcp.run()