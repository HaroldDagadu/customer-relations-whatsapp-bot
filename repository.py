"""
Data Access Layer — Repository pattern for all database and JSON file operations.
"""
import json
import os
import logging
from datetime import datetime
from database import get_db_connection

logger = logging.getLogger(__name__)

# --- JSON File Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRANCHES_FILE = os.path.join(BASE_DIR, "branches.json")
PACKAGES_FILE = os.path.join(BASE_DIR, "packages.json")
FEES_FILE = os.path.join(BASE_DIR, "fees.json")


def load_json_file(filepath: str, default_val: list) -> list:
    if not os.path.exists(filepath):
        write_json_file(filepath, default_val)
        return default_val
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_val


def write_json_file(filepath: str, data: list):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error writing to {filepath}: {e}")


def init_json_databases():
    """Initialize JSON databases with default seed data if they don't exist."""
    if not os.path.exists(BRANCHES_FILE):
        branches = [
            {"id": 1, "name": "Central Branch", "region": "Region A", "contact_numbers": "+000 200 000 0001", "address": "1 High Street, City Centre", "google_maps_link": "https://maps.google.com/?q=Central+Branch"},
            {"id": 2, "name": "East Branch", "region": "Region B", "contact_numbers": "+000 200 000 0002", "address": "25 Market Road, Eastside", "google_maps_link": "https://maps.google.com/?q=East+Branch"},
            {"id": 3, "name": "West Branch", "region": "Region C", "contact_numbers": "+000 200 000 0003", "address": "8 Station Avenue, Westend", "google_maps_link": "https://maps.google.com/?q=West+Branch"},
            {"id": 4, "name": "North Branch", "region": "Region D", "contact_numbers": "+000 200 000 0004", "address": "40 Hilltop Close, Northgate", "google_maps_link": "https://maps.google.com/?q=North+Branch"},
        ]
        write_json_file(BRANCHES_FILE, branches)

    if not os.path.exists(PACKAGES_FILE):
        packages = [
            {"id": 1, "name": "Basic Package", "description": "Entry-level package with standard features.", "schedule_type": "Flexible", "duration_weeks": "4", "price": 100.00},
            {"id": 2, "name": "Standard Package", "description": "Mid-tier package covering most needs.", "schedule_type": "Combined", "duration_weeks": "6", "price": 250.00},
            {"id": 3, "name": "Express Package", "description": "Fast-track package for quicker completion.", "schedule_type": "Weekdays", "duration_weeks": "3", "price": 500.00},
            {"id": 4, "name": "Premium Package", "description": "Top-tier package with all features included.", "schedule_type": "Flexible", "duration_weeks": "8", "price": 750.00},
        ]
        write_json_file(PACKAGES_FILE, packages)

    if not os.path.exists(FEES_FILE):
        fees = [
            {"id": 1, "name": "Registration Fee", "description": "Mandatory one-off onboarding fee.", "amount": 50.0, "mandatory": True, "pass_through": True},
            {"id": 2, "name": "Documentation Fee", "description": "Mandatory fee for document processing.", "amount": 75.0, "mandatory": True, "pass_through": True},
            {"id": 3, "name": "Equipment Rental", "description": "Optional equipment rental for the final session.", "amount": 150.0, "mandatory": False, "pass_through": False},
        ]
        write_json_file(FEES_FILE, fees)


init_json_databases()


