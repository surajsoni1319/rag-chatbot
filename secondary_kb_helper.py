# """
# Secondary KB Helper - Phase 3A.2
# Converts approved user feedback into searchable vector embeddings
# """

# from extensions import db
# from models import UserFeedback
# from src.embeddings import EmbeddingPipeline
# from src.pg_vectorstore import PostgresVectorStore
# from langchain.schema import Document
# import json
# from datetime import datetime


# class SecondaryKBHelper:
#     """Helper class to manage Secondary Knowledge Base from user feedback"""
    
#     @staticmethod
#     def feedback_to_embeddings(feedback_id, admin_id):
#         """
#         Convert approved feedback to vector embeddings and store in Secondary KB
        
#         Args:
#             feedback_id: ID of the UserFeedback record
#             admin_id: ID of the admin who approved it
            
#         Returns:
#             dict: Status and details of the operation
#         """
#         try:
#             # Get the feedback
#             feedback = UserFeedback.query.get(feedback_id)
#             if not feedback:
#                 return {"status": "error", "message": "Feedback not found"}
            
#             if feedback.status != 'approved':
#                 return {"status": "error", "message": "Only approved feedback can be added to KB"}
            
#             # Create a document from the feedback
#             # Combine original Q&A with the corrected feedback
#             content_parts = []
            
#             if feedback.original_question:
#                 content_parts.append(f"Question: {feedback.original_question}")
            
#             if feedback.feedback_text:
#                 content_parts.append(f"Correct Answer: {feedback.feedback_text}")
            
#             # If there was an original answer, include it for context
#             if feedback.original_answer:
#                 content_parts.append(f"Previous Answer (incorrect): {feedback.original_answer}")
            
#             full_content = "\n\n".join(content_parts)
            
#             # Create metadata
#             metadata = {
#                 "source": "user_feedback",
#                 "feedback_id": feedback_id,
#                 "feedback_type": feedback.feedback_type,
#                 "submitted_by": feedback.user.email,
#                 "approved_by_id": admin_id,
#                 "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
#                 "approved_at": feedback.reviewed_at.isoformat() if feedback.reviewed_at else None
#             }
            
#             # Create Document object
#             doc = Document(
#                 page_content=full_content,
#                 metadata=metadata
#             )
            
#             # Generate embeddings
#             print(f"📝 Generating embeddings for feedback #{feedback_id}...")
#             embedding_pipeline = EmbeddingPipeline()
            
#             # Process the document (returns chunks and vectors)
#             chunks, vectors = embedding_pipeline.process([doc])
            
#             print(f"✂️ Created {len(chunks)} chunks from feedback")
            
#             # Store in PostgreSQL vector store
#             # Use the user's department
#             user_dept = feedback.user.department.strip().lower()
            
#             # Create store instance
#             store = PostgresVectorStore(user_dept, feedback.user)
            
#             # Store with source_type='secondary' and feedback_id
#             inserted_count = store.build(
#                 vectors=vectors,
#                 documents=chunks,
#                 access_level='public',  # Make feedback accessible to all
#                 is_cross_dept=True,     # Available across departments
#                 source_type='secondary',  # Mark as secondary KB
#                 uploaded_by=admin_id,
#                 file_name=f"feedback_{feedback_id}",
#                 file_type='feedback'
#             )
            
#             print(f"✅ Successfully added {inserted_count} vectors to Secondary KB")
            
#             return {
#                 "status": "success",
#                 "message": f"Feedback added to Secondary Knowledge Base with {inserted_count} chunks",
#                 "chunks_created": len(chunks),
#                 "vectors_stored": inserted_count
#             }
            
#         except Exception as e:
#             print(f"❌ Error converting feedback to embeddings: {str(e)}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "status": "error",
#                 "message": f"Failed to add to KB: {str(e)}"
#             }
    
#     @staticmethod
#     def remove_feedback_from_kb(feedback_id):
#         """
#         Remove feedback embeddings from Secondary KB
#         (e.g., when feedback is rejected or deleted)
        
#         Args:
#             feedback_id: ID of the feedback to remove
            
#         Returns:
#             dict: Status and count of removed vectors
#         """
#         try:
#             from sqlalchemy import text
            
#             result = db.session.execute(
#                 text("""
#                     DELETE FROM document_embeddings 
#                     WHERE source_type = 'secondary' 
#                     AND file_name = :fname
#                 """),
#                 {"fname": f"feedback_{feedback_id}"}
#             )
#             db.session.commit()
            
#             removed_count = result.rowcount
#             print(f"🗑️ Removed {removed_count} vectors for feedback #{feedback_id}")
            
#             return {
#                 "status": "success",
#                 "removed_count": removed_count
#             }
            
#         except Exception as e:
#             db.session.rollback()
#             print(f"❌ Error removing feedback from KB: {str(e)}")
#             return {
#                 "status": "error",
#                 "message": str(e)
#             }
    
#     @staticmethod
#     def get_secondary_kb_stats():
#         """
#         Get statistics about Secondary KB
        
