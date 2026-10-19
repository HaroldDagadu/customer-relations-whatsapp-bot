import sqlite3
import logging
import hashlib
import os
from contextlib import contextmanager
from config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    db_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + db_hash.hex()


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, hash_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        db_hash = bytes.fromhex(hash_hex)
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_hash == db_hash
    except Exception:
        return False


def get_db_path():
    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        return db_url[len("sqlite:///"):]
    return "whatsapp.db"


def init_db():
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # --- Users Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT,
                is_human_chat INTEGER DEFAULT 0,
                location TEXT,
                town TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- Messages Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'admin')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_user_time
            ON messages(user_id, created_at)
        """)

        # Migration: drop biometric_included column from packages if present
        cursor.execute("PRAGMA table_info(packages)")
        pkg_columns = [row[1] for row in cursor.fetchall()]
        if "biometric_included" in pkg_columns:
            logger.info("Migrating packages: dropping biometric_included column...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS packages_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    schedule_type TEXT,
                    duration_weeks TEXT,
                    price REAL NOT NULL
                )
            """)
            cursor.execute("""
                INSERT INTO packages_new (id, name, description, schedule_type, duration_weeks, price)
                SELECT id, name, description, schedule_type, duration_weeks, price FROM packages
            """)
            cursor.execute("DROP TABLE packages")
            cursor.execute("ALTER TABLE packages_new RENAME TO packages")
            logger.info("Migration complete: biometric_included column removed from packages.")

        # Migrations check: drop old registrations if deprecated columns are present
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registrations'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(registrations)")
            columns = [row[1] for row in cursor.fetchall()]
            if "event_id" in columns or "email" in columns or "industry" in columns or "experience" in columns:
                logger.info("Migrating database: dropping old registrations table due to schema change...")
                cursor.execute("DROP TABLE IF EXISTS registrations")
                cursor.execute("DROP TABLE IF EXISTS events")
                cursor.execute("DROP TABLE IF EXISTS clients")
                cursor.execute("DROP TABLE IF EXISTS support_tickets")

        # --- Packages Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Non-Students',
                description TEXT,
                schedule_type TEXT,
                duration_weeks TEXT,
                price REAL NOT NULL
            )
        """)
        
        # Migration: Add category column if missing
        cursor.execute("PRAGMA table_info(packages)")
        pkg_columns = [row[1] for row in cursor.fetchall()]
        if "category" not in pkg_columns:
            logger.info("Migrating packages: adding category column...")
            cursor.execute("ALTER TABLE packages ADD COLUMN category TEXT NOT NULL DEFAULT 'Non-Students'")

        # --- Checkout Fees Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                mandatory INTEGER DEFAULT 1,
                pass_through INTEGER DEFAULT 0
            )
        """)

        # --- Registrations Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                package_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                name TEXT,
                dob TEXT,
                ghana_card TEXT,
                place_of_birth TEXT,
                witness_name TEXT,
                witness_phone TEXT,
                marital_status TEXT,
                location TEXT,
                payment_reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(package_id) REFERENCES packages(id) ON DELETE CASCADE
            )
        """)

        # --- Admin Users Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('super_admin', 'branch_admin')),
                location TEXT,
                must_reset_password INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- Admin Sessions Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(admin_id) REFERENCES admin_users(id) ON DELETE CASCADE
            )
        """)

        # --- Knowledge Base Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- Clients (Office Branches) Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                address TEXT,
                contact_numbers TEXT,
                google_maps_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # --- Support Tickets Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                description TEXT,
                location TEXT,
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'resolved', 'closed')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Migration: add location column to support_tickets if not present
        cursor.execute("PRAGMA table_info(support_tickets)")
        ticket_columns = [row[1] for row in cursor.fetchall()]
        if ticket_columns and "location" not in ticket_columns:
            logger.info("Migrating support_tickets: adding location column...")
            cursor.execute("ALTER TABLE support_tickets ADD COLUMN location TEXT")

        # Migration: add town column to users if not present
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in cursor.fetchall()]
        if user_columns and "town" not in user_columns:
            logger.info("Migrating users: adding town column...")
            cursor.execute("ALTER TABLE users ADD COLUMN town TEXT")

        # --- Broadcasts Table ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                sent_by INTEGER NOT NULL,
                recipient_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(sent_by) REFERENCES admin_users(id) ON DELETE SET NULL
            )
        """)

        # --- Seed Default Clients/Branches ---
        cursor.execute("SELECT COUNT(*) FROM clients")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO clients (name, region, contact_numbers, address, google_maps_link) VALUES (?, ?, ?, ?, ?)",
                ("Central Branch", "Region A", "+000 200 000 0001", "1 High Street, City Centre", "https://maps.google.com/?q=Central+Branch")
            )
            cursor.execute(
                "INSERT INTO clients (name, region, contact_numbers, address, google_maps_link) VALUES (?, ?, ?, ?, ?)",
                ("East Branch", "Region B", "+000 200 000 0002", "25 Market Road, Eastside", "https://maps.google.com/?q=East+Branch")
            )
            cursor.execute(
                "INSERT INTO clients (name, region, contact_numbers, address, google_maps_link) VALUES (?, ?, ?, ?, ?)",
                ("West Branch", "Region C", "+000 200 000 0003", "8 Station Avenue, Westend", "https://maps.google.com/?q=West+Branch")
            )
            cursor.execute(
                "INSERT INTO clients (name, region, contact_numbers, address, google_maps_link) VALUES (?, ?, ?, ?, ?)",
                ("North Branch", "Region D", "+000 200 000 0004", "40 Hilltop Close, Northgate", "https://maps.google.com/?q=North+Branch")
            )

        # --- Seed Default Packages ---
        cursor.execute("SELECT COUNT(*) FROM packages")
        if cursor.fetchone()[0] == 0:
            packages = [
                ("Basic Package", "Entry-level package with standard features.", "Flexible", "4", 100.00),
                ("Standard Package", "Mid-tier package covering most needs.", "Combined", "6", 250.00),
                ("Express Package", "Fast-track package for quicker completion.", "Weekdays", "3", 500.00),
                ("Premium Package", "Top-tier package with all features included.", "Flexible", "8", 750.00),
            ]
            cursor.executemany("""
                INSERT INTO packages (name, description, schedule_type, duration_weeks, price)
                VALUES (?, ?, ?, ?, ?)
            """, packages)

        # --- Seed Default Fees ---
        cursor.execute("SELECT COUNT(*) FROM fees")
        if cursor.fetchone()[0] == 0:
            fees = [
                ("Registration Fee", "Mandatory one-off onboarding fee.", 50.0, 1, 1),
                ("Documentation Fee", "Mandatory fee for document processing.", 75.0, 1, 1),
                ("Equipment Rental", "Optional equipment rental for the final session.", 150.0, 0, 0),
            ]
            cursor.executemany("""
                INSERT INTO fees (name, description, amount, mandatory, pass_through)
                VALUES (?, ?, ?, ?, ?)
            """, fees)

        # --- Seed Default Super Admin (username: admin, password: admin123) ---
        cursor.execute("SELECT COUNT(*) FROM admin_users WHERE username = ?", ("admin",))
        if cursor.fetchone()[0] == 0:
            pw_hash = hash_password("admin123")
            cursor.execute("""
                INSERT INTO admin_users (username, password_hash, role, location, must_reset_password)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", pw_hash, "super_admin", None, 0))

        conn.commit()
        logger.info("Database initialized successfully.")


@contextmanager
def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


# Initialize DB on import
init_db()