class Repository:
    # ==========================================
    # User Operations
    # ==========================================
    @staticmethod
    def get_or_create_user(phone_number: str, name: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,))
            user = cursor.fetchone()
            if user:
                return dict(user)
            cursor.execute("INSERT INTO users (phone_number, name) VALUES (?, ?)", (phone_number, name))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,))
            return dict(cursor.fetchone())

    @staticmethod
    def get_user_by_id(user_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            return dict(user) if user else None

    @staticmethod
    def get_user_by_phone(phone: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE phone_number = ?", (phone,))
            user = cursor.fetchone()
            return dict(user) if user else None

    @staticmethod
    def update_user_human_chat(user_id: int, is_human_chat: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_human_chat = ? WHERE id = ?", (is_human_chat, user_id))
            conn.commit()

    @staticmethod
    def update_user_location(user_id: int, location: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET location = ? WHERE id = ?", (location, user_id))
            conn.commit()

    @staticmethod
    def update_user_town(user_id: int, town: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET town = ? WHERE id = ?", (town, user_id))
            conn.commit()

    @staticmethod
    def update_user_town_and_location(user_id: int, town: str, location: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET town = ?, location = ? WHERE id = ?", (town, location, user_id))
            conn.commit()
            
    @staticmethod
    def update_lead_status(phone_number: str, lead_status: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET lead_status = ? WHERE phone_number = ?", (lead_status, phone_number))
            conn.commit()

    @staticmethod
    def update_lead_analysis(phone_number: str, lead_status: str, ai_analysis: str, ai_next_steps: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET lead_status = ?, ai_analysis = ?, ai_next_steps = ? 
                WHERE phone_number = ?
            """, (lead_status, ai_analysis, ai_next_steps, phone_number))
            conn.commit()

    # ==========================================
    # Message Operations
    # ==========================================
    @staticmethod
    def log_message(user_id: int, role: str, content: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
            conn.commit()

    @staticmethod
    def get_user_messages(user_id: int, limit: int = 50, since: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if since:
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE user_id = ? AND created_at > ? 
                    ORDER BY created_at ASC 
                    LIMIT ?
                """, (user_id, since, limit))
                return [dict(row) for row in cursor.fetchall()]
            else:
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (user_id, limit))
                rows = [dict(row) for row in cursor.fetchall()]
                rows.reverse()
                return rows

    @staticmethod
    def get_recent_context_messages(user_id: int, limit: int = 20):
        """Fetch recent messages suitable for LLM context, with filtering and
        limiting done at the database level. Excludes flow-registration stubs,
        flow-ticket stubs, empty content, and admin messages."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages
                WHERE user_id = ?
                  AND role IN ('user', 'assistant')
                  AND content IS NOT NULL
                  AND content != ''
                  AND content NOT LIKE '[Flow Registration]%'
                  AND content NOT LIKE '[Flow Ticket]%'
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    # ==========================================
    # Chat List Operations
    # ==========================================
    @staticmethod
    def get_chats_list(location: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if location:
                cursor.execute("""
                    SELECT u.*,
                           (SELECT content FROM messages WHERE user_id = u.id ORDER BY created_at DESC LIMIT 1) as last_message,
                           (SELECT created_at FROM messages WHERE user_id = u.id ORDER BY created_at DESC LIMIT 1) as last_message_time
                    FROM users u WHERE u.location = ? ORDER BY last_message_time DESC
                """, (location,))
            else:
                cursor.execute("""
                    SELECT u.*,
                           (SELECT content FROM messages WHERE user_id = u.id ORDER BY created_at DESC LIMIT 1) as last_message,
                           (SELECT created_at FROM messages WHERE user_id = u.id ORDER BY created_at DESC LIMIT 1) as last_message_time
                    FROM users u ORDER BY last_message_time DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    # ==========================================
    # Admin Auth Operations
    # ==========================================
    @staticmethod
    def get_admin_by_username(username: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admin_users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_admin_by_session_token(token: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT au.* FROM admin_users au
                JOIN admin_sessions s ON au.id = s.admin_id
                WHERE s.token = ? AND (s.expires_at IS NULL OR s.expires_at > datetime('now'))
            """, (token,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_admin_session(admin_id: int, token: str, expires_at: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO admin_sessions (admin_id, token, expires_at) VALUES (?, ?, ?)", (admin_id, token, expires_at))
            conn.commit()

    @staticmethod
    def delete_admin_session(token: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
            conn.commit()

    @staticmethod
    def get_admins():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role, location, created_at FROM admin_users")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def create_admin(username: str, password_hash: str, role: str, location: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO admin_users (username, password_hash, role, location, must_reset_password) VALUES (?, ?, ?, ?, 1)", (username, password_hash, role, location))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_admin_password(admin_id: int, new_password_hash: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE admin_users SET password_hash=?, must_reset_password=0 WHERE id=?", (new_password_hash, admin_id))
            conn.commit()

    @staticmethod
    def update_admin(admin_id: int, username: str, role: str, location: str = None, password_hash: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if password_hash:
                cursor.execute("UPDATE admin_users SET username=?, role=?, location=?, password_hash=? WHERE id=?", (username, role, location, password_hash, admin_id))
            else:
                cursor.execute("UPDATE admin_users SET username=?, role=?, location=? WHERE id=?", (username, role, location, admin_id))
            conn.commit()

    @staticmethod
    def delete_admin(admin_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admin_users WHERE id = ?", (admin_id,))
            conn.commit()

    # ==========================================
    # Branch / Client CRUD
    # ==========================================
    # ==========================================
    # Branch / Client CRUD
    # ==========================================
    @staticmethod
    def get_clients():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_client_by_id(client_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_client(name, region, contact_numbers=None, address=None, google_maps_link=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clients (name, region, contact_numbers, address, google_maps_link)
                VALUES (?, ?, ?, ?, ?)
            """, (name, region, contact_numbers, address, google_maps_link))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_client(client_id, name, region, contact_numbers=None, address=None, google_maps_link=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE clients SET name=?, region=?, contact_numbers=?, address=?, google_maps_link=?
                WHERE id=?
            """, (name, region, contact_numbers, address, google_maps_link, client_id))
            conn.commit()

    @staticmethod
    def delete_client(client_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            conn.commit()

    # ==========================================
    # Packages CRUD
    # ==========================================
    @staticmethod
    def get_packages():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_package_by_id(package_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages WHERE id = ?", (package_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_package(name, category, description, schedule_type, duration_weeks, price):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO packages (name, category, description, schedule_type, duration_weeks, price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, category, description, schedule_type, duration_weeks, price))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_package(package_id, name, category, description, schedule_type, duration_weeks, price):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE packages SET name=?, category=?, description=?, schedule_type=?, duration_weeks=?, price=?
                WHERE id=?
            """, (name, category, description, schedule_type, duration_weeks, price, package_id))
            conn.commit()

    @staticmethod
    def delete_package(package_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM packages WHERE id = ?", (package_id,))
            conn.commit()

    # ==========================================
    # Add-On Fees CRUD
    # ==========================================
    @staticmethod
    def get_fees():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fees ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_fee_by_id(fee_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fees WHERE id = ?", (fee_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_fee(name, description, amount, mandatory, pass_through):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fees (name, description, amount, mandatory, pass_through)
                VALUES (?, ?, ?, ?, ?)
            """, (name, description, amount, 1 if mandatory else 0, 1 if pass_through else 0))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_fee(fee_id, name, description, amount, mandatory, pass_through):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE fees SET name=?, description=?, amount=?, mandatory=?, pass_through=?
                WHERE id=?
            """, (name, description, amount, 1 if mandatory else 0, 1 if pass_through else 0, fee_id))
            conn.commit()

    @staticmethod
    def delete_fee(fee_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fees WHERE id = ?", (fee_id,))
            conn.commit()

    # ==========================================
    # Knowledge Base CRUD
    # ==========================================
    @staticmethod
    def get_knowledge_base():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knowledge_base ORDER BY topic")
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_knowledge_by_id(kb_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM knowledge_base WHERE id = ?", (kb_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_knowledge(topic, content, source_file=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO knowledge_base (topic, content, source_file) VALUES (?, ?, ?)", (topic, content, source_file))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_knowledge(kb_id, topic, content):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE knowledge_base SET topic=?, content=? WHERE id=?", (topic, content, kb_id))
            conn.commit()

    @staticmethod
    def delete_knowledge(kb_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM knowledge_base WHERE id = ?", (kb_id,))
            conn.commit()

    # ==========================================
    # Support Tickets
    # ==========================================
    @staticmethod
    def get_tickets(location: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if location:
                cursor.execute("""
                    SELECT t.*, u.phone_number, u.name as user_name FROM support_tickets t
                    JOIN users u ON t.user_id = u.id 
                    WHERE t.location = ? OR (t.location IS NULL AND u.location = ?) 
                    ORDER BY t.created_at DESC
                """, (location, location))
            else:
                cursor.execute("""
                    SELECT t.*, u.phone_number, u.name as user_name FROM support_tickets t
                    JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_ticket_by_id(ticket_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_ticket(user_id, subject, description=None, location=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO support_tickets (user_id, subject, description, location) VALUES (?, ?, ?, ?)", (user_id, subject, description, location))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_ticket_status(ticket_id, status):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE support_tickets SET status = ? WHERE id = ?", (status, ticket_id))
            conn.commit()

    @staticmethod
    def update_ticket_full(ticket_id, subject, description, status, location=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE support_tickets SET subject=?, description=?, status=?, location=? WHERE id=?", (subject, description, status, location, ticket_id))
            conn.commit()

    @staticmethod
    def delete_ticket(ticket_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
            conn.commit()

    # ==========================================
    # Broadcasts
    # ==========================================
    @staticmethod
    def get_broadcasts():
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.*, au.username as sent_by_name FROM broadcasts b
                LEFT JOIN admin_users au ON b.sent_by = au.id
                ORDER BY b.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def create_broadcast(message, sent_by, recipient_count):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO broadcasts (message, sent_by, recipient_count) VALUES (?, ?, ?)", (message, sent_by, recipient_count))
            conn.commit()
            return cursor.lastrowid

    # ==========================================
    # Registrations
    # ==========================================
    @staticmethod
    def get_registrations_filtered(location=None, status=None, package_id=None, search=None, start_date=None, end_date=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.*, u.phone_number, u.name as user_name, u.location as user_location,
                       p.name as package_name, p.price
                FROM registrations r
                JOIN users u ON r.user_id = u.id
                JOIN packages p ON r.package_id = p.id
                WHERE 1=1
            """
            params = []
            if location:
                query += " AND r.location = ?"
                params.append(location)
            if status:
                query += " AND r.status = ?"
                params.append(status)
            if package_id:
                query += " AND r.package_id = ?"
                params.append(package_id)
            if search:
                query += " AND (u.name LIKE ? OR u.phone_number LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            if start_date:
                query += " AND r.created_at >= ?"
                params.append(f"{start_date} 00:00:00")
            if end_date:
                query += " AND r.created_at <= ?"
                params.append(f"{end_date} 23:59:59")
            query += " ORDER BY r.created_at DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_unique_registered_users(location=None, search=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT u.id, u.phone_number, u.name, u.location, u.town, u.created_at
                FROM users u JOIN registrations r ON u.id = r.user_id WHERE 1=1
            """
            params = []
            if location:
                query += " AND u.location = ?"
                params.append(location)
            if search:
                query += " AND (u.name LIKE ? OR u.phone_number LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_registration_by_reference(payment_reference: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM registrations WHERE payment_reference = ?", (payment_reference,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_registration_by_id(reg_id: int):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, u.phone_number, u.name as user_name, u.location as user_location,
                       p.name as package_name, p.price
                FROM registrations r
                JOIN users u ON r.user_id = u.id
                JOIN packages p ON r.package_id = p.id
                WHERE r.id = ?
            """, (reg_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_registration(user_id, package_id, status='pending', name=None, dob=None, ghana_card=None, place_of_birth=None, witness_name=None, witness_phone=None, marital_status=None, location=None, payment_reference=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO registrations (user_id, package_id, status, name, dob, ghana_card, place_of_birth, witness_name, witness_phone, marital_status, location, payment_reference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, package_id, status, name, dob, ghana_card, place_of_birth, witness_name, witness_phone, marital_status, location, payment_reference))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def update_registration_full(reg_id, package_id, status, name=None, dob=None, ghana_card=None, place_of_birth=None, witness_name=None, witness_phone=None, marital_status=None, location=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE registrations 
                SET package_id=?, status=?, name=?, dob=?, ghana_card=?, place_of_birth=?, witness_name=?, witness_phone=?, marital_status=?, location=?
                WHERE id=?
            """, (package_id, status, name, dob, ghana_card, place_of_birth, witness_name, witness_phone, marital_status, location, reg_id))
            conn.commit()

    @staticmethod
    def delete_registration(reg_id):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
            conn.commit()

    @staticmethod
    def update_registration_status(registration_id, status, payment_reference=None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if payment_reference:
                cursor.execute("UPDATE registrations SET status=?, payment_reference=? WHERE id=?", (status, payment_reference, registration_id))
            else:
                cursor.execute("UPDATE registrations SET status=? WHERE id=?", (status, registration_id))
            conn.commit()

    # ==========================================
    # Overview / Metrics
    # ==========================================
    @staticmethod
    def get_overview_metrics(location: str = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()

            def q(base, where_clause="", params=()):
                sql = base + (" WHERE " + where_clause if where_clause else "")
                cursor.execute(sql, params)
                return cursor.fetchone()[0]

            loc_filter = "u.location = ?" if location else None
            loc_params = (location,) if location else ()

            # Total users
            global_total_users = q("SELECT COUNT(*) FROM users")
            if location:
                total_users = q("SELECT COUNT(*) FROM users", "location = ?", loc_params)
            else:
                total_users = global_total_users

            # Active chats today (users who sent a message today)
            if location:
                cursor.execute("""
                    SELECT COUNT(DISTINCT m.user_id) FROM messages m
                    JOIN users u ON m.user_id = u.id
                    WHERE m.created_at >= date('now') AND u.location = ?
                """, loc_params)
            else:
                cursor.execute("SELECT COUNT(DISTINCT user_id) FROM messages WHERE created_at >= date('now')")
            active_chats_today = cursor.fetchone()[0]

            # Messages last 24h
            if location:
                cursor.execute("""
                    SELECT COUNT(*) FROM messages m JOIN users u ON m.user_id = u.id
                    WHERE m.created_at >= datetime('now', '-1 day') AND u.location = ?
                """, loc_params)
            else:
                cursor.execute("SELECT COUNT(*) FROM messages WHERE created_at >= datetime('now', '-1 day')")
            messages_24h = cursor.fetchone()[0]

            # Total registrations
            if location:
                cursor.execute("""
                    SELECT COUNT(*) FROM registrations r JOIN users u ON r.user_id = u.id WHERE u.location = ?
                """, loc_params)
            else:
                cursor.execute("SELECT COUNT(*) FROM registrations")
            total_registrations = cursor.fetchone()[0]

            # Total revenue
            if location:
                cursor.execute("""
                    SELECT COALESCE(SUM(p.price), 0) FROM registrations r
                    JOIN users u ON r.user_id = u.id JOIN packages p ON r.package_id = p.id
                    WHERE u.location = ? AND r.status = 'confirmed'
                """, loc_params)
            else:
                cursor.execute("""
                    SELECT COALESCE(SUM(p.price), 0) FROM registrations r
                    JOIN packages p ON r.package_id = p.id WHERE r.status = 'confirmed'
                """)
            total_revenue = float(cursor.fetchone()[0])

            # Open tickets
            if location:
                cursor.execute("""
                    SELECT COUNT(*) FROM support_tickets t JOIN users u ON t.user_id = u.id
                    WHERE u.location = ? AND t.status = 'open'
                """, loc_params)
            else:
                cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
            open_tickets = cursor.fetchone()[0]

            # Total broadcasts
            cursor.execute("SELECT COUNT(*) FROM broadcasts")
            total_broadcasts = cursor.fetchone()[0]

        return {
            "total_users": total_users,
            "global_total_users": global_total_users,
            "active_chats_today": active_chats_today,
            "messages_24h": messages_24h,
            "total_registrations": total_registrations,
            "total_revenue": total_revenue,
            "open_tickets": open_tickets,
            "total_broadcasts": total_broadcasts,
        }

    @staticmethod
    def get_message_trend(days: int = 7):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM messages
                WHERE created_at >= date('now', '-{days} days')
                GROUP BY date(created_at)
                ORDER BY day ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_message_analytics(start_date: str, end_date: str, direction: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            conditions = ["date(created_at) >= ?", "date(created_at) <= ?"]
            params = [start_date, end_date]
            
            if direction == 'received':
                conditions.append("role = 'user'")
            elif direction == 'sent':
                conditions.append("role IN ('assistant', 'admin')")
                
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT COUNT(*) as total_messages, COUNT(DISTINCT user_id) as unique_users
                FROM messages
                WHERE {where_clause}
            """, params)
            totals = dict(cursor.fetchone())
            
            cursor.execute(f"""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM messages
                WHERE {where_clause}
                GROUP BY date(created_at)
                ORDER BY day ASC
            """, params)
            trend = [dict(row) for row in cursor.fetchall()]
            
            return {
                "totals": totals,
                "trend": trend
            }
    @staticmethod
    def get_registration_trend(days: int = 7):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM registrations
                WHERE created_at >= date('now', '-{days} days')
                GROUP BY date(created_at)
                ORDER BY day ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_registration_analytics(start_date: str, end_date: str, status: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            conditions = ["date(created_at) >= ?", "date(created_at) <= ?"]
            params = [start_date, end_date]
            
            if status != 'all':
                conditions.append("status = ?")
                params.append(status)
                
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT COUNT(*) as total_registrations
                FROM registrations
                WHERE {where_clause}
            """, params)
            totals = dict(cursor.fetchone())
            
            # Additional metric: Pending in this range (regardless of filter, maybe useful, but let's just stick to the filtered total and unique users? For registrations, total is fine.)
            cursor.execute(f"""
                SELECT COUNT(*) as pending_registrations
                FROM registrations
                WHERE status = 'pending' AND date(created_at) >= ? AND date(created_at) <= ?
            """, [start_date, end_date])
            pending = cursor.fetchone()['pending_registrations']
            totals['pending_registrations'] = pending

            cursor.execute(f"""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM registrations
                WHERE {where_clause}
                GROUP BY date(created_at)
                ORDER BY day ASC
            """, params)
            trend = [dict(row) for row in cursor.fetchall()]
            
            return {
                "totals": totals,
                "trend": trend
            }

    @staticmethod
    def get_ticket_analytics(start_date: str, end_date: str, status: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            conditions = ["date(created_at) >= ?", "date(created_at) <= ?"]
            params = [start_date, end_date]
            
            if status != 'all':
                conditions.append("status = ?")
                params.append(status)
                
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT COUNT(*) as total_tickets
                FROM support_tickets
                WHERE {where_clause}
            """, params)
            totals = dict(cursor.fetchone())
            
            cursor.execute(f"""
                SELECT COUNT(*) as open_tickets
                FROM support_tickets
                WHERE status = 'open' AND date(created_at) >= ? AND date(created_at) <= ?
            """, [start_date, end_date])
            totals['open_tickets'] = cursor.fetchone()['open_tickets']

            cursor.execute(f"""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM support_tickets
                WHERE {where_clause}
                GROUP BY date(created_at)
                ORDER BY day ASC
            """, params)
            trend = [dict(row) for row in cursor.fetchall()]
            
            return {
                "totals": totals,
                "trend": trend
            }
