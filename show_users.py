import MySQLdb
db = MySQLdb.connect(host='localhost', user='root', passwd='Mohith@123', db='attendance_system')
cur = db.cursor()
print('=== ADMIN ===')
cur.execute('SELECT id, username FROM admin')
for r in cur.fetchall():
    print(f'  ID:{r[0]}  Email: {r[1]}')
print()
print('=== EMPLOYEES ===')
cur.execute('SELECT id, name, email FROM employees')
for r in cur.fetchall():
    print(f'  ID:{r[0]}  Name:{r[1]}  Email:{r[2]}')
db.close()