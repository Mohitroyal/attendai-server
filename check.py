import MySQLdb
db = MySQLdb.connect(host='localhost', user='root', passwd='Mohith@123', db='attendance_system')
cur = db.cursor()
print('=== ADMIN TABLE ===')
cur.execute('SELECT id, username, password FROM admin')
for r in cur.fetchall():
    print(r)
print()
print('=== EMPLOYEES TABLE ===')
cur.execute('SELECT id, name, email FROM employees')
for r in cur.fetchall():
    print(r)
db.close()
