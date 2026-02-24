from app import app
from extensions import db
from models import ChatHistory, ChatSession
from datetime import datetime

with app.app_context():
    # Get all chat history without session_id
    orphan_chats = ChatHistory.query.filter_by(session_id=None).all()
    
    if orphan_chats:
        print(f"Found {len(orphan_chats)} orphan chat messages")
        
        # Group by user_id
        user_chats = {}
        for chat in orphan_chats:
            if chat.user_id not in user_chats:
                user_chats[chat.user_id] = []
            user_chats[chat.user_id].append(chat)
        
        # Create a "Legacy Chat" session for each user
        for user_id, chats in user_chats.items():
            # Create legacy session
            legacy_session = ChatSession(
                user_id=user_id,
                title="Legacy Chat (migrated)",
                created_at=min(c.timestamp for c in chats),
                updated_at=max(c.timestamp for c in chats)
            )
            db.session.add(legacy_session)
            db.session.flush()  # Get the session ID
            
            # Assign all orphan chats to this session
            for chat in chats:
                chat.session_id = legacy_session.id
            
            print(f"✅ Created legacy session {legacy_session.id} for user {user_id} with {len(chats)} messages")
        
        db.session.commit()
        print("✅ Migration complete!")
    else:
        print("No orphan chats found. Nothing to migrate.")