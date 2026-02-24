# """
# Feedback Routes for Phase 3A
# Handle user feedback submissions and admin reviews
# """

# from flask import request, jsonify, render_template
# from flask_login import login_required, current_user
# from functools import wraps
# from extensions import db  # FIXED: Removed 'app.' prefix
# from models import User, ChatHistory, UserFeedback, AdminActivityLog  # FIXED: Removed 'app.models.'
# from datetime import datetime
# import os
# from werkzeug.utils import secure_filename

# # Admin required decorator
# def admin_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if not current_user.is_authenticated or not current_user.is_admin():
#             return jsonify({"error": "Admin access required"}), 403
#         return f(*args, **kwargs)
#     return decorated_function

# # Allowed file extensions for feedback attachments
# ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'}
# UPLOAD_FOLDER = 'uploads/feedback'

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def register_feedback_routes(app):
    
#     # Ensure upload folder exists
#     os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
#     @app.route("/feedback/submit", methods=["POST"])
#     @login_required
#     def submit_feedback():
#         """User submits feedback about an answer"""
#         try:
#             # Get form data
#             data = request.form
#             chat_id = data.get('chat_history_id')
#             feedback_text = data.get('feedback_text', '').strip()
#             feedback_type = data.get('feedback_type', 'correction')
            
#             if not feedback_text:
#                 return jsonify({"status": "error", "message": "Feedback text is required"}), 400
            
#             # Get original Q&A if chat_id provided
#             original_question = None
#             original_answer = None
#             if chat_id:
#                 chat = ChatHistory.query.get(chat_id)
#                 if chat and chat.user_id == current_user.id:
#                     original_question = chat.question
#                     original_answer = chat.answer
            
#             # Handle file uploads
#             attached_files = []
#             if 'files' in request.files:
#                 files = request.files.getlist('files')
#                 for file in files:
#                     if file and allowed_file(file.filename):
#                         filename = secure_filename(file.filename)
#                         # Add timestamp to avoid duplicates
#                         timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
#                         filename = f"{current_user.id}_{timestamp}_{filename}"
#                         filepath = os.path.join(UPLOAD_FOLDER, filename)
#                         file.save(filepath)
#                         attached_files.append(filepath)
            
#             # Create feedback record
#             feedback = UserFeedback(
#                 user_id=current_user.id,
#                 chat_history_id=chat_id if chat_id else None,
#                 original_question=original_question,
#                 original_answer=original_answer,
#                 feedback_text=feedback_text,
#                 feedback_type=feedback_type,
#                 attached_files=attached_files,
#                 status='pending'
#             )
            
#             db.session.add(feedback)
#             db.session.commit()
            
#             return jsonify({
#                 "status": "success",
#                 "message": "Thank you! Your feedback has been submitted and will be reviewed by our team.",
#                 "feedback_id": feedback.id
#             })
            
#         except Exception as e:
#             db.session.rollback()
#             print(f"❌ Error submitting feedback: {str(e)}")
#             import traceback
#             traceback.print_exc()
#             return jsonify({"status": "error", "message": str(e)}), 500
    
#     @app.route("/feedback/my-submissions")
#     @login_required
#     def my_feedback_submissions():
#         """User views their own feedback submissions"""
#         try:
#             feedbacks = UserFeedback.query.filter_by(
#                 user_id=current_user.id
#             ).order_by(UserFeedback.created_at.desc()).all()
            
#             return render_template('user_feedback_history.html', feedbacks=feedbacks)
            
#         except Exception as e:
#             print(f"❌ Error loading feedback history: {str(e)}")
#             return jsonify({"error": str(e)}), 500
    
#     @app.route("/admin/feedback")
#     @login_required
#     @admin_required
#     def admin_feedback_review():
#         """Admin reviews all feedback submissions"""
#         try:
#             # Get filter parameters
#             status_filter = request.args.get('status', 'pending')
            
#             query = UserFeedback.query
            
#             if status_filter and status_filter != 'all':
#                 query = query.filter_by(status=status_filter)
            
#             feedbacks = query.order_by(UserFeedback.created_at.desc()).all()
            
#             # Get statistics
#             stats = {
#                 'pending': UserFeedback.query.filter_by(status='pending').count(),
#                 'approved': UserFeedback.query.filter_by(status='approved').count(),
#                 'rejected': UserFeedback.query.filter_by(status='rejected').count(),
#                 'total': UserFeedback.query.count()
#             }
            
#             return render_template('admin_feedback_review.html', 
#                                  feedbacks=feedbacks, 
#                                  stats=stats,
#                                  current_filter=status_filter)
            
#         except Exception as e:
#             print(f"❌ Error loading feedback: {str(e)}")
#             return jsonify({"error": str(e)}), 500
    
