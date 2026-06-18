import sqlite3
from datetime import datetime

conn = sqlite3.connect('property_old.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY,
    room_number VARCHAR(50) UNIQUE,
    name VARCHAR(100),
    phone VARCHAR(20)
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    phone VARCHAR(20),
    fault_types TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    ticket_no VARCHAR(50) UNIQUE,
    room_number VARCHAR(50),
    description TEXT,
    fault_type VARCHAR(50),
    status VARCHAR(20) DEFAULT '待指派',
    assigned_worker_id INTEGER,
    created_at DATETIME,
    completed_at DATETIME,
    duration FLOAT,
    rating INTEGER,
    FOREIGN KEY (assigned_worker_id) REFERENCES workers(id)
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ticket_logs (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    action VARCHAR(50),
    operator VARCHAR(100),
    detail TEXT,
    created_at DATETIME,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    worker_id INTEGER NOT NULL,
    content TEXT,
    notify_type VARCHAR(50),
    created_at DATETIME,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (worker_id) REFERENCES workers(id)
)''')

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

cursor.execute("INSERT INTO tenants (room_number, name, phone) VALUES (?, ?, ?)",
               ('A101', '业主王', '13900139001'))
cursor.execute("INSERT INTO tenants (room_number, name, phone) VALUES (?, ?, ?)",
               ('B202', '业主李', '13900139002'))

cursor.execute("INSERT INTO workers (name, phone, fault_types) VALUES (?, ?, ?)",
               ('张师傅', '13800138001', '["水电", "照明"]'))
cursor.execute("INSERT INTO workers (name, phone, fault_types) VALUES (?, ?, ?)",
               ('李师傅', '13800138002', '["门禁"]'))

cursor.execute('''INSERT INTO tickets
    (ticket_no, room_number, description, fault_type, status, assigned_worker_id, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)''',
    ('GD202606180001', 'A101', '水管漏水', '水电', '待接单', 1, now))

cursor.execute('''INSERT INTO tickets
    (ticket_no, room_number, description, fault_type, status, assigned_worker_id, created_at, completed_at, duration, rating)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
    ('GD202606180002', 'B202', '灯不亮', '照明', '已完成', 1, now, now, 2.5, 5))

cursor.execute('''INSERT INTO notifications
    (ticket_id, worker_id, content, notify_type, created_at)
    VALUES (?, ?, ?, ?, ?)''',
    (1, 1, '您有新工单GD202606180001', '自动指派通知', now))

cursor.execute('''INSERT INTO notifications
    (ticket_id, worker_id, content, notify_type, created_at)
    VALUES (?, ?, ?, ?, ?)''',
    (2, 1, '您有新工单GD202606180002', '自动指派通知', now))

conn.commit()
conn.close()

print("旧版数据库创建完成: property_old.db")
print("表结构:")
conn = sqlite3.connect('property_old.db')
cursor = conn.cursor()
for table in ['tickets', 'notifications']:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    print(f"  {table}: {[c[1] for c in columns]}")
cursor.execute("SELECT COUNT(*) FROM tickets")
print(f"  tickets: {cursor.fetchone()[0]} 条")
cursor.execute("SELECT COUNT(*) FROM notifications")
print(f"  notifications: {cursor.fetchone()[0]} 条")
conn.close()
