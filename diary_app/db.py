import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "diary.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        color TEXT DEFAULT '#009CA6'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        is_done INTEGER DEFAULT 0,
        category_id INTEGER,
        alarm_time TEXT,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS memo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        content TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ddays
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     name
                     TEXT
                     NOT
                     NULL,
                     target_date
                     TEXT
                     NOT
                     NULL
                 )''')

    conn.commit()
    conn.close()

def get_todo_stats(year: int, month: int) -> tuple:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pattern = f"{year}-{month:02d}-%"
    c.execute("SELECT COUNT(*), SUM(is_done) FROM todos WHERE date LIKE ?", (pattern,))
    row = c.fetchone()
    conn.close()
    return (row[0] or 0, row[1] or 0)

def get_todo_stats_range(start: str, end: str) -> tuple:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(is_done) FROM todos WHERE date BETWEEN ? AND ?", (start, end))
    row = c.fetchone()
    conn.close()
    return (row[0] or 0, row[1] or 0)

def get_ddays() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM ddays ORDER BY target_date")
    result = c.fetchall()
    conn.close()
    return result

def add_dday(name: str, target_date: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO ddays (name, target_date) VALUES (?, ?)", (name, target_date))
    conn.commit()
    conn.close()

def delete_dday(did: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM ddays WHERE id = ?", (did,))
    conn.commit()
    conn.close()

def get_memos_for_month(year: int, month: int) -> dict:
    """해당 월의 모든 메모 반환 {날짜문자열: 내용}"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pattern = f"{year}-{month:02d}-%"
    c.execute("SELECT date, content FROM memo WHERE date LIKE ?", (pattern,))
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result

def get_memo(date_str: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT content FROM memo WHERE date = ?", (date_str,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def save_memo(date_str: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO memo (date, content) VALUES (?, ?)
                 ON CONFLICT(date) DO UPDATE SET content = excluded.content""",
              (date_str, content))
    conn.commit()
    conn.close()

def delete_memo(date_str: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM memo WHERE date = ?", (date_str,))
    conn.commit()
    conn.close()

def get_todos_for_week(date_str: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM todos WHERE date = ? ORDER BY is_done, id", (date_str,))
    result = c.fetchall()
    conn.close()
    return result

def add_todo(title: str, date_str: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO todos (title, date) VALUES (?, ?)", (title, date_str))
    conn.commit()
    conn.close()

def toggle_todo(todo_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE todos SET is_done = CASE WHEN is_done = 0 THEN 1 ELSE 0 END WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

def delete_todo(todo_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("DB 초기화 완료!")