#     @app.route("/feedback/<int:feedback_id>/details")
#     @login_required
#     def get_feedback_details(feedback_id):
#         """Get feedback details for viewing"""
#         try:
#             feedback = UserFeedback.query.get_or_404(feedback_id)
            
#             # Only admin or the user who submitted can view
#             if not current_user.is_admin() and feedback.user_id != current_user.id:
#                 return jsonify({"error": "Unauthorized"}), 403
            
#             return jsonify({
#                 "id": feedback.id,
#                 "user_email": feedback.user.email,
#                 "user": {
#                     "department": feedback.user.department
#                 },
#                 "feedback_type": feedback.feedback_type,
#                 "original_question": feedback.original_question,
#                 "original_answer": feedback.original_answer,
#                 "feedback_text": feedback.feedback_text,
#                 "attached_files": feedback.attached_files or [],
#                 "status": feedback.status,
#                 "admin_notes": feedback.admin_notes,
#                 "created_at": feedback.created_at.isoformat() if feedback.created_at else None
#             })
            
#         except Exception as e:
#             print(f"❌ Error loading feedback details: {str(e)}")
#             return jsonify({"error": str(e)}), 500
    
#     @app.route("/admin/feedback/<int:feedback_id>/approve", methods=["POST"])
#     @login_required
#     @admin_required
#     def approve_feedback(feedback_id):
#         """Admin approves feedback - adds to Secondary KB"""
#         try:
#             feedback = UserFeedback.query.get_or_404(feedback_id)
#             data = request.json or {}
            
#             # Update feedback status
#             feedback.status = 'approved'
#             feedback.reviewed_by = current_user.id
#             feedback.reviewed_at = datetime.utcnow()
#             feedback.admin_notes = data.get('admin_notes', '')
            
#             db.session.commit()
            
#             # Log activity
#             log = AdminActivityLog(
#                 admin_id=current_user.id,
#                 action_type='edit',
#                 target_type='feedback',
#                 target_id=feedback_id,
#                 description=f"Approved feedback from {feedback.user.email}"
#             )
#             db.session.add(log)
#             db.session.commit()
            
#             return jsonify({
#                 "status": "success",
#                 "message": "Feedback approved and added to knowledge base"
#             })
            
#         except Exception as e:
#             db.session.rollback()
#             print(f"❌ Error approving feedback: {str(e)}")
#             return jsonify({"status": "error", "message": str(e)}), 500
    
#     @app.route("/admin/feedback/<int:feedback_id>/reject", methods=["POST"])
#     @login_required
#     @admin_required
#     def reject_feedback(feedback_id):
#         """Admin rejects feedback"""
#         try:
#             feedback = UserFeedback.query.get_or_404(feedback_id)
#             data = request.json or {}
            
#             feedback.status = 'rejected'
#             feedback.reviewed_by = current_user.id
#             feedback.reviewed_at = datetime.utcnow()
#             feedback.admin_notes = data.get('admin_notes', '')
            
#             db.session.commit()
            
#             # Log activity
#             log = AdminActivityLog(
#                 admin_id=current_user.id,
#                 action_type='edit',
#                 target_type='feedback',
#                 target_id=feedback_id,
#                 description=f"Rejected feedback from {feedback.user.email}"
#             )
#             db.session.add(log)
#             db.session.commit()
            
#             return jsonify({
#                 "status": "success",
#                 "message": "Feedback rejected"
#             })
            
#         except Exception as e:
#             db.session.rollback()
#             print(f"❌ Error rejecting feedback: {str(e)}")
#             return jsonify({"status": "error", "message": str(e)}), 500
    
#     @app.route("/admin/feedback/<int:feedback_id>/delete", methods=["POST"])
#     @login_required
#     @admin_required
#     def delete_feedback(feedback_id):
#         """Admin deletes feedback"""
#         try:
#             feedback = UserFeedback.query.get_or_404(feedback_id)
            
#             # Delete attached files
#             if feedback.attached_files:
#                 for filepath in feedback.attached_files:
#                     if os.path.exists(filepath):
#                         os.remove(filepath)
            
#             db.session.delete(feedback)
#             db.session.commit()
            
#             # Log activity
#             log = AdminActivityLog(
#                 admin_id=current_user.id,
#                 action_type='delete',
#                 target_type='feedback',
#                 target_id=feedback_id,
#                 description=f"Deleted feedback #{feedback_id}"
#             )
#             db.session.add(log)
#             db.session.commit()
            
#             return jsonify({
#                 "status": "success",
#                 "message": "Feedback deleted successfully"
#             })
            
#         except Exception as e:
#             db.session.rollback()
#             print(f"❌ Error deleting feedback: {str(e)}")
#             return jsonify({"status": "error", "message": str(e)}), 500
    
