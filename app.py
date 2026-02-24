import os
import hashlib  # ✅ BUG #11 FIX: Added for file hashing
import mimetypes  # ✅ BUG #15 FIX: For MIME type validation
from werkzeug.utils import secure_filename  # ✅ BUG #15 FIX: For filename sanitization
from flask import Flask, render_template, request, jsonify, session
from flask_login import login_required, current_user
from config import Config
from extensions import db, login_manager, migrate, limiter, csrf  # ✅ BUG #12 & #14 FIX
from models import User, ChatHistory, ChatSession, AdminActivityLog, UnansweredQuery
from auth import register_auth_routes
from admin_routes import register_admin_routes  # NEW: Import admin routes
from feedback_routes import register_feedback_routes  # PHASE 3A: Import feedback routes
from src.data_loader import load_documents
from src.embeddings import EmbeddingPipeline
from src.pg_vectorstore import PostgresVectorStore
from src.rag_chain import RAGChatbot
from datetime import datetime
from sqlalchemy import text

app = Flask(__name__)
app.config.from_object(Config)

# ✅ BUG #14 FIX: Accept CSRF token from X-CSRFToken header (for fetch/AJAX requests)
app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken', 'X-CSRF-Token']

# ✅ BUG #15 FIX: Upload validation constants
MAX_FILE_SIZE    = 50  * 1024 * 1024   # 50MB per file
MAX_TOTAL_SIZE   = 200 * 1024 * 1024   # 200MB total per batch
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'xlsx'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/octet-stream'  # fallback for some systems
}

