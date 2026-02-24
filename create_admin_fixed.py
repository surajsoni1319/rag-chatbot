import psycopg2
from werkzeug.security import generate_password_hash

# Connect to Docker PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="rag_chatbot",
    user="postgres",
    password="postgres123"
)

cursor = conn.cursor()

# Check if admin exists
cursor.execute("SELECT id FROM \"user\" WHERE email = 'admin@starcement.co.in'")
existing = cursor.fetchone()

if existing:
    print("Admin user already exists. Updating password...")
    hashed_password = generate_password_hash("admin123")
    cursor.execute("""
        UPDATE "user" 
        SET password = %s, 
            name = 'System Administrator',
            role = 'admin',
            access_level = 'executive'
        WHERE email = 'admin@starcement.co.in'
    """, (hashed_password,))
    print("✅ Admin password updated!")
else:
    print("Creating new admin user...")
    hashed_password = generate_password_hash("admin123")
    cursor.execute("""
        INSERT INTO "user" (email, password, name, department, role, access_level)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, email, name, role, access_level;
    """, (
        'admin@starcement.co.in',
        hashed_password,
        'System Administrator',
        'admin',
        'admin',
        'executive'
    ))
    result = cursor.fetchone()
    print(f"✅ Admin user created!")
    print(f"ID: {result[0]}")
    print(f"Email: {result[1]}")
    print(f"Name: {result[2]}")
    print(f"Role: {result[3]}")
    print(f"Access Level: {result[4]}")

conn.commit()
cursor.close()
conn.close()

print("\n" + "="*60)
print("Login Credentials:")
print("  Email: admin@starcement.co.in")
print("  Password: admin123")
print("="*60)