"""
Analytics Helper Functions for Phase 3B
Provides data queries and calculations for admin analytics dashboard
"""

from extensions import db
from models import User, ChatHistory, UserFeedback, AdminActivityLog, UnansweredQuery, ChatSession
from sqlalchemy import func, desc, and_, cast, Integer
from datetime import datetime, timedelta
import json


class AnalyticsHelper:
    """Helper class for analytics calculations"""
    
    @staticmethod
    def get_date_range(period='7d'):
        """Get start and end dates based on period"""
        end_date = datetime.utcnow()
        
        if period == '7d':
            start_date = end_date - timedelta(days=7)
        elif period == '30d':
            start_date = end_date - timedelta(days=30)
        elif period == '90d':
            start_date = end_date - timedelta(days=90)
        elif period == 'all':
            start_date = datetime(2000, 1, 1)  # All time
        elif isinstance(period, tuple):  # Custom range
            start_date, end_date = period
        else:
            start_date = end_date - timedelta(days=7)
        
        return start_date, end_date
    
    @staticmethod
    def get_most_asked_questions(limit=10, period='7d'):
        """Get most frequently asked questions"""
        start_date, end_date = AnalyticsHelper.get_date_range(period)
        
        results = db.session.query(
            ChatHistory.question,
            func.count(ChatHistory.id).label('count')
        ).filter(
            ChatHistory.timestamp.between(start_date, end_date)
        ).group_by(
            ChatHistory.question
        ).order_by(
            desc('count')
        ).limit(limit).all()
        
        return [{'question': r.question[:100], 'count': r.count} for r in results]
    
    @staticmethod
    def get_user_activity_ranking(limit=10, period='7d'):
        """Get users ranked by query count"""
        start_date, end_date = AnalyticsHelper.get_date_range(period)
        
        results = db.session.query(
            User.email,
            User.name,
            User.department,
            func.count(ChatHistory.id).label('query_count')
        ).join(
            ChatHistory, User.id == ChatHistory.user_id
        ).filter(
            ChatHistory.timestamp.between(start_date, end_date)
        ).group_by(
            User.id, User.email, User.name, User.department
        ).order_by(
            desc('query_count')
        ).limit(limit).all()
        
        return [{
            'email': r.email,
            'name': r.name or r.email.split('@')[0],
            'department': r.department,
            'query_count': r.query_count
        } for r in results]
    
    @staticmethod
    def get_department_usage(period='7d'):
        """Get query count by department"""
        start_date, end_date = AnalyticsHelper.get_date_range(period)
        
        results = db.session.query(
            User.department,
            func.count(ChatHistory.id).label('query_count')
        ).join(
            ChatHistory, User.id == ChatHistory.user_id
        ).filter(
            ChatHistory.timestamp.between(start_date, end_date)
        ).group_by(
            User.department
        ).all()
        
        return [{
            'department': r.department.upper(),
            'query_count': r.query_count
        } for r in results]
    
    @staticmethod
    def get_response_accuracy():
        """Calculate response accuracy from feedback"""
        total_feedback = UserFeedback.query.count()
        
        if total_feedback == 0:
            return {
                'accuracy_percentage': 0,
                'total_feedback': 0,
                'approved': 0,
                'rejected': 0,
                'pending': 0
            }
        
        approved = UserFeedback.query.filter_by(status='approved').count()
        rejected = UserFeedback.query.filter_by(status='rejected').count()
        pending = UserFeedback.query.filter_by(status='pending').count()
        
        # Accuracy = queries without negative feedback / total queries
        # Assuming rejected feedback indicates inaccurate responses
        total_queries = ChatHistory.query.count()
        inaccurate = rejected
        
        accuracy = ((total_queries - inaccurate) / total_queries * 100) if total_queries > 0 else 100
        
        return {
            'accuracy_percentage': round(accuracy, 2),
            'total_feedback': total_feedback,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'total_queries': total_queries
        }
    
    @staticmethod
    def get_average_response_time(period='7d'):
        """Calculate average response time (simulated - based on query complexity)"""
        start_date, end_date = AnalyticsHelper.get_date_range(period)
        
        queries = ChatHistory.query.filter(
            ChatHistory.timestamp.between(start_date, end_date)
        ).all()
        
        if not queries:
            return {
                'avg_time_seconds': 0,
                'total_queries': 0
            }
        
        # Estimate response time based on answer length
        # Real implementation would require timing data
        total_time = 0
        for q in queries:
            # Estimate: 1 second base + 0.01 seconds per character
            estimated_time = 1.0 + (len(q.answer) * 0.01) if q.answer else 1.0
            total_time += estimated_time
        
        avg_time = total_time / len(queries)
        
        return {
            'avg_time_seconds': round(avg_time, 2),
            'total_queries': len(queries)
        }
    
    @staticmethod
    def get_document_upload_stats(period='30d'):
        """Get document upload statistics"""
        start_date, end_date = AnalyticsHelper.get_date_range(period)
        
        # Get upload activities from admin activity log
        uploads = AdminActivityLog.query.filter(
            and_(
                AdminActivityLog.action_type == 'upload',
                AdminActivityLog.created_at.between(start_date, end_date)
            )
        ).all()
        
        total_uploads = len(uploads)
        total_files = 0
        by_department = {}
        
        for upload in uploads:
            if upload.meta_data and 'file_count' in upload.meta_data:
                total_files += upload.meta_data['file_count']
            
            # Extract department from description
            if upload.description:
                for dept in ['hr', 'it', 'finance', 'tech', 'admin', 'operations']:
                    if dept in upload.description.lower():
                        by_department[dept] = by_department.get(dept, 0) + 1
        
        return {
            'total_uploads': total_uploads,
            'total_files': total_files,
            'by_department': by_department,
            'uploads_per_week': round(total_uploads / 4, 1) if period == '30d' else total_uploads
        }
    
    @staticmethod
    def get_query_volume_timeline(period='30d'):
        """Get query volume over time for charting"""
        start_date, end_date = AnalyticsHelper.get_date_range(period)
        
        # Group by date
        results = db.session.query(
            func.date(ChatHistory.timestamp).label('date'),
            func.count(ChatHistory.id).label('count')
        ).filter(
            ChatHistory.timestamp.between(start_date, end_date)
        ).group_by(
            func.date(ChatHistory.timestamp)
        ).order_by('date').all()
        
        return [{
            'date': r.date.strftime('%Y-%m-%d'),
            'count': r.count
        } for r in results]
    
    @staticmethod
    def get_overview_stats():
        """Get overview statistics for dashboard cards"""
        total_users = User.query.count()
        total_queries = ChatHistory.query.count()
        total_documents = db.session.query(
            func.count(func.distinct(AdminActivityLog.target_id))
        ).filter(
            AdminActivityLog.action_type == 'upload'
        ).scalar() or 0
        
        unanswered_queries = UnansweredQuery.query.filter_by(resolved=False).count()
        
        # Active users (queried in last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        active_users = db.session.query(
            func.count(func.distinct(ChatHistory.user_id))
        ).filter(
            ChatHistory.timestamp >= seven_days_ago
        ).scalar() or 0
        
        # Queries today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        queries_today = ChatHistory.query.filter(
            ChatHistory.timestamp >= today_start
        ).count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_queries': total_queries,
            'queries_today': queries_today,
            'total_documents': total_documents,
            'unanswered_queries': unanswered_queries
        }
    
    @staticmethod
    def export_to_csv(data, filename):
        """Export analytics data to CSV format"""
        import csv
        from io import StringIO
        
        output = StringIO()
        
        if not data:
            return ""
        
        # Get headers from first item
        headers = data[0].keys()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    @staticmethod
    def export_to_pdf(data, title, period):
        """Export analytics data to PDF format (placeholder)"""
        # This would require reportlab or weasyprint
        # For now, return a simple text representation
        # You can enhance this with actual PDF generation
        
        from io import BytesIO
        
        pdf_content = f"""
ANALYTICS REPORT
================
Title: {title}
Period: {period}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

Data:
{json.dumps(data, indent=2)}
        """
        
        return pdf_content.encode('utf-8')