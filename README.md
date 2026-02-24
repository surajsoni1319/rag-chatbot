🚀 RAG Chatbot
Production-Ready Retrieval-Augmented Generation System

Built with Flask • OpenAI • PostgreSQL (pgvector)

🏷 Badges
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-Backend-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-Embeddings-green)
![Alembic](https://img.shields.io/badge/Alembic-Migrations-orange)
![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)
🧠 Overview

A production-grade Retrieval-Augmented Generation (RAG) chatbot built using Flask and PostgreSQL (pgvector), integrating OpenAI embeddings for semantic search.

This system enables:

Context-aware responses

Department-wise document management

Admin dashboard

Chat session persistence

User feedback tracking

Vector similarity search

Database schema migrations

Designed with scalability and production-readiness in mind.

🏗 System Architecture
🔁 RAG Flow Diagram

GitHub automatically renders this diagram.

🛠 Tech Stack
Layer	Technology
Backend	Flask
LLM	OpenAI API
Embeddings	OpenAI Embeddings
Vector DB	PostgreSQL + pgvector
ORM	SQLAlchemy
Migrations	Alembic
Frontend	Jinja Templates
Auth	Session-Based Authentication
Deployment Ready	Docker Compatible
🔥 Core Features
👤 User Capabilities

Secure Login

Context-aware Chat

Persistent Chat Sessions

Feedback Submission

Feedback History Tracking

🛠 Admin Capabilities

Admin Dashboard

Department-wise Document Upload

Knowledge Base Management

Query Monitoring

User Management

Feedback Review Interface

Basic Analytics

📂 Project Structure
rag_chatbot/
│
├── app.py
├── config.py
├── extensions.py
├── models.py
│
├── src/
│   ├── embeddings.py
│   ├── rag_chain.py
│   ├── pg_vectorstore.py
│   ├── vectorstore.py
│   └── data_loader.py
│
├── templates/
├── static/
├── migrations/
├── requirements.txt
└── .gitignore

Clean separation between:

Business logic

Vector operations

Database layer

Presentation layer

🐘 PostgreSQL Vector Configuration

Enable pgvector extension:

CREATE EXTENSION IF NOT EXISTS vector;

Example vector column:

embedding VECTOR(1536)
⚙️ Local Setup
1️⃣ Clone Repository
git clone https://github.com/surajsoni1319/rag-chatbot.git
cd rag-chatbot
2️⃣ Create Virtual Environment
python -m venv venv
venv\Scripts\activate
3️⃣ Install Dependencies
pip install -r requirements.txt
4️⃣ Configure Environment Variables

Create .env file:

OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://username:password@localhost:5432/ragdb
SECRET_KEY=your_secret_key

⚠️ Never commit .env file.

5️⃣ Run Database Migrations
alembic upgrade head
6️⃣ Run Application
python app.py

Access at:

http://localhost:5000
🔐 Security Considerations

API keys stored in environment variables

.env excluded via .gitignore

Database migrations controlled via Alembic

Admin routes separated from user routes

Feedback logging for monitoring system accuracy

📊 Database Schema Management

Using Alembic:

alembic revision --autogenerate -m "schema update"
alembic upgrade head
🚀 Production Readiness Highlights

✔ Vector search with PostgreSQL (pgvector)
✔ Structured RAG pipeline
✔ Modular code architecture
✔ Migration-controlled schema
✔ Admin management system
✔ Feedback-driven improvement loop
✔ Docker deployment ready

🧪 Example RAG Lifecycle

Admin uploads PDF

Document is chunked

Embeddings generated

Stored in PostgreSQL vector column

User query embedded

Similarity search retrieves context

LLM generates contextual answer

Feedback stored for improvement

📈 Future Enhancements

JWT Authentication

Redis Caching

Async Processing (Celery)

REST API endpoints

Rate Limiting

CI/CD Pipeline

Cloud Deployment (AWS / Azure)

Multi-tenant architecture
