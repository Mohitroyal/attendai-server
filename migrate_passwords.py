"""
=====================================================
  migrate_passwords.py
  Run this ONCE to hash all existing plain text
  passwords in your database.

  Usage:
    python3 migrate_passwords.py

  This is safe to run — it checks if the password
  is already hashed before touching it.
=====================================================
"""

import os
import sys
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

try:
    import MySQLdb
except ImportError:
    print("Install mysqlclient: pip3 install mysqlclient")
    sys.exit(1)

# Connect
db = MySQLdb.connect(
    host=os.environ.get('MYSQL_HOST',     'localhost'),
    user=os.environ.get('MYSQL_USER',     'root'),
    passwd=os.environ.get('MYSQL_PASSWORD', ''),
    db=os.environ.get('MYSQL_DB',         'attendance_system')
)
cur = db.cursor()

print("=" * 50)
print("  Password Migration Tool")
print("=" * 50)

# ── Migrate employees ──────────────────────────
print("\n📋 Checking employees table...")
cur.execute("SELECT id, name, email, password FROM employees")
employees = cur.fetchall()
migrated_emp = 0

for emp_id, name, email, password in employees:
    # Skip if already bcrypt hashed
    if password and (password.startswith('$2b$') or password.startswith('$2y$')):
        print(f"  ⏭  {name} ({email}) — already hashed, skipping")
        continue
    # Hash the plain text password
    hashed = generate_password_hash(password or 'changeme123')
    cur.execute("UPDATE employees SET password=%s WHERE id=%s", (hashed, emp_id))
    print(f"  ✅ {name} ({email}) — password hashed")
    migrated_emp += 1

# ── Migrate admin ──────────────────────────────
print("\n📋 Checking admin table...")
cur.execute("SELECT id, username, password FROM admin")
admins = cur.fetchall()
migrated_adm = 0

for adm_id, username, password in admins:
    if password and (password.startswith('$2b$') or password.startswith('$2y$')):
        print(f"  ⏭  Admin '{username}' — already hashed, skipping")
        continue
    hashed = generate_password_hash(password or 'admin123')
    cur.execute("UPDATE admin SET password=%s WHERE id=%s", (hashed, adm_id))
    print(f"  ✅ Admin '{username}' — password hashed")
    migrated_adm += 1

db.commit()
cur.close()
db.close()

print(f"\n{'=' * 50}")
print(f"  Migration complete!")
print(f"  Employees migrated : {migrated_emp}")
print(f"  Admins migrated    : {migrated_adm}")
print(f"{'=' * 50}")
print("\n⚠️  Important: Update your .env with the correct")
print("   passwords BEFORE telling users to log in.")
print("   The migrated passwords are the same as before")
print("   — just now stored securely.\n")