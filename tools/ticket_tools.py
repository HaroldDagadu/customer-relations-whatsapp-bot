"""Support ticket creation tool using WhatsApp Flows."""
import logging
from langchain_core.tools import tool
from database import get_db_connection
from tools.registration_tools import send_whatsapp_flow_message_sync

logger = logging.getLogger(__name__)


@tool
def open_support_ticket(user_id: int, subject: str = "", description: str = "", location: str = "") -> str:
    """Open a support ticket or file a complaint/feedback for the user.
    Requires user_id. 
    Provide subject and description if already collected via chat. 
    Provide location (branch name) if collected or required.
    If the user's branch is not already registered in the system, you must ask the user for it first before calling this tool.
    """
    try:
        from config import settings

        # Query user location and phone number
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number, location FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            phone = row["phone_number"] if row else None
            user_location = row["location"] if row else None

        if not phone:
            return "Error: User phone number not found in database."

        # Determine target location
        target_location = location.strip() if location else (user_location or "").strip()

        # If we still do not have a location, ask the user for it
        if not target_location:
            return (
                "To open a support ticket, please provide your branch location first. "
                "Available branches: Central, East, West, North. "
                "Which branch do you belong to?"
            )

        # Update the user's default location if they just provided it
        if target_location and not user_location:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET location = ? WHERE id = ?", (target_location, user_id))
                conn.commit()
            user_location = target_location

        # If subject is already collected/provided, create the ticket directly
        if subject:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO support_tickets (user_id, subject, description, location, status) VALUES (?, ?, ?, ?, 'open')",
                    (user_id, subject, description or None, target_location)
                )
                conn.commit()
                ticket_id = cursor.lastrowid
            
            return (
                f"Support ticket created successfully!\n"
                f"Ticket ID: {ticket_id}\n"
                f"Subject: {subject}\n"
                f"Branch: {target_location}\n"
                f"Status: OPEN\n\n"
                f"An agent will review your issue and reach out shortly."
            )

        # If Flow ID is configured and NOT disabled, send the interactive Flow message
        if not settings.disable_whatsapp_flows and settings.ticket_flow_id and "your_" not in settings.ticket_flow_id and settings.ticket_flow_id.strip():
            flow_token = f"ticket_token_{user_id}"
            flow_sent = send_whatsapp_flow_message_sync(
                to_phone_number=phone,
                flow_id=settings.ticket_flow_id,
                flow_token=flow_token,
                cta_text="Create Ticket",
                body_text="Please tap below to describe your support request or complaint.",
                header_text="Customer Support",
                footer_text="Support Helpdesk",
                flow_screen="TICKET_SCREEN",
                flow_data={"user_id": str(user_id)}
            )
            if flow_sent:
                return "I have sent the support ticket form to your WhatsApp. Please tap 'Create Ticket' to fill out your complaint."
            else:
                return (
                    "Failed to send the Support Ticket form. Please state the Subject and description of the issue directly in this chat, and I will open the ticket for you."
                )

        # Fallback instructions if Flows are not configured/ready
        return (
            "Please describe your issue or complaint directly in this chat, including the Subject and Description, and I will create a ticket for you."
        )
    except Exception as e:
        logger.error("Error in open_support_ticket: %s", e)
        return f"Error opening support ticket: {str(e)}"


@tool
def get_user_tickets(user_id: int) -> str:
    """Retrieve the user's support and feedback tickets from the database. Use this tool when the user asks about the status of their support request, ticket, or complaint."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, subject, description, status, created_at 
                FROM support_tickets 
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            rows = cursor.fetchall()
            
        if not rows:
            return "You do not have any support tickets on file."
            
        result = "Your Support Tickets:\n"
        for row in rows:
            desc = f" - {row['description']}" if row['description'] else ""
            result += (
                f"- Ticket ID: {row['id']}\n"
                f"  Subject: {row['subject']}{desc}\n"
                f"  Status: {row['status'].upper()}\n"
                f"  Created: {row['created_at'].split(' ')[0] if row['created_at'] else 'N/A'}\n\n"
            )
        return result
    except Exception as e:
        logger.error("Error in get_user_tickets: %s", e)
        return f"Error fetching tickets: {str(e)}"