def allowed_extension(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file(f):
    """
    ✅ BUG #15 FIX: Comprehensive file validation
    Returns: (is_valid: bool, error_message: str)
    """
    filename = f.filename

    # 1. Check filename exists
    if not filename:
        return False, "No filename provided"

    # 2. Sanitize filename - check for path traversal
    safe_name = secure_filename(filename)
    if not safe_name:
        return False, f"Invalid filename: {filename}"

    # 3. Check file extension
    if not allowed_extension(filename):
        ext = filename.rsplit('.', 1)[-1].upper() if '.' in filename else 'UNKNOWN'
        return False, f"File type .{ext} not allowed. Allowed: PDF, DOCX, TXT, XLSX"

    # 4. Check file size
    f.seek(0, 2)  # Seek to end
    file_size = f.tell()
    f.seek(0)     # Reset pointer

    if file_size == 0:
        return False, f"File '{filename}' is empty"

    if file_size > MAX_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        return False, f"File '{filename}' is {size_mb:.1f}MB - exceeds 50MB limit"

    # 5. Check MIME type
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False, f"File '{filename}' has invalid MIME type: {mime_type}"

    # 6. Validate file content (magic bytes check)
    header = f.read(8)
    f.seek(0)

    ext = filename.rsplit('.', 1)[1].lower()

    # PDF magic bytes: %PDF
    if ext == 'pdf' and not header.startswith(b'%PDF'):
        return False, f"File '{filename}' is not a valid PDF (content mismatch)"

    # DOCX/XLSX magic bytes: PK (ZIP format)
    if ext in ('docx', 'xlsx') and not header.startswith(b'PK'):
        return False, f"File '{filename}' is not a valid {ext.upper()} (content mismatch)"

    return True, ""


db.init_app(app)
login_manager.init_app(app)
migrate.init_app(app, db)

# ✅ BUG #12 FIX: Initialize rate limiter
limiter.init_app(app)

# ✅ BUG #14 FIX: Initialize CSRF protection
csrf.init_app(app)

# ✅ BUG #14 FIX: CSRF exemptions moved to end of file (after route definitions)

# Register routes
register_auth_routes(app)
register_admin_routes(app)  # NEW: Register admin routes
register_feedback_routes(app)  # PHASE 3A: Register feedback routes

# Store chatbot instances per session
chatbot_instances = {}

# ✅ BUG #11 FIX: File hash calculation function
def calculate_file_hash(file):
    """
    Calculate SHA-256 hash of uploaded file for deduplication
    Returns: hex string of file hash
    """
    sha256 = hashlib.sha256()
    
    # Read file in chunks to handle large files
    file.seek(0)  # Reset file pointer to beginning
    while chunk := file.read(8192):
        sha256.update(chunk)
    
    file.seek(0)  # Reset for later use
    return sha256.hexdigest()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/")
@login_required
def home():
    """Enhanced chat interface with user info"""
    return render_template("chat.html")

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    """Upload and process documents - Admin only with deduplication"""
    # Check if user is admin
    if not current_user.is_admin():
        return jsonify({
            "status": "error", 
            "message": "Only administrators can upload documents. Please contact admin@starcement.co.in"
        }), 403
    
    try:
        # Get department from form or use current user's department
        dept = request.form.get("department", current_user.department.strip().lower())
        upload_path = os.path.join("uploads", dept)
        os.makedirs(upload_path, exist_ok=True)
        
        files = request.files.getlist("files")
        if not files or files[0].filename == '':
            return jsonify({"status": "error", "message": "No files selected"}), 400

        # ✅ BUG #15 FIX: Check total batch size
        total_size = 0
        for f in files:
            if f.filename:
                f.seek(0, 2)
                total_size += f.tell()
                f.seek(0)

        if total_size > MAX_TOTAL_SIZE:
            total_mb = total_size / (1024 * 1024)
            return jsonify({
                "status": "error",
                "message": f"Total upload size {total_mb:.1f}MB exceeds 200MB batch limit"
            }), 400

        # ✅ BUG #15 FIX: Validate each file before processing
        validation_errors = []
        for f in files:
            if f.filename:
                is_valid, error_msg = validate_file(f)
                if not is_valid:
                    validation_errors.append(error_msg)

        if validation_errors:
            print(f"❌ Validation failed: {validation_errors}")
            return jsonify({
                "status": "error",
                "message": "File validation failed",
                "errors": validation_errors
            }), 400

        # Get access control parameters from request
        access_level = request.form.get("access_level", "public")
        is_cross_dept = request.form.get("is_cross_dept", "false").lower() == "true"
        
        print(f"📁 Processing {len(files)} file(s) for department: {dept}")
        print(f"🔒 Access level: {access_level}, Cross-dept: {is_cross_dept}")
        
        # ✅ BUG #11 FIX: Check for duplicate files before processing
        saved_files = []
        skipped_files = []
        file_hashes = {}
        
        for f in files:
            if not f.filename:
                continue
            
            # ✅ BUG #15 FIX: Use sanitized filename
            safe_filename = secure_filename(f.filename)
            print(f"🔒 Sanitized filename: {f.filename} → {safe_filename}")
            
            # Calculate file hash
            print(f"🔍 Calculating hash for: {f.filename}")
            file_hash = calculate_file_hash(f)
            print(f"   Hash: {file_hash[:16]}...")
            
            # Check if this file already exists in database
            existing = db.session.execute(
                text("""
                    SELECT file_name, department, created_at
                    FROM document_embeddings 
                    WHERE file_hash = :hash 
                    LIMIT 1
                """),
                {"hash": file_hash}
            ).fetchone()
            
            if existing:
                print(f"⚠️ DUPLICATE DETECTED: {f.filename}")
                print(f"   Already exists as: {existing.file_name} in {existing.department}")
                print(f"   Uploaded on: {existing.created_at}")
                skipped_files.append({
                    'filename': f.filename,
                    'reason': f'Already exists as "{existing.file_name}" in {existing.department} department',
                    'uploaded_date': str(existing.created_at)
                })
                continue
            
            # File is unique, save it
            file_path = os.path.join(upload_path, safe_filename)
            f.save(file_path)
            saved_files.append(safe_filename)
            file_hashes[safe_filename] = file_hash
            print(f"✅ Saved: {safe_filename}")
        
        # If all files were duplicates
        if not saved_files:
            print(f"❌ All {len(files)} file(s) were duplicates")
            return jsonify({
                "status": "warning",
                "message": f"All {len(files)} file(s) were duplicates and have been skipped",
                "skipped_files": skipped_files
            }), 409
        
        # Load and process documents
        print(f"📖 Loading {len(saved_files)} unique document(s) from: {upload_path}")
        docs = load_documents(upload_path)
        
        if not docs:
            return jsonify({"status": "error", "message": "No valid documents found"}), 400
        
        print(f"📄 Loaded {len(docs)} document pages")
        
        # Generate embeddings
        print(f"🔢 Generating embeddings...")
        embedding_pipeline = EmbeddingPipeline()
        chunks, vectors = embedding_pipeline.process(docs)
        
        print(f"✂️ Created {len(chunks)} chunks")
        
        # ✅ BUG #11 FIX: Determine file hash for this batch
        # If single file, use its hash; if multiple, use combined hash
        if len(saved_files) == 1:
            batch_file_hash = file_hashes[saved_files[0]]
        else:
            # For multiple files, create a combined hash
            combined = ''.join(sorted(file_hashes.values()))
            batch_file_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        print(f"📦 Batch hash: {batch_file_hash[:16]}...")
        
        # Store in PostgreSQL vector store
        store = PostgresVectorStore(dept, current_user)
        inserted_count = store.build(
            vectors, 
            chunks,
            access_level=access_level,
            is_cross_dept=is_cross_dept,
            source_type='primary',
            uploaded_by=current_user.id,
            file_name=", ".join(saved_files) if saved_files else None,
            file_type=saved_files[0].split('.')[-1] if saved_files else None,
            file_hash=batch_file_hash  # ✅ BUG #11 FIX: Pass file hash
        )
        
        # ✅ BUG #10 FIX: Analyze table after bulk insert
        try:
            db.session.execute(text("ANALYZE document_embeddings"))
            print("✅ Table statistics updated (ANALYZE)")
        except Exception as e:
            print(f"⚠️ ANALYZE failed (non-critical): {e}")
        
        # Log admin activity
        log = AdminActivityLog(
            admin_id=current_user.id,
            action_type='upload',
            target_type='document',
            description=f"Uploaded {len(saved_files)} file(s) to {dept} department" + 
                       (f" ({len(skipped_files)} duplicate(s) skipped)" if skipped_files else ""),
            meta_data={
                'files_uploaded': saved_files,
                'files_skipped': len(skipped_files),
                'skipped_details': skipped_files,
                'chunks_created': len(chunks),
                'vectors_stored': inserted_count,
                'access_level': access_level,
                'is_cross_dept': is_cross_dept,
                'file_hash': batch_file_hash
            }
        )
        db.session.add(log)
        db.session.commit()
        
        # Clear chatbot instances for this department to force reload
        keys_to_delete = [k for k in chatbot_instances.keys() if k.startswith(f"{current_user.id}_")]
        for key in keys_to_delete:
            del chatbot_instances[key]
        
        print(f"✅ Upload complete: {len(saved_files)} uploaded, {len(skipped_files)} skipped")
        
        # Prepare response
        response_data = {
            "status": "success",
            "message": f"Successfully processed {len(saved_files)} file(s), created {inserted_count} vectors",
            "files_uploaded": saved_files,
            "chunks_created": len(chunks),
            "vectors_stored": inserted_count
        }
        
        # Include skipped files info if any
        if skipped_files:
            response_data['skipped_files'] = skipped_files
            response_data['warning'] = f"{len(skipped_files)} duplicate file(s) were skipped"
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error", 
            "message": f"Upload failed: {str(e)}"
        }), 500

