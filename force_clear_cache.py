import sys
import os
import shutil

print("=" * 60)
print("FORCE CACHE CLEAR AND MODULE RELOAD")
print("=" * 60)

# Step 1: Find and delete all __pycache__ folders
print("\n1. Deleting all __pycache__ folders...")
project_root = r"D:\rag_chatbot"
deleted_count = 0

for root, dirs, files in os.walk(project_root):
    if '__pycache__' in dirs:
        cache_dir = os.path.join(root, '__pycache__')
        try:
            shutil.rmtree(cache_dir)
            print(f"   ✓ Deleted: {cache_dir}")
            deleted_count += 1
        except Exception as e:
            print(f"   ✗ Failed: {cache_dir} - {e}")

print(f"\nDeleted {deleted_count} __pycache__ folders")

# Step 2: Delete all .pyc files
print("\n2. Deleting all .pyc files...")
pyc_count = 0

for root, dirs, files in os.walk(project_root):
    for file in files:
        if file.endswith('.pyc'):
            pyc_file = os.path.join(root, file)
            try:
                os.remove(pyc_file)
                print(f"   ✓ Deleted: {pyc_file}")
                pyc_count += 1
            except Exception as e:
                print(f"   ✗ Failed: {pyc_file} - {e}")

print(f"\nDeleted {pyc_count} .pyc files")

# Step 3: Check if pg_vectorstore is currently loaded
print("\n3. Checking loaded modules...")
pg_modules = [key for key in sys.modules.keys() if 'pg_vectorstore' in key.lower()]
if pg_modules:
    print(f"   Found loaded modules: {pg_modules}")
    for mod in pg_modules:
        del sys.modules[mod]
        print(f"   ✓ Unloaded: {mod}")
else:
    print("   No pg_vectorstore modules currently loaded")

# Step 4: Verify the file
print("\n4. Verifying pg_vectorstore.py file...")
pg_file = r"D:\rag_chatbot\src\pg_vectorstore.py"

if os.path.exists(pg_file):
    file_size = os.path.getsize(pg_file)
    print(f"   File exists: {pg_file}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    
    if file_size < 30000:
        print("   ⚠️  WARNING: File seems too small!")
    elif file_size > 100000:
        print("   ⚠️  WARNING: File seems too large (might have old code)!")
    else:
        print("   ✓ File size looks good")
    
    # Check the SQL syntax in file
    with open(pg_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if '%(dept)s' in content:
            print("   ❌ ERROR: File contains OLD syntax %(param)s")
            print("   You MUST replace this file with pg_vectorstore_HYBRID.py")
        elif ':dept' in content:
            print("   ✓ File contains CORRECT syntax :param")
        else:
            print("   ⚠️  WARNING: Cannot verify SQL syntax")
else:
    print(f"   ❌ ERROR: File not found at {pg_file}")

print("\n" + "=" * 60)
print("CLEANUP COMPLETE!")
print("=" * 60)
print("\nNEXT STEPS:")
print("1. If file has OLD syntax, replace it with pg_vectorstore_HYBRID.py")
print("2. Close ALL terminal windows")
print("3. Open a NEW terminal")
print("4. Run: python app.py")
print("\nPress Enter to exit...")
input()
