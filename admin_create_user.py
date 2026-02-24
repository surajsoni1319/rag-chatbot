from app import app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    email = input("Email: ")
    password = input("Password: ")
    department = input("Department: ").strip().lower()

    user = User(
        email=email,
        password=generate_password_hash(password),
        department=department
    )
    db.session.add(user)
    db.session.commit()
    print("User created")