@app.route("/chat", methods=["POST"])
@limiter.limit("30 per minute")  # ✅ BUG #12 FIX: Rate limit chat endpoint
@login_required
def chat():
    """Handle chat requests"""
    try:
        question = request.json.get("message")
        chat_session_id = request.json.get("session_id")
        
        if not question:
            return jsonify({"reply": "Please provide a message"}), 400
        
        dept = current_user.department.strip().lower()
        
        # Check if department has vectors in PostgreSQL
        result = db.session.execute(
            text("""
                SELECT COUNT(*) 
                FROM document_embeddings 
                WHERE (department = :dept OR is_cross_dept = true)
                  AND source_type = 'primary'
            """),
            {"dept": dept}
        ).scalar()
        
        if result == 0:
            return jsonify({
                "reply": "⚠️ No documents found for your department. Please contact your administrator at admin@starcement.co.in to upload department documents first."
            }), 200
        
        # Create new session if none provided
        if not chat_session_id:
            chat_session = ChatSession(
                user_id=current_user.id,
                title=question[:50] + "..." if len(question) > 50 else question
            )
            db.session.add(chat_session)
            db.session.commit()
            chat_session_id = chat_session.id
        
        # Get or create chatbot instance for this session
        bot_key = f"{current_user.id}_{chat_session_id}"
        
        if bot_key not in chatbot_instances:
            # Use PostgreSQL vector store with user access control
            store = PostgresVectorStore(dept, current_user)
            chatbot_instances[bot_key] = RAGChatbot(store)
            
            # Load previous conversation history for this session
            previous_chats = ChatHistory.query.filter_by(
                session_id=chat_session_id
            ).order_by(ChatHistory.timestamp).all()
            
            for prev_chat in previous_chats:
                chatbot_instances[bot_key].conversation_history.append(
                    (prev_chat.question, prev_chat.answer)
                )
        
        bot = chatbot_instances[bot_key]
        answer = bot.ask(question)
        
        # Check if this is an "unanswered" response
        if "admin@starcement.co.in" in answer or "cannot find" in answer.lower():
            # Log as unanswered query
            unanswered = UnansweredQuery(
                user_id=current_user.id,
                question=question,
                department=dept,
                access_level=current_user.access_level
            )
            db.session.add(unanswered)
        
        # Save to database
        chat_history = ChatHistory(
            session_id=chat_session_id,
            user_id=current_user.id,
            question=question,
            answer=answer
        )
        db.session.add(chat_history)
        
        # Update session timestamp
        chat_session = db.session.get(ChatSession, chat_session_id)
        if chat_session:
            chat_session.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            "reply": answer,
            "session_id": chat_session_id,
            "chat_id": chat_history.id  # PHASE 3A: Return chat_id for feedback
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Chat error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "reply": f"⚠️ An error occurred while processing your request. Please try again or contact support."
        }), 500