#     @app.route("/feedback/<int:feedback_id>/status")
#     @login_required
#     def check_feedback_status(feedback_id):
#         """User checks status of their feedback"""
#         try:
#             feedback = UserFeedback.query.get_or_404(feedback_id)
            
#             # Ensure user can only see their own feedback
#             if feedback.user_id != current_user.id:
#                 return jsonify({"error": "Unauthorized"}), 403
            
#             return jsonify({
#                 "status": feedback.status,
#                 "reviewed_at": feedback.reviewed_at.isoformat() if feedback.reviewed_at else None,
#                 "admin_notes": feedback.admin_notes if feedback.status != 'pending' else None
#             })
            
#         except Exception as e:
#             print(f"❌ Error checking feedback status: {str(e)}")
#             return jsonify({"error": str(e)}), 500




# 3a.2 updarted secondary_kb_helper.py with feedback integration

"""
Feedback Routes for Phase 3A
Handle user feedback submissions and admin reviews
"""

from flask import request, jsonify, render_template
from flask_login import login_required, current_user
from functools import wraps
from extensions import db  # FIXED: Removed 'app.' prefix
from models import User, ChatHistory, UserFeedback, AdminActivityLog  # FIXED: Removed 'app.models.'
from datetime import datetime
import os
from werkzeug.utils import secure_filename

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Allowed file extensions for feedback attachments
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'}
UPLOAD_FOLDER = 'uploads/feedback'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def register_feedback_routes(app):
    
    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    @app.route("/feedback/submit", methods=["POST"])
    @login_required
    def submit_feedback():
        """User submits feedback about an answer"""
        try:
            # Get form data
            data = request.form
            chat_id = data.get('chat_history_id')
            feedback_text = data.get('feedback_text', '').strip()
            feedback_type = data.get('feedback_type', 'correction')
            
            if not feedback_text:
                return jsonify({"status": "error", "message": "Feedback text is required"}), 400
            
            # Get original Q&A if chat_id provided
            original_question = None
            original_answer = None
            if chat_id:
                chat = ChatHistory.query.get(chat_id)
                if chat and chat.user_id == current_user.id:
                    original_question = chat.question
                    original_answer = chat.answer
            
            # Handle file uploads
            attached_files = []
            if 'files' in request.files:
                files = request.files.getlist('files')
                for file in files:
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        # Add timestamp to avoid duplicates
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        filename = f"{current_user.id}_{timestamp}_{filename}"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        file.save(filepath)
                        attached_files.append(filepath)
            
            # Create feedback record
            feedback = UserFeedback(
                user_id=current_user.id,
                chat_history_id=chat_id if chat_id else None,
                original_question=original_question,
                original_answer=original_answer,
                feedback_text=feedback_text,
                feedback_type=feedback_type,
                attached_files=attached_files,
                status='pending'
            )
            
            db.session.add(feedback)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "Thank you! Your feedback has been submitted and will be reviewed by our team.",
                "feedback_id": feedback.id
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error submitting feedback: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/feedback/my-submissions")
    @login_required
    def my_feedback_submissions():
        """User views their own feedback submissions"""
        try:
            feedbacks = UserFeedback.query.filter_by(
                user_id=current_user.id
            ).order_by(UserFeedback.created_at.desc()).all()
            
            return render_template('user_feedback_history.html', feedbacks=feedbacks)
            
        except Exception as e:
            print(f"❌ Error loading feedback history: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/admin/feedback")
    @login_required
    @admin_required
    def admin_feedback_review():
        """Admin reviews all feedback submissions"""
        try:
            # Get filter parameters
            status_filter = request.args.get('status', 'pending')
            
            query = UserFeedback.query
            
            if status_filter and status_filter != 'all':
                query = query.filter_by(status=status_filter)
            
            feedbacks = query.order_by(UserFeedback.created_at.desc()).all()
            
            # Get statistics
            stats = {
                'pending': UserFeedback.query.filter_by(status='pending').count(),
                'approved': UserFeedback.query.filter_by(status='approved').count(),
                'rejected': UserFeedback.query.filter_by(status='rejected').count(),
                'total': UserFeedback.query.count()
            }
            
            return render_template('admin_feedback_review.html', 
                                 feedbacks=feedbacks, 
                                 stats=stats,
                                 current_filter=status_filter)
            
        except Exception as e:
            print(f"❌ Error loading feedback: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/feedback/<int:feedback_id>/details")
    @login_required
    def get_feedback_details(feedback_id):
        """Get feedback details for viewing"""
        try:
            feedback = UserFeedback.query.get_or_404(feedback_id)
            
            # Only admin or the user who submitted can view
            if not current_user.is_admin() and feedback.user_id != current_user.id:
                return jsonify({"error": "Unauthorized"}), 403
            
            return jsonify({
                "id": feedback.id,
                "user_email": feedback.user.email,
                "user": {
                    "department": feedback.user.department
                },
                "feedback_type": feedback.feedback_type,
                "original_question": feedback.original_question,
                "original_answer": feedback.original_answer,
                "feedback_text": feedback.feedback_text,
                "attached_files": feedback.attached_files or [],
                "status": feedback.status,
                "admin_notes": feedback.admin_notes,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None
            })
            
        except Exception as e:
            print(f"❌ Error loading feedback details: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/admin/feedback/<int:feedback_id>/approve", methods=["POST"])
    @login_required
    @admin_required
    def approve_feedback(feedback_id):
        """Admin approves feedback - adds to Secondary KB"""
        try:
            feedback = UserFeedback.query.get_or_404(feedback_id)
            data = request.json or {}
            
            # Update feedback status
            feedback.status = 'approved'
            feedback.reviewed_by = current_user.id
            feedback.reviewed_at = datetime.utcnow()
            feedback.admin_notes = data.get('admin_notes', '')
            
            db.session.commit()
            
            # PHASE 3A.2: Add approved feedback to Secondary KB
            from secondary_kb_helper import SecondaryKBHelper
            
            kb_result = SecondaryKBHelper.feedback_to_embeddings(
                feedback_id=feedback_id,
                admin_id=current_user.id
            )
            
            # Log activity
            log_description = f"Approved feedback from {feedback.user.email}"
            if kb_result['status'] == 'success':
                log_description += f" - Added to Secondary KB ({kb_result.get('chunks_created', 0)} chunks)"
            else:
                log_description += f" - KB Error: {kb_result.get('message', 'Unknown error')}"
            
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='edit',
                target_type='feedback',
                target_id=feedback_id,
                description=log_description,
                meta_data={
                    'kb_status': kb_result['status'],
                    'chunks_created': kb_result.get('chunks_created', 0),
                    'vectors_stored': kb_result.get('vectors_stored', 0)
                }
            )
            db.session.add(log)
            db.session.commit()
            
            # Return success with KB integration details
            message = "Feedback approved"
            if kb_result['status'] == 'success':
                message += f" and added to knowledge base ({kb_result.get('vectors_stored', 0)} vectors)"
            else:
                message += " but failed to add to knowledge base"
            
            return jsonify({
                "status": "success",
                "message": message,
                "kb_integration": kb_result
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error approving feedback: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/feedback/<int:feedback_id>/reject", methods=["POST"])
    @login_required
    @admin_required
    def reject_feedback(feedback_id):
        """Admin rejects feedback"""
        try:
            feedback = UserFeedback.query.get_or_404(feedback_id)
            data = request.json or {}
            
            feedback.status = 'rejected'
            feedback.reviewed_by = current_user.id
            feedback.reviewed_at = datetime.utcnow()
            feedback.admin_notes = data.get('admin_notes', '')
            
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='edit',
                target_type='feedback',
                target_id=feedback_id,
                description=f"Rejected feedback from {feedback.user.email}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "Feedback rejected"
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error rejecting feedback: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/admin/feedback/<int:feedback_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def delete_feedback(feedback_id):
        """Admin deletes feedback"""
        try:
            feedback = UserFeedback.query.get_or_404(feedback_id)
            
            # PHASE 3A.2: Remove from Secondary KB if it was approved
            if feedback.status == 'approved':
                from secondary_kb_helper import SecondaryKBHelper
                SecondaryKBHelper.remove_feedback_from_kb(feedback_id)
            
            # Delete attached files
            if feedback.attached_files:
                for filepath in feedback.attached_files:
                    if os.path.exists(filepath):
                        os.remove(filepath)
            
            db.session.delete(feedback)
            db.session.commit()
            
            # Log activity
            log = AdminActivityLog(
                admin_id=current_user.id,
                action_type='delete',
                target_type='feedback',
                target_id=feedback_id,
                description=f"Deleted feedback #{feedback_id}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "Feedback deleted successfully"
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error deleting feedback: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route("/feedback/<int:feedback_id>/status")
    @login_required
    def check_feedback_status(feedback_id):
        """User checks status of their feedback"""
        try:
            feedback = UserFeedback.query.get_or_404(feedback_id)
            
            # Ensure user can only see their own feedback
            if feedback.user_id != current_user.id:
                return jsonify({"error": "Unauthorized"}), 403
            
            return jsonify({
                "status": feedback.status,
                "reviewed_at": feedback.reviewed_at.isoformat() if feedback.reviewed_at else None,
                "admin_notes": feedback.admin_notes if feedback.status != 'pending' else None
            })
            
        except Exception as e:
            print(f"❌ Error checking feedback status: {str(e)}")
            return jsonify({"error": str(e)}), 500