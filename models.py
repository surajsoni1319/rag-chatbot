from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    
    # NEW FIELDS
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')
    access_level = db.Column(db.String(20), default='employee')
    
    # Relationships - FIXED: Added foreign_keys specification
    sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade='all, delete-orphan')
    chat_history = db.relationship('ChatHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    feedback = db.relationship('UserFeedback', foreign_keys='UserFeedback.user_id', backref='user', lazy=True)
    unanswered_queries = db.relationship('UnansweredQuery', foreign_keys='UnansweredQuery.user_id', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def is_admin(self):
        return self.role == 'admin'
    
    def can_access(self, required_level):
        """Check if user can access content with required_level"""
        levels = ['public', 'employee', 'manager', 'senior_mgmt', 'executive']
        try:
            user_level_index = levels.index(self.access_level)
            required_level_index = levels.index(required_level)
            return user_level_index >= required_level_index
        except ValueError:
            return False


class ChatSession(db.Model):
    __tablename__ = 'chat_session'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), default='New Chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db.relationship('ChatHistory', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChatSession {self.id}: {self.title}>'


class ChatHistory(db.Model):
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.Text)
    answer = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChatHistory {self.id}>'


class UserFeedback(db.Model):
    __tablename__ = 'user_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chat_history_id = db.Column(db.Integer, db.ForeignKey('chat_history.id'), nullable=True)
    original_question = db.Column(db.Text)
    original_answer = db.Column(db.Text)
    feedback_text = db.Column(db.Text)
    feedback_type = db.Column(db.String(50), default='correction')
    attached_files = db.Column(db.JSON, default=list)
    status = db.Column(db.String(20), default='pending')
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationship for reviewer
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_feedback')
    
    def __repr__(self):
        return f'<UserFeedback {self.id}: {self.status}>'


class UnansweredQuery(db.Model):
    __tablename__ = 'unanswered_queries'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    department = db.Column(db.String(50))
    access_level = db.Column(db.String(20))
    similarity_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolution_notes = db.Column(db.Text)
    
    # Relationship for resolver
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='resolved_queries')
    
    def __repr__(self):
        return f'<UnansweredQuery {self.id}: {self.resolved}>'


class AdminActivityLog(db.Model):
    __tablename__ = 'admin_activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    meta_data = db.Column('metadata', db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    admin = db.relationship('User', backref='activity_logs')
    
    def __repr__(self):
        return f'<AdminActivityLog {self.id}: {self.action_type}>'