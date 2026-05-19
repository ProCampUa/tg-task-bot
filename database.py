import os
import psycopg2
from datetime import date, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            assignee TEXT,
            assignee_id BIGINT,
            deadline TEXT,
            status TEXT DEFAULT 'в работе',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            task_id INTEGER REFERENCES tasks(id),
            author TEXT,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_task(chat_id, title, assignee, assignee_id, deadline):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO tasks (chat_id, title, assignee, assignee_id, deadline) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (chat_id, title, assignee, assignee_id, deadline)
    )
    task_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return task_id

def complete_task(task_id, chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE tasks SET status='vypolneno' WHERE id=%s AND chat_id=%s",
        (task_id, chat_id)
    )
    rows = c.rowcount
    conn.commit()
    conn.close()
    return rows > 0

def get_completed_count(assignee, chat_id=None):
    conn = get_conn()
    c = conn.cursor()
    # Загальна статистика по всіх чатах
    c.execute(
        "SELECT COUNT(*) FROM tasks WHERE assignee=%s AND status='vypolneno'",
        (assignee,)
    )
    count = c.fetchone()[0]
    conn.close()
    return count

def get_top_performers(limit=3):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT assignee, COUNT(*) as total
        FROM tasks
        WHERE status='vypolneno' AND assignee IS NOT NULL AND assignee != '-'
        GROUP BY assignee
        ORDER BY total DESC
        LIMIT %s
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_tasks(chat_id, user_id=None):
    conn = get_conn()
    c = conn.cursor()
    if user_id:
        c.execute("SELECT * FROM tasks WHERE chat_id=%s AND assignee_id=%s ORDER BY deadline", (chat_id, user_id))
    else:
        c.execute("SELECT * FROM tasks WHERE chat_id=%s ORDER BY deadline", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_tasks_due_tomorrow(chat_id):
    conn = get_conn()
    c = conn.cursor()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    c.execute(
        "SELECT * FROM tasks WHERE chat_id=%s AND deadline=%s AND status != 'vypolneno'",
        (chat_id, tomorrow)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_chats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT chat_id FROM tasks")
    chats = [r[0] for r in c.fetchall()]
    conn.close()
    return chats

def get_report_data(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM tasks WHERE chat_id=%s GROUP BY status", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return dict(rows)

def add_comment(task_id, author, text):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO comments (task_id, author, text) VALUES (%s,%s,%s)",
        (task_id, author, text)
    )
    conn.commit()
    conn.close()

def get_comments(task_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT author, text FROM comments WHERE task_id=%s ORDER BY created_at", (task_id,))
    rows = c.fetchall()
    conn.close()
    return rows