#         Returns:
#             dict: Statistics about secondary knowledge base
#         """
#         try:
#             from sqlalchemy import text
            
#             result = db.session.execute(
#                 text("""
#                     SELECT 
#                         COUNT(*) as total_vectors,
#                         COUNT(DISTINCT file_name) as total_feedbacks,
#                         MIN(created_at) as first_added,
#                         MAX(created_at) as last_added
#                     FROM document_embeddings
#                     WHERE source_type = 'secondary'
#                 """)
#             ).fetchone()
            
#             if result:
#                 return {
#                     "total_vectors": result.total_vectors,
#                     "total_feedbacks": result.total_feedbacks,
#                     "first_added": result.first_added,
#                     "last_added": result.last_added
#                 }
            
#             return {
#                 "total_vectors": 0,
#                 "total_feedbacks": 0,
#                 "first_added": None,
#                 "last_added": None
#             }
            
#         except Exception as e:
#             print(f"❌ Error getting Secondary KB stats: {str(e)}")
#             return None
    
#     @staticmethod
#     def rebuild_secondary_kb():
#         """
#         Rebuild entire Secondary KB from all approved feedbacks
#         Useful for maintenance or after changes
        
#         Returns:
#             dict: Status and statistics
#         """
#         try:
#             # Get all approved feedbacks
#             approved_feedbacks = UserFeedback.query.filter_by(status='approved').all()
            
#             print(f"🔄 Rebuilding Secondary KB from {len(approved_feedbacks)} approved feedbacks...")
            
#             success_count = 0
#             error_count = 0
            
#             for feedback in approved_feedbacks:
#                 result = SecondaryKBHelper.feedback_to_embeddings(
#                     feedback.id,
#                     feedback.reviewed_by
#                 )
                
#                 if result['status'] == 'success':
#                     success_count += 1
#                 else:
#                     error_count += 1
#                     print(f"⚠️ Failed to process feedback #{feedback.id}: {result['message']}")
            
#             return {
#                 "status": "success",
#                 "total_processed": len(approved_feedbacks),
#                 "success_count": success_count,
#                 "error_count": error_count
#             }
            
#         except Exception as e:
#             print(f"❌ Error rebuilding Secondary KB: {str(e)}")
#             import traceback
#             traceback.print_exc()
#             return {
#                 "status": "error",
#                 "message": str(e)
#             }




################################




"""
Secondary KB Helper - Phase 3A.2
Converts approved user feedback into searchable vector embeddings
"""

from extensions import db
from models import UserFeedback
from src.embeddings import EmbeddingPipeline
from src.pg_vectorstore import PostgresVectorStore
from langchain.schema import Document
import json
from datetime import datetime


