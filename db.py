import sqlite3
import os
from datetime import datetime
import pandas as pd

# Use environment variable for DB path or default to data/ledger.db
DB_FILE = os.getenv("DATABASE_URL", "data/ledger.db")

def init_db():
    """Initializes the SQLite database with the transactions table."""
    # Ensure the directory exists
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            payee TEXT NOT NULL,
            item_name TEXT,
            invoice_number TEXT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            account TEXT NOT NULL,
            file_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Check if file_path column exists (migration for existing DBs)
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [column[1] for column in cursor.fetchall()]
    if "file_path" not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN file_path TEXT")
    if "item_name" not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN item_name TEXT")
    if "invoice_number" not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN invoice_number TEXT")
        
    conn.commit()
    conn.close()

def save_transaction(date, payee, amount, category, account, file_path=None, item_name=None, invoice_number=None):
    """Saves a single transaction to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (date, payee, item_name, invoice_number, amount, category, account, file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (date, payee, item_name, invoice_number, amount, category, account, file_path))
    conn.commit()
    conn.close()
    return True

def get_recent_transactions(limit=5):
    """Retrieves the most recent transactions."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(f"SELECT * FROM transactions ORDER BY date DESC, created_at DESC LIMIT {limit}", conn)
    conn.close()
    return df

def get_monthly_report(year, month):
    """Retrieves all transactions for a given year and month."""
    conn = sqlite3.connect(DB_FILE)
    # Format month to be two digits
    month_str = f"{int(month):02d}"
    query = "SELECT * FROM transactions WHERE date LIKE ? ORDER BY date ASC"
    df = pd.read_sql_query(query, conn, params=(f"{year}-{month_str}-%",))
    conn.close()
    return df

def get_available_months():
    """Returns a list of unique year-month strings available in the data."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT strftime('%Y-%m', date) as ym FROM transactions ORDER BY ym DESC")
    months = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return months

def get_unique_categories():
    """Returns a list of unique categories used in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM transactions ORDER BY category ASC")
    categories = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return categories

def get_unique_accounts():
    """Returns a list of unique accounts used in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT account FROM transactions ORDER BY account ASC")
    accounts = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return accounts

def delete_transaction(transaction_id):
    """Deletes a transaction from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()
    return True

def update_transaction(transaction_id, date, payee, amount, category, account, item_name=None, invoice_number=None):
    """Updates an existing transaction."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE transactions 
        SET date = ?, payee = ?, item_name = ?, invoice_number = ?, amount = ?, category = ?, account = ?
        WHERE id = ?
    """, (date, payee, item_name, invoice_number, amount, category, account, transaction_id))
    conn.commit()
    conn.close()
    return True

def run_query(query):
    """Executes an arbitrary SQL query and returns a DataFrame or success message."""
    conn = sqlite3.connect(DB_FILE)
    try:
        # Check if it's a SELECT query
        if query.strip().upper().startswith("SELECT") or query.strip().upper().startswith("PRAGMA"):
            df = pd.read_sql_query(query, conn)
            return df, None
        else:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            return f"Query executed successfully. Rows affected: {cursor.rowcount}", None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()
