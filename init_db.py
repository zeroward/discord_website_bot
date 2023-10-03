import sqlite3

# Connect to SQLite and create table if it doesn't exist
conn = sqlite3.connect('websites.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS websites (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    description TEXT,
    updated_by TEXT,
    first_referenced TEXT,
    last_referenced TEXT,
    last_updated TEXT,
    reference_count INTEGER DEFAULT 0
)
''')
conn.commit()
conn.close()

