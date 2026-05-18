import sqlite3
from datetime import datetime

DB_PATH = "tasks.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            assignee TEXT,
            assignee_id INTEGER,
            deadline TEXT,
            status TEXT DEFAULT 'в работе',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_task(chat_id, title, assignee, assignee_id, deadline):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (chat_id, title, assignee, assignee_id, deadline) VALUES (?,?,?,?,?)",
        (chat_id, title, assignee, assignee_id, deadline)
    )
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id

def complete_task(task_id, chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE tasks SET status='выполнено' WHERE id=? AND chat_id=?",
        (task_id, chat_id)
    )
    rows = c.rowcount
    conn.commit()
    conn.close()
    return rows > 0

def get_tasks(chat_id, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute("SELECT * FROM tasks WHERE chat_id=? AND assignee_id=? ORDER BY deadline", (chat_id, user_id))
    else:
        c.execute("SELECT * FROM tasks WHERE chat_id=? ORDER BY deadline", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_tasks_due_tomorrow(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    from datetime import date, timedelta
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    c.execute(
        "SELECT * FROM tasks WHERE chat_id=? AND deadline=? AND status != 'выполнено'",
        (chat_id, tomorrow)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_chats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT chat_id FROM tasks")
    chats = [r[0] for r in c.fetchall()]
    conn.close()
    return chats

def get_report_data(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM tasks WHERE chat_id=? GROUP BY status", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return dict(rows)

def add_comment(task_id, author, text):
    import sqlite3
    conn = sqlite3.connect("tasks.db")
    conn.execute(
        "INSERT INTO comments (task_id, author, text) VALUES (?,?,?)",
        (task_id, author, text)
    )
    conn.commit()
    conn.close()

def get_comments(task_id):
    import sqlite3
    conn = sqlite3.connect("tasks.db")
    c = conn.cursor()
    c.execute("SELECT author, text FROM comments WHERE task_id=? ORDER BY created_at", (task_id,))
    rows = c.fetchall()
    conn.close()
    return rows
