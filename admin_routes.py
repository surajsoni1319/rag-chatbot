"""
Admin Routes for Star Cement AI Chatbot
Handles all admin panel functionality
"""

from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from models import User, ChatHistory, ChatSession, AdminActivityLog, UnansweredQuery
from sqlalchemy import text, func
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from auth import validate_password  # ✅ BUG #13 FIX: Import password validator
# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def register_admin_routes(app):
    
    @app.route("/admin")
    @login_required
    @admin_required
    def admin_dashboard():
        """Admin dashboard with stats"""
        
        # Get stats
        total_docs_result = db.session.execute(text(
            "SELECT COUNT(DISTINCT file_name) FROM document_embeddings"
        )).scalar()
        
        total_users = User.query.count()
        total_chats = ChatHistory.query.count()
        
        # Unanswered queries
        unanswered = UnansweredQuery.query.filter_by(resolved=False).count()
        
        # Chats today
        today = datetime.utcnow().date()
        chats_today = ChatHistory.query.filter(
            func.date(ChatHistory.timestamp) == today
        ).count()
        
        # Active users today
        active_today = db.session.query(func.count(func.distinct(ChatHistory.user_id))).filter(
            func.date(ChatHistory.timestamp) == today
        ).scalar()
        
        # New docs this month
        first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        new_docs = db.session.execute(text(
            "SELECT COUNT(DISTINCT file_name) FROM document_embeddings WHERE created_at >= :date"
        ), {"date": first_of_month}).scalar()
        
        stats = {
            'total_documents': total_docs_result or 0,
            'total_users': total_users,
            'total_chats': total_chats,
            'unanswered_queries': unanswered,
            'chats_today': chats_today,
            'active_today': active_today or 0,
            'new_docs_this_month': new_docs or 0
        }
        
        # Department breakdown
        dept_stats = db.session.execute(text("""
            SELECT 
                department,
                COUNT(DISTINCT file_name) as doc_count,
                COUNT(*) as total_chunks
            FROM document_embeddings 
            GROUP BY department
        """)).fetchall()
        
        departments = []
        for dept in dept_stats:
            user_count = User.query.filter_by(department=dept.department).count()
            query_count = db.session.execute(text("""
                SELECT COUNT(*) FROM chat_history ch
                JOIN "user" u ON ch.user_id = u.id
                WHERE u.department = :dept
            """), {"dept": dept.department}).scalar()
            
            departments.append({
                'name': dept.department,
                'doc_count': dept.doc_count,
                'user_count': user_count,
                'query_count': query_count or 0
            })
        
        # Recent activities
        recent_logs = AdminActivityLog.query.order_by(
            AdminActivityLog.created_at.desc()
        ).limit(10).all()
        
        recent_activities = []
        for log in recent_logs:
            time_diff = datetime.utcnow() - log.created_at
            if time_diff.days > 0:
                timestamp = f"{time_diff.days}d ago"
            elif time_diff.seconds >= 3600:
                timestamp = f"{time_diff.seconds // 3600}h ago"
            elif time_diff.seconds >= 60:
                timestamp = f"{time_diff.seconds // 60}m ago"
            else:
                timestamp = "Just now"
            
            recent_activities.append({
                'type': log.action_type,
                'description': log.description,
                'timestamp': timestamp
            })
        
        return render_template('admin_dashboard.html',
                             stats=stats,
                             departments=departments,
                             recent_activities=recent_activities)
    
    @app.route("/admin/documents")
    @login_required
    @admin_required
    def admin_documents():
        """Document management page"""
        
        # Get all documents with details
        docs_result = db.session.execute(text("""
            SELECT 
                file_name,
                department,
                access_level,
                file_type,
                is_cross_dept,
                uploaded_by,
                MIN(created_at) as created_at,
                COUNT(*) as chunk_count,
                MIN(id) as id
            FROM document_embeddings
            WHERE file_name IS NOT NULL
            GROUP BY file_name, department, access_level, file_type, is_cross_dept, uploaded_by
            ORDER BY created_at DESC
        """)).fetchall()
        
        documents = []
        for doc in docs_result:
            uploader = User.query.get(doc.uploaded_by) if doc.uploaded_by else None
            documents.append({
                'id': doc.id,
                'file_name': doc.file_name,
                'department': doc.department,
                'access_level': doc.access_level,
                'file_type': doc.file_type,
                'is_cross_dept': doc.is_cross_dept,
                'chunk_count': doc.chunk_count,
                'created_at': doc.created_at,
                'uploaded_by_name': uploader.name or uploader.email if uploader else 'Unknown'
            })
        
        departments = db.session.execute(text(
            "SELECT DISTINCT department FROM document_embeddings ORDER BY department"
        )).fetchall()
        
        return render_template('admin_documents.html',
                             documents=documents,
                             departments=[d[0] for d in departments])
    
    @app.route("/admin/documents/<int:doc_id>/delete", methods=['POST'])
    @login_required
    @admin_required
    def delete_document(doc_id):
        """Delete a document and all its chunks"""
        try:
            # Get document info
            doc_info = db.session.execute(text(
                "SELECT file_name, department FROM document_embeddings WHERE id = :id"
            ), {"id": doc_id}).fetchone()
            
            if not doc_info:
                return jsonify({"status": "error", "message": "Document not found"}), 404
            
            # Delete all chunks of this document
            db.session.execute(text(
                "DELETE FROM document_embeddings WHERE file_name = :fname AND department = :dept"
            ), {"fname": doc_info.file_name, "dept": doc_info.department})
            
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='delete',
                target_type='document',
                description=f"Deleted document: {doc_info.file_name} from {doc_info.department}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "Document deleted"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/upload")
    @login_required
    @admin_required
    def admin_upload():
        """Document upload page"""
        return render_template('admin_upload.html')
    
    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        """User management page"""
        users = User.query.all()
        
        departments = db.session.execute(text(
            "SELECT DISTINCT department FROM \"user\" ORDER BY department"
        )).fetchall()
        
        return render_template('admin_users.html',
                             users=users,
                             departments=[d[0] for d in departments])
    
    @app.route("/admin/users/<int:user_id>")
    @login_required
    @admin_required
    def get_user(user_id):
        """Get user details for editing"""
        user = User.query.get_or_404(user_id)
        return jsonify({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'department': user.department,
            'role': user.role,
            'access_level': user.access_level
        })
    
    @app.route("/admin/users/add", methods=['POST'])
    @login_required
    @admin_required
    def add_user():
        """Add new user"""
        try:
            data = request.json
            
            # Check if email already exists
            if User.query.filter_by(email=data['email']).first():
                return jsonify({"status": "error", "message": "Email already exists"}), 400
            
            user = User(
                name=data.get('name'),
                email=data['email'],
                password=generate_password_hash(data['password']),
                department=data['department'],
                role=data['role'],
                access_level=data['access_level']
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='user',
                target_type='create',
                description=f"Created new user: {data['email']}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User created"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/users/<int:user_id>/edit", methods=['POST'])
    @login_required
    @admin_required
    def edit_user(user_id):
        """Edit existing user"""
        try:
            user = User.query.get_or_404(user_id)
            data = request.json
            
            user.name = data.get('name')
            user.email = data['email']
            user.department = data['department']
            user.role = data['role']
            user.access_level = data['access_level']
            
            if data.get('password'):
                user.password = generate_password_hash(data['password'])
            
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='user',
                target_type='edit',
                description=f"Updated user: {data['email']}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User updated"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/users/<int:user_id>/delete", methods=['POST'])
    @login_required
    @admin_required
    def delete_user(user_id):
        """Delete user"""
        try:
            if user_id == current_user.id:
                return jsonify({"status": "error", "message": "Cannot delete yourself"}), 400
            
            user = User.query.get_or_404(user_id)
            email = user.email
            
            db.session.delete(user)
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='user',
                target_type='delete',
                description=f"Deleted user: {email}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User deleted"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/queries")
    @login_required
    @admin_required
    def admin_queries():
        """Unanswered queries page"""
        queries = UnansweredQuery.query.filter_by(resolved=False).order_by(
            UnansweredQuery.created_at.desc()
        ).all()
        
        query_list = []
        for q in queries:
            user = User.query.get(q.user_id)
            query_list.append({
                'id': q.id,
                'question': q.question,
                'user_email': user.email if user else 'Unknown',
                'department': q.department,
                'access_level': q.access_level,
                'created_at': q.created_at
            })
        
        return render_template('admin_queries.html', queries=query_list)
    
    @app.route("/admin/queries/<int:query_id>/resolve", methods=['POST'])
    @login_required
    @admin_required
    def resolve_query(query_id):
        """Mark query as resolved"""
        try:
            query = UnansweredQuery.query.get_or_404(query_id)
            query.resolved = True
            query.resolved_at = datetime.utcnow()
            query.resolved_by = current_user.id
            query.resolution_notes = request.json.get('notes', '')
            
            db.session.commit()
            
            return jsonify({"status": "success", "message": "Query resolved"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/feedback")
    @login_required
    @admin_required
    def admin_feedback():
        """User feedback page (placeholder for Phase 3)"""
        return render_template('admin_feedback.html')




#######################################################



"""
Admin Routes for Star Cement AI Chatbot
Handles all admin panel functionality
"""

from flask import render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from models import User, ChatHistory, ChatSession, AdminActivityLog, UnansweredQuery
from sqlalchemy import text, func
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from auth import validate_password  # ✅ BUG #13 FIX: Import password validator

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def register_admin_routes(app):
    
    @app.route("/admin")
    @login_required
    @admin_required
    def admin_dashboard():
        """Admin dashboard with stats"""
        
        # Get stats
        total_docs_result = db.session.execute(text(
            "SELECT COUNT(DISTINCT file_name) FROM document_embeddings"
        )).scalar()
        
        total_users = User.query.count()
        total_chats = ChatHistory.query.count()
        
        # Unanswered queries
        unanswered = UnansweredQuery.query.filter_by(resolved=False).count()
        
        # Chats today
        today = datetime.utcnow().date()
        chats_today = ChatHistory.query.filter(
            func.date(ChatHistory.timestamp) == today
        ).count()
        
        # Active users today
        active_today = db.session.query(func.count(func.distinct(ChatHistory.user_id))).filter(
            func.date(ChatHistory.timestamp) == today
        ).scalar()
        
        # New docs this month
        first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        new_docs = db.session.execute(text(
            "SELECT COUNT(DISTINCT file_name) FROM document_embeddings WHERE created_at >= :date"
        ), {"date": first_of_month}).scalar()
        
        stats = {
            'total_documents': total_docs_result or 0,
            'total_users': total_users,
            'total_chats': total_chats,
            'unanswered_queries': unanswered,
            'chats_today': chats_today,
            'active_today': active_today or 0,
            'new_docs_this_month': new_docs or 0
        }
        
        # Department breakdown
        dept_stats = db.session.execute(text("""
            SELECT 
                department,
                COUNT(DISTINCT file_name) as doc_count,
                COUNT(*) as total_chunks
            FROM document_embeddings 
            GROUP BY department
        """)).fetchall()
        
        departments = []
        for dept in dept_stats:
            user_count = User.query.filter_by(department=dept.department).count()
            query_count = db.session.execute(text("""
                SELECT COUNT(*) FROM chat_history ch
                JOIN "user" u ON ch.user_id = u.id
                WHERE u.department = :dept
            """), {"dept": dept.department}).scalar()
            
            departments.append({
                'name': dept.department,
                'doc_count': dept.doc_count,
                'user_count': user_count,
                'query_count': query_count or 0
            })
        
        # Recent activities
        recent_logs = AdminActivityLog.query.order_by(
            AdminActivityLog.created_at.desc()
        ).limit(10).all()
        
        recent_activities = []
        for log in recent_logs:
            time_diff = datetime.utcnow() - log.created_at
            if time_diff.days > 0:
                timestamp = f"{time_diff.days}d ago"
            elif time_diff.seconds >= 3600:
                timestamp = f"{time_diff.seconds // 3600}h ago"
            elif time_diff.seconds >= 60:
                timestamp = f"{time_diff.seconds // 60}m ago"
            else:
                timestamp = "Just now"
            
            recent_activities.append({
                'type': log.action_type,
                'description': log.description,
                'timestamp': timestamp
            })
        
        return render_template('admin_dashboard.html',
                             stats=stats,
                             departments=departments,
                             recent_activities=recent_activities)
    
    @app.route("/admin/documents")
    @login_required
    @admin_required
    def admin_documents():
        """Document management page"""
        
        # Get all documents with details
        docs_result = db.session.execute(text("""
            SELECT 
                file_name,
                department,
                access_level,
                file_type,
                is_cross_dept,
                uploaded_by,
                MIN(created_at) as created_at,
                COUNT(*) as chunk_count,
                MIN(id) as id
            FROM document_embeddings
            WHERE file_name IS NOT NULL AND source_type = 'primary'  -- ✅ PRIMARY KB ONLY
            GROUP BY file_name, department, access_level, file_type, is_cross_dept, uploaded_by
            ORDER BY created_at DESC
        """)).fetchall()
        
        documents = []
        for doc in docs_result:
            uploader = User.query.get(doc.uploaded_by) if doc.uploaded_by else None
            documents.append({
                'id': doc.id,
                'file_name': doc.file_name,
                'department': doc.department,
                'access_level': doc.access_level,
                'file_type': doc.file_type,
                'is_cross_dept': doc.is_cross_dept,
                'chunk_count': doc.chunk_count,
                'created_at': doc.created_at,
                'uploaded_by_name': uploader.name or uploader.email if uploader else 'Unknown'
            })
        
        departments = db.session.execute(text(
            "SELECT DISTINCT department FROM document_embeddings ORDER BY department"
        )).fetchall()
        
        return render_template('admin_documents.html',
                             documents=documents,
                             departments=[d[0] for d in departments])
    
    
    @app.route("/admin/knowledge-base")
    @login_required
    @admin_required
    def admin_knowledge_base():
        """Secondary Knowledge Base (from approved feedback)"""
        
        # Get all SECONDARY documents with details
        docs_result = db.session.execute(text("""
            SELECT 
                file_name,
                department,
                access_level,
                file_type,
                is_cross_dept,
                uploaded_by,
                MIN(created_at) as created_at,
                COUNT(*) as chunk_count,
                MIN(id) as id
            FROM document_embeddings
            WHERE file_name IS NOT NULL AND source_type = 'secondary'  -- ✅ SECONDARY KB ONLY
            GROUP BY file_name, department, access_level, file_type, is_cross_dept, uploaded_by
            ORDER BY created_at DESC
        """)).fetchall()
        
        documents = []
        for doc in docs_result:
            uploader = User.query.get(doc.uploaded_by) if doc.uploaded_by else None
            documents.append({
                'id': doc.id,
                'file_name': doc.file_name,
                'department': doc.department,
                'access_level': doc.access_level,
                'file_type': doc.file_type,
                'is_cross_dept': doc.is_cross_dept,
                'chunk_count': doc.chunk_count,
                'created_at': doc.created_at,
                'uploaded_by_name': uploader.name or uploader.email if uploader else 'Unknown'
            })
        
        departments = db.session.execute(text(
            "SELECT DISTINCT department FROM document_embeddings WHERE source_type = 'secondary' ORDER BY department"
        )).fetchall()
        
        return render_template('admin_knowledge_base.html',
                             documents=documents,
                             departments=[d[0] for d in departments])

    
    @app.route("/admin/documents/<int:doc_id>/view")
    @login_required
    @admin_required
    def view_document(doc_id):
        """View document chunks and details"""
        
        # Get the document details
        doc = db.session.execute(text("""
            SELECT 
                file_name,
                department,
                access_level,
                file_type,
                is_cross_dept,
                uploaded_by,
                created_at,
                file_hash
            FROM document_embeddings
            WHERE id = :id
            LIMIT 1
        """), {"id": doc_id}).fetchone()
        
        if not doc:
            return "Document not found", 404
        
        # Get all chunks for this document
        chunks = db.session.execute(text("""
            SELECT 
                id,
                content,
                metadata,
                created_at
            FROM document_embeddings
            WHERE file_name = :fname 
              AND department = :dept
            ORDER BY id
        """), {
            "fname": doc.file_name,
            "dept": doc.department
        }).fetchall()
        
        # Get uploader info
        uploader = User.query.get(doc.uploaded_by) if doc.uploaded_by else None
        
        document_info = {
            'id': doc_id,
            'file_name': doc.file_name,
            'department': doc.department,
            'access_level': doc.access_level,
            'file_type': doc.file_type,
            'is_cross_dept': doc.is_cross_dept,
            'created_at': doc.created_at,
            'file_hash': doc.file_hash[:16] + '...' if doc.file_hash else 'N/A',
            'uploaded_by_name': uploader.name or uploader.email if uploader else 'Unknown',
            'chunk_count': len(chunks)
        }
        
        # Prepare chunks data
        chunks_data = []
        for i, chunk in enumerate(chunks, 1):
            try:
                import json
                metadata = json.loads(chunk.metadata) if chunk.metadata else {}
            except:
                metadata = {}
            
            chunks_data.append({
                'number': i,
                'id': chunk.id,
                'content': chunk.content,
                'metadata': metadata,
                'created_at': chunk.created_at
            })
        
        return render_template('view_document.html',
                             document=document_info,
                             chunks=chunks_data)

    @app.route("/admin/documents/<int:doc_id>/delete", methods=['POST'])
    @login_required
    @admin_required
    def delete_document(doc_id):
        """Delete a document and all its chunks"""
        try:
            # Get document info
            doc_info = db.session.execute(text(
                "SELECT file_name, department FROM document_embeddings WHERE id = :id"
            ), {"id": doc_id}).fetchone()
            
            if not doc_info:
                return jsonify({"status": "error", "message": "Document not found"}), 404
            
            # Delete all chunks of this document
            db.session.execute(text(
                "DELETE FROM document_embeddings WHERE file_name = :fname AND department = :dept"
            ), {"fname": doc_info.file_name, "dept": doc_info.department})
            
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='delete',
                target_type='document',
                description=f"Deleted document: {doc_info.file_name} from {doc_info.department}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "Document deleted"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/upload")
    @login_required
    @admin_required
    def admin_upload():
        """Document upload page"""
        return render_template('admin_upload.html')
    
    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        """User management page"""
        users = User.query.all()
        
        departments = db.session.execute(text(
            "SELECT DISTINCT department FROM \"user\" ORDER BY department"
        )).fetchall()
        
        return render_template('admin_users.html',
                             users=users,
                             departments=[d[0] for d in departments])
    
    @app.route("/admin/users/<int:user_id>")
    @login_required
    @admin_required
    def get_user(user_id):
        """Get user details for editing"""
        user = User.query.get_or_404(user_id)
        return jsonify({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'department': user.department,
            'role': user.role,
            'access_level': user.access_level
        })
    
    @app.route("/admin/users/add", methods=['POST'])
    @login_required
    @admin_required
    def add_user():
        """Add new user"""
        try:
            data = request.json
            
            # Check if email already exists
            if User.query.filter_by(email=data['email']).first():
                return jsonify({"status": "error", "message": "Email already exists"}), 400
            
            # ✅ BUG #13 FIX: Validate password strength
            is_valid, errors = validate_password(data.get('password', ''))
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Password does not meet requirements: " + ", ".join(errors)
                }), 400
            
            user = User(
                name=data.get('name'),
                email=data['email'],
                password=generate_password_hash(data['password']),
                department=data['department'],
                role=data['role'],
                access_level=data['access_level']
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='create',
                target_type='user',
                target_id=user.id,
                description=f"Created new user: {data['email']}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User created successfully"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/users/<int:user_id>/edit", methods=['POST'])
    @login_required
    @admin_required
    def edit_user(user_id):
        """Edit existing user"""
        try:
            user = User.query.get_or_404(user_id)
            data = request.json
            
            user.name = data.get('name')
            user.email = data['email']
            user.department = data['department']
            user.role = data['role']
            user.access_level = data['access_level']
            
            if data.get('password'):
                # ✅ BUG #13 FIX: Validate password strength on update
                is_valid, errors = validate_password(data['password'])
                if not is_valid:
                    return jsonify({
                        "status": "error",
                        "message": "Password does not meet requirements: " + ", ".join(errors)
                    }), 400
                user.password = generate_password_hash(data['password'])
            
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='edit',
                target_type='user',
                target_id=user_id,
                description=f"Updated user: {data['email']}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User updated successfully"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/users/<int:user_id>/delete", methods=['POST'])
    @login_required
    @admin_required
    def delete_user(user_id):
        """Delete user"""
        try:
            if user_id == current_user.id:
                return jsonify({"status": "error", "message": "Cannot delete yourself"}), 400
            
            user = User.query.get_or_404(user_id)
            email = user.email
            
            db.session.delete(user)
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='delete',
                target_type='user',
                target_id=user_id,
                description=f"Deleted user: {email}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({"status": "success", "message": "User deleted successfully"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/queries")
    @login_required
    @admin_required
    def admin_queries():
        """Unanswered queries page"""
        queries = UnansweredQuery.query.filter_by(resolved=False).order_by(
            UnansweredQuery.created_at.desc()
        ).all()
        
        query_list = []
        for q in queries:
            user = User.query.get(q.user_id)
            query_list.append({
                'id': q.id,
                'question': q.question,
                'user_email': user.email if user else 'Unknown',
                'department': q.department,
                'access_level': q.access_level,
                'created_at': q.created_at
            })
        
        return render_template('admin_queries.html', queries=query_list)
    
    @app.route("/admin/queries/<int:query_id>/resolve", methods=['POST'])
    @login_required
    @admin_required
    def resolve_query(query_id):
        """Mark query as resolved"""
        try:
            query = UnansweredQuery.query.get_or_404(query_id)
            query.resolved = True
            query.resolved_at = datetime.utcnow()
            query.resolved_by = current_user.id
            query.resolution_notes = request.json.get('notes', '')
            
            db.session.commit()
            
            return jsonify({"status": "success", "message": "Query resolved"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # ============================================
    # PHASE 3B: ANALYTICS ROUTES
    # ============================================
    
    @app.route("/admin/analytics")
    @login_required
    @admin_required
    def admin_analytics():
        """Analytics dashboard"""
        from analytics_helper import AnalyticsHelper
        
        period = request.args.get('period', '30d')
        overview = AnalyticsHelper.get_overview_stats()
        most_asked = AnalyticsHelper.get_most_asked_questions(limit=10, period=period)
        user_ranking = AnalyticsHelper.get_user_activity_ranking(limit=10, period=period)
        dept_usage = AnalyticsHelper.get_department_usage(period=period)
        accuracy = AnalyticsHelper.get_response_accuracy()
        avg_response_time = AnalyticsHelper.get_average_response_time(period=period)
        doc_stats = AnalyticsHelper.get_document_upload_stats(period=period)
        query_timeline = AnalyticsHelper.get_query_volume_timeline(period=period)
        
        return render_template('admin_analytics.html',
                             period=period,
                             overview=overview,
                             most_asked=most_asked,
                             user_ranking=user_ranking,
                             dept_usage=dept_usage,
                             accuracy=accuracy,
                             avg_response_time=avg_response_time,
                             doc_stats=doc_stats,
                             query_timeline=query_timeline)
    
    @app.route("/admin/analytics/export")
    @login_required
    @admin_required
    def export_analytics():
        """Export analytics data"""
        from analytics_helper import AnalyticsHelper
        from flask import Response
        
        export_type = request.args.get('type', 'csv')
        data_type = request.args.get('data', 'most_asked')
        period = request.args.get('period', '30d')
        
        if data_type == 'most_asked':
            data = AnalyticsHelper.get_most_asked_questions(limit=50, period=period)
            filename = f'most_asked_questions_{period}'
        elif data_type == 'user_ranking':
            data = AnalyticsHelper.get_user_activity_ranking(limit=50, period=period)
            filename = f'user_activity_{period}'
        elif data_type == 'dept_usage':
            data = AnalyticsHelper.get_department_usage(period=period)
            filename = f'department_usage_{period}'
        else:
            return jsonify({"error": "Invalid data type"}), 400
        
        if export_type == 'csv':
            csv_data = AnalyticsHelper.export_to_csv(data, filename)
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}.csv'}
            )
        elif export_type == 'pdf':
            pdf_data = AnalyticsHelper.export_to_pdf(data, filename, period)
            return Response(
                pdf_data,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename={filename}.pdf'}
            )
        else:
            return jsonify({"error": "Invalid export type"}), 400
    
    @app.route("/admin/analytics/data")
    @login_required
    @admin_required
    def get_analytics_data():
        """API endpoint for dynamic analytics data"""
        from analytics_helper import AnalyticsHelper
        
        data_type = request.args.get('type')
        period = request.args.get('period', '30d')
        
        if data_type == 'query_timeline':
            data = AnalyticsHelper.get_query_volume_timeline(period=period)
        elif data_type == 'dept_usage':
            data = AnalyticsHelper.get_department_usage(period=period)
        elif data_type == 'overview':
            data = AnalyticsHelper.get_overview_stats()
        else:
            return jsonify({"error": "Invalid data type"}), 400
        
        return jsonify(data)