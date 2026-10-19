import os
from dotenv import load_dotenv
from database import init_db, SessionLocal, User, ChatSession, ChatHistoryModel, DocumentRecord

load_dotenv(override=True)

# 1. S'assurer que les tables sont créées
init_db()

# 2. Ouvrir une session de base de données
db = SessionLocal()

try:
    print("Insertion des données initiales (Seed)...")

    # --- 1. Créer un utilisateur par défaut ---
    default_user = db.query(User).filter_by(username="admin_anass").first()
    if not default_user:
        default_user = User(username="admin_anass", role="Admin")
        db.add(default_user)
        db.commit()
        db.refresh(default_user)
        print(f"Utilisateur créé : {default_user.username} (ID: {default_user.id})")
    else:
        print(f"Utilisateur existant : {default_user.username}")

    # --- 2. Créer une session de chat pour cet utilisateur ---
    default_session = db.query(ChatSession).filter_by(user_id=default_user.id).first()
    if not default_session:
        default_session = ChatSession(title="Session Initiale Enterprise", user_id=default_user.id)
        db.add(default_session)
        db.commit()
        db.refresh(default_session)
        print(f"Session de chat créée (ID: {default_session.id})")
    else:
        print(f"Session de chat existante (ID: {default_session.id})")

    # --- 3. Insérer un message d'historique de test ---
    existing_message = db.query(ChatHistoryModel).filter_by(session_id=default_session.id).first()
    if not existing_message:
        test_message = ChatHistoryModel(
            session_id=default_session.id,
            question="Quel est le statut du système ?",
            answer="[MCP Réel - Exécuté] ChromaDB est synchronisée, PostgreSQL/SQLite est actif, aucun incident critique.",
            route_pris="TOOL"
        )
        db.add(test_message)
        db.commit()
        print("Message d'historique de test inséré avec succès.")

    # --- 4. Insérer un document de test dans les métadonnées ---
    existing_doc = db.query(DocumentRecord).filter_by(filename="info.txt").first()
    if not existing_doc:
        test_doc = DocumentRecord(filename="info.txt", file_type="txt")
        db.add(test_doc)
        db.commit()
        print("Document de test 'info.txt' enregistré en base.")
    else:
        print("Document de test 'info.txt' déjà présent.")

    print("Seed exécuté avec succès ! Ta base de données est prête.")

except Exception as e:
    db.rollback()
    print(f"Erreur lors de l'insertion des données seed : {e}")
finally:
    db.close()