class SecondaryKBHelper:
    """Helper class to manage Secondary Knowledge Base from user feedback"""
    
    @staticmethod
    def feedback_to_embeddings(feedback_id, admin_id):
        """
        Convert approved feedback to vector embeddings and store in Secondary KB
        
        Args:
            feedback_id: ID of the UserFeedback record
            admin_id: ID of the admin who approved it
            
        Returns:
            dict: Status and details of the operation
        """
        try:
            # Get the feedback
            feedback = UserFeedback.query.get(feedback_id)
            if not feedback:
                return {"status": "error", "message": "Feedback not found"}
            
            if feedback.status != 'approved':
                return {"status": "error", "message": "Only approved feedback can be added to KB"}
            
            # Create a document from the feedback
            # Combine original Q&A with the corrected feedback
            content_parts = []
            
            if feedback.original_question:
                content_parts.append(f"Question: {feedback.original_question}")
            
            if feedback.feedback_text:
                content_parts.append(f"Correct Answer: {feedback.feedback_text}")
            
            # If there was an original answer, include it for context
            if feedback.original_answer:
                content_parts.append(f"Previous Answer (incorrect): {feedback.original_answer}")
            
            full_content = "\n\n".join(content_parts)
            
            # Create metadata
            metadata = {
                "source": "user_feedback",
                "feedback_id": feedback_id,
                "feedback_type": feedback.feedback_type,
                "submitted_by": feedback.user.email,
                "approved_by_id": admin_id,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
                "approved_at": feedback.reviewed_at.isoformat() if feedback.reviewed_at else None
            }
            
            # Create Document object
            doc = Document(
                page_content=full_content,
                metadata=metadata
            )
            
            # Generate embeddings
            print(f"📝 Generating embeddings for feedback #{feedback_id}...")
            embedding_pipeline = EmbeddingPipeline()
            
            # Process the document (returns chunks and vectors)
            chunks, vectors = embedding_pipeline.process([doc])
            
            print(f"✂️ Created {len(chunks)} chunks from feedback")
            
            # ✅ INHERIT DEPARTMENT CONTEXT FROM ORIGINAL QUESTION
            # Get the chat history to determine which docs were used
            from models import ChatHistory
            from sqlalchemy import text
            
            user_dept = feedback.user.department.strip().lower()
            target_dept = user_dept
            target_access = 'employee'  # Default
            target_cross_dept = False    # Default
            
            # Try to get context from chat history
            if feedback.chat_history_id:
                chat = ChatHistory.query.get(feedback.chat_history_id)
                if chat:
                    # Find which PRIMARY documents were used to answer this question
                    # Check the user's department docs that would have been searched
                    doc_context = db.session.execute(text("""
                        SELECT DISTINCT 
                            department,
                            access_level,
                            is_cross_dept
                        FROM document_embeddings
                        WHERE source_type = 'primary'
                          AND (department = :dept OR is_cross_dept = true)
                        LIMIT 1
                    """), {"dept": user_dept}).fetchone()
                    
                    if doc_context:
                        target_dept = doc_context.department
                        target_access = doc_context.access_level
                        target_cross_dept = doc_context.is_cross_dept
                        print(f"📍 Inherited context: dept={target_dept}, access={target_access}, cross_dept={target_cross_dept}")
                    else:
                        print(f"⚠️ No doc context found, using user's department: {user_dept}")
            
            # Create store instance with target department
            store = PostgresVectorStore(target_dept, feedback.user)
            
            # Store with inherited context
            inserted_count = store.build(
                vectors=vectors,
                documents=chunks,
                access_level=target_access,        # ✅ Inherited from original docs
                is_cross_dept=target_cross_dept,   # ✅ Inherited from original docs
                source_type='secondary',           # Mark as secondary KB
                uploaded_by=admin_id,
                file_name=f"feedback_{feedback_id}",
                file_type='feedback',
                feedback_id=feedback_id
            )
            
            print(f"✅ Stored feedback in {target_dept} dept, cross_dept={target_cross_dept}")
            
            print(f"✅ Successfully added {inserted_count} vectors to Secondary KB")
            
            return {
                "status": "success",
                "message": f"Feedback added to Secondary Knowledge Base with {inserted_count} chunks",
                "chunks_created": len(chunks),
                "vectors_stored": inserted_count
            }
            
        except Exception as e:
            print(f"❌ Error converting feedback to embeddings: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Failed to add to KB: {str(e)}"
            }
    
    @staticmethod
    def remove_feedback_from_kb(feedback_id):
        """
        Remove feedback embeddings from Secondary KB
        (e.g., when feedback is rejected or deleted)
        
        Args:
            feedback_id: ID of the feedback to remove
            
        Returns:
            dict: Status and count of removed vectors
        """
        try:
            from sqlalchemy import text
            
            # ✅ BUG #5 FIX: Use feedback_id column for more reliable deletion
            result = db.session.execute(
                text("""
                    DELETE FROM document_embeddings 
                    WHERE feedback_id = :fid
                """),
                {"fid": feedback_id}
            )
            db.session.commit()
            
            removed_count = result.rowcount
            print(f"🗑️ Removed {removed_count} vectors for feedback #{feedback_id}")
            
            return {
                "status": "success",
                "removed_count": removed_count
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error removing feedback from KB: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    @staticmethod
    def get_secondary_kb_stats():
        """
        Get statistics about Secondary KB
        
        Returns:
            dict: Statistics about secondary knowledge base
        """
        try:
            from sqlalchemy import text
            
            result = db.session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_vectors,
                        COUNT(DISTINCT file_name) as total_feedbacks,
                        MIN(created_at) as first_added,
                        MAX(created_at) as last_added
                    FROM document_embeddings
                    WHERE source_type = 'secondary'
                """)
            ).fetchone()
            
            if result:
                return {
                    "total_vectors": result.total_vectors,
                    "total_feedbacks": result.total_feedbacks,
                    "first_added": result.first_added,
                    "last_added": result.last_added
                }
            
            return {
                "total_vectors": 0,
                "total_feedbacks": 0,
                "first_added": None,
                "last_added": None
            }
            
        except Exception as e:
            print(f"❌ Error getting Secondary KB stats: {str(e)}")
            return None
    
    @staticmethod
    def rebuild_secondary_kb():
        """
        Rebuild entire Secondary KB from all approved feedbacks
        Useful for maintenance or after changes
        
        Returns:
            dict: Status and statistics
        """
        try:
            # Get all approved feedbacks
            approved_feedbacks = UserFeedback.query.filter_by(status='approved').all()
            
            print(f"🔄 Rebuilding Secondary KB from {len(approved_feedbacks)} approved feedbacks...")
            
            success_count = 0
            error_count = 0
            
            for feedback in approved_feedbacks:
                result = SecondaryKBHelper.feedback_to_embeddings(
                    feedback.id,
                    feedback.reviewed_by
                )
                
                if result['status'] == 'success':
                    success_count += 1
                else:
                    error_count += 1
                    print(f"⚠️ Failed to process feedback #{feedback.id}: {result['message']}")
            
            return {
                "status": "success",
                "total_processed": len(approved_feedbacks),
                "success_count": success_count,
                "error_count": error_count
            }
            
        except Exception as e:
            print(f"❌ Error rebuilding Secondary KB: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": str(e)
            }