@app.route("/sessions", methods=["GET"])
@login_required
def get_sessions():
    """Get all chat sessions for current user"""
    try:
        sessions = ChatSession.query.filter_by(
            user_id=current_user.id
        ).order_by(ChatSession.updated_at.desc()).all()
        
        return jsonify([{
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat()
        } for s in sessions])
    except Exception as e:
        print(f"❌ Error fetching sessions: {str(e)}")
        return jsonify([]), 500

@app.route("/session/<int:session_id>", methods=["GET"])
@login_required
def get_session(session_id):
    """Get all messages from a specific session"""
    try:
        session_obj = db.session.get(ChatSession, session_id)
        
        if not session_obj or session_obj.user_id != current_user.id:
            return jsonify({"error": "Session not found"}), 404
        
        messages = ChatHistory.query.filter_by(
            session_id=session_id
        ).order_by(ChatHistory.timestamp).all()
        
        return jsonify({
            "session": {
                "id": session_obj.id,
                "title": session_obj.title
            },
            "messages": [{
                "id": m.id,  # PHASE 3A: Include message id for feedback
                "question": m.question,
                "answer": m.answer,
                "timestamp": m.timestamp.isoformat()
            } for m in messages]
        })
    except Exception as e:
        print(f"❌ Error fetching session: {str(e)}")
        return jsonify({"error": "Failed to load session"}), 500

@app.route("/session/<int:session_id>", methods=["DELETE"])
@login_required
def delete_session(session_id):
    """Delete a chat session"""
    try:
        session_obj = db.session.get(ChatSession, session_id)
        
        if not session_obj or session_obj.user_id != current_user.id:
            return jsonify({"error": "Session not found"}), 404
        
        # Delete all messages in this session
        ChatHistory.query.filter_by(session_id=session_id).delete()
        
        # Delete the session
        db.session.delete(session_obj)
        db.session.commit()
        
        # Clear from memory
        bot_key = f"{current_user.id}_{session_id}"
        if bot_key in chatbot_instances:
            del chatbot_instances[bot_key]
        
        return jsonify({"status": "Session deleted successfully"})
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting session: {str(e)}")
        return jsonify({"error": "Failed to delete session"}), 500

@app.route("/session/<int:session_id>/rename", methods=["POST"])
@login_required
def rename_session(session_id):
    """Rename a chat session"""
    try:
        session_obj = db.session.get(ChatSession, session_id)
        
        if not session_obj or session_obj.user_id != current_user.id:
            return jsonify({"error": "Session not found"}), 404
        
        new_title = request.json.get("title")
        if new_title:
            session_obj.title = new_title
            db.session.commit()
            return jsonify({"status": "Session renamed successfully"})
        
        return jsonify({"error": "No title provided"}), 400
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error renaming session: {str(e)}")
        return jsonify({"error": "Failed to rename session"}), 500


# ✅ BUG #12 FIX: Rate limit error handler
@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors"""
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please wait a moment before trying again.",
        "retry_after": str(e.description)
    }), 429

# ✅ BUG #14 FIX: Exempt JSON API endpoints from CSRF
# (These use session-based auth, not HTML form submissions)
csrf.exempt(chat)
csrf.exempt(get_sessions)
csrf.exempt(get_session)
csrf.exempt(delete_session)
csrf.exempt(rename_session)

if __name__ == "__main__":
    app.run(debug=True)