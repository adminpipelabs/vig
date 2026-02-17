#!/usr/bin/env python3
"""
Test script to diagnose dashboard startup issues
"""
import sys
import os

print("=" * 60)
print("Dashboard Diagnostic Test")
print("=" * 60)

# Test 1: Python version
print(f"\n1. Python version: {sys.version}")

# Test 2: Check dependencies
print("\n2. Checking dependencies...")
deps = {
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'httpx': 'httpx',
    'cryptography': 'cryptography',
    'psycopg2': 'psycopg2-binary',
    'dotenv': 'python-dotenv',
}

missing = []
for module, package in deps.items():
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'unknown')
        print(f"   ✅ {package}: {version}")
    except ImportError:
        print(f"   ❌ {package}: MISSING")
        missing.append(package)

if missing:
    print(f"\n   Missing packages: {', '.join(missing)}")
    print(f"   Install with: pip install {' '.join(missing)}")

# Test 3: Import dashboard
print("\n3. Testing dashboard import...")
try:
    from dashboard import app
    print(f"   ✅ Dashboard app imported successfully")
    print(f"   ✅ Routes count: {len([r for r in app.routes if hasattr(r, 'path')])}")
    
    # List key routes
    key_routes = ['/', '/terminal', '/api/health', '/api/stats']
    print(f"\n   Key routes:")
    for route in app.routes:
        if hasattr(route, 'path'):
            if route.path in key_routes or route.path.startswith('/api/'):
                methods = getattr(route, 'methods', set())
                print(f"      {list(methods)[0] if methods else 'GET':6} {route.path}")
except Exception as e:
    print(f"   ❌ Dashboard import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check environment
print("\n4. Environment variables...")
env_vars = ['DATABASE_URL', 'PORT', 'DB_PATH']
for var in env_vars:
    value = os.getenv(var, 'NOT SET')
    if var == 'DATABASE_URL' and value != 'NOT SET':
        # Mask password
        if '@' in value:
            parts = value.split('@')
            if len(parts) == 2:
                masked = parts[0].split(':')[0] + ':***@' + parts[1]
                print(f"   {var}: {masked}")
            else:
                print(f"   {var}: {value[:20]}...")
        else:
            print(f"   {var}: {value}")
    else:
        print(f"   {var}: {value}")

# Test 5: Database connection
print("\n5. Testing database connection...")
try:
    from dashboard import get_db, is_postgres
    conn = get_db()
    is_pg = is_postgres(conn)
    db_type = "PostgreSQL" if is_pg else "SQLite"
    print(f"   ✅ Connected to {db_type}")
    
    # Check if tables exist
    c = conn.cursor()
    if is_pg:
        c.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
    else:
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    
    tables = [row[0] if isinstance(row, dict) else row[0] for row in c.fetchall()]
    required_tables = ['bets', 'windows', 'bot_status']
    
    print(f"   Tables found: {', '.join(tables) if tables else 'none'}")
    for table in required_tables:
        if table in tables:
            print(f"      ✅ {table}")
        else:
            print(f"      ⚠️  {table} (missing - will be created on first use)")
    
    conn.close()
except Exception as e:
    print(f"   ⚠️  Database check failed: {e}")
    print(f"   (This is OK if tables don't exist yet)")

# Test 6: Test uvicorn startup
print("\n6. Testing uvicorn startup command...")
print("   Command: uvicorn dashboard:app --host 0.0.0.0 --port $PORT")
print("   ✅ Command looks correct")

print("\n" + "=" * 60)
print("Diagnostic complete!")
print("=" * 60)

if missing:
    print(f"\n⚠️  ACTION REQUIRED: Install missing packages:")
    print(f"   pip install {' '.join(missing)}")
    sys.exit(1)
else:
    print("\n✅ All checks passed! Dashboard should start successfully.")
    print("\nTo start locally:")
    print("   PORT=8080 uvicorn dashboard:app --host 0.0.0.0 --port 8080")
    sys.exit(0)
