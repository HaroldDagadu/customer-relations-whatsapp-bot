"""Registration and event tools for the LangChain agent."""
import json
import logging
from langchain_core.tools import tool
from database import get_db_connection

logger = logging.getLogger(__name__)


def _get_branch_list_text() -> str:
    """Fetch active branches from DB and format them as a numbered list for registration prompts."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, region FROM clients ORDER BY id")
            rows = cursor.fetchall()
        if not rows:
            return "   (No branches found — contact the school for assistance)"
        lines = []
        for row in rows:
            lines.append(f"   - {row['name']} (ID: {row['id']}, Region: {row['region']})")
        return "\n".join(lines)
    except Exception:
        return "   (Could not load branches — contact the school for assistance)"


def _get_branch_info(branch_name: str) -> dict | None:
    """Look up a branch by name (case-insensitive partial match) and return its full details."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, region, address, contact_numbers, google_maps_link FROM clients")
            rows = cursor.fetchall()
        name_lower = branch_name.strip().lower()
        for row in rows:
            if name_lower in row['name'].lower() or row['name'].lower() in name_lower:
                return dict(row)
        # Fallback: try matching just the key word (e.g. "West" matches "West Branch")
        for row in rows:
            for word in name_lower.split():
                if len(word) > 2 and word in row['name'].lower():
                    return dict(row)
        return None
    except Exception:
        return None


@tool
def get_user_registrations(user_id: int) -> str:
    """Retrieve the user's current package registrations and payment status from the database. Use this when a user asks about their registration status or details."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.status, r.created_at, p.name as package_name, p.price 
                FROM registrations r
                JOIN packages p ON r.package_id = p.id
                WHERE r.user_id = ?
            """, (user_id,))
            rows = cursor.fetchall()
            
        if not rows:
            return "You do not have any registrations on record. Would you like to view our packages and register?"
            
        result = "Your Package Registrations:\n"
        for row in rows:
            result += (
                f"- ID: {row['id']}\n"
                f"  Package: {row['package_name']}\n"
                f"  Price: {row['price']} GHS\n"
                f"  Status: {row['status'].capitalize()}\n"
                f"  Submitted: {row['created_at'].split(' ')[0] if row['created_at'] else 'N/A'}\n\n"
            )
        return result
    except Exception as e:
        logger.error("Error in get_user_registrations: %s", e)
        return f"Error fetching registration details: {str(e)}"

def send_whatsapp_flow_message_sync(
    to_phone_number: str,
    flow_id: str,
    flow_token: str,
    cta_text: str,
    body_text: str,
    header_text: str = "Registration",
    footer_text: str = "Secure Form",
    flow_screen: str = "REG_SCREEN",
    flow_data: dict = None
) -> bool:
    """Send an interactive WhatsApp Flow message synchronously."""
    from config import settings
    import httpx
    import logging

    logger = logging.getLogger(__name__)

    phone_number_id = settings.whatsapp_phone_number_id.strip() if settings.whatsapp_phone_number_id else ""
    api_token = settings.whatsapp_api_token.strip() if settings.whatsapp_api_token else ""
    if not api_token or not phone_number_id or not flow_id or "your_" in flow_id or not flow_id.strip():
        logger.warning("WhatsApp API credentials or Flow ID missing/placeholder. Skipping Flow message.")
        return False

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    action_params = {
        "flow_message_version": "3",
        "flow_token": flow_token,
        "flow_id": flow_id,
        "flow_cta": cta_text,
        "flow_action": "navigate",
        "flow_action_payload": {
            "screen": flow_screen,
            "data": flow_data or {}
        }
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_number,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": body_text
            },
            "footer": {
                "text": footer_text
            },
            "action": {
                "name": "flow",
                "parameters": action_params
            }
        }
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=15.0)
        response.raise_for_status()
        logger.info("Sent WhatsApp Flow message to %s", to_phone_number)
        return True
    except Exception as e:
        logger.error("Failed to send WhatsApp Flow message: %s", e)
        if hasattr(e, 'response') and e.response:
            logger.error("Error response details: %s", e.response.text)
        return False


@tool
def register_user_for_package(
    user_id: int, 
    package_id: int, 
    name: str = "",
    dob: str = "",
    ghana_card: str = "",
    place_of_birth: str = "",
    witness_name: str = "",
    witness_phone: str = "",
    marital_status: str = "",
    location: str = "",
    confirmed: bool = False
) -> str:
    """Register a user for a specific package.
    Requires user_id and package_id. 
    Provide name, dob, ghana_card, place_of_birth, witness_name, witness_phone, marital_status, and location if already collected via chat.
    Once all details are collected, call this tool with confirmed=False first — the tool will return a summary for the user to review.
    After the user confirms the details are correct, call this tool again with the same details and confirmed=True to finalize.
    If not provided, the system will attempt to send a WhatsApp Flow form first (unless Flows are disabled).
    """
    try:
        import httpx
        import re
        from config import settings
        from repository import Repository

        # Check package exists
        package = Repository.get_package_by_id(package_id)
        if not package:
            return f"Package with ID {package_id} not found."

        # Check for duplicate registration
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM registrations WHERE user_id = ? AND package_id = ? AND status != 'cancelled'",
                (user_id, package_id)
            )
            existing = cursor.fetchone()
            if existing:
                return f"You are already registered for the {package['name']} package."

            # Fetch user phone
            cursor.execute("SELECT phone_number FROM users WHERE id = ?", (user_id,))
            user_row = cursor.fetchone()
            phone = user_row["phone_number"] if user_row else "0000000000"

        has_all_details = bool(name and dob and ghana_card and place_of_birth and witness_name and witness_phone and marital_status and location)

        # Validation
        validation_errors = []
        if name and len(name.strip()) < 3:
            validation_errors.append("Full Name must be at least 3 characters.")
        if dob:
            if not re.search(r'\d', dob):
                validation_errors.append("Date of Birth must be a valid date.")
        if ghana_card:
            if not re.match(r'^GHA-\d{9}-\d$', ghana_card.strip().upper()):
                validation_errors.append("Ghana Card Number must be in the exact format GHA-XXXXXXXXX-X.")
        if place_of_birth and len(place_of_birth.strip()) < 2:
            validation_errors.append("Place of Birth is required.")
        if witness_name and len(witness_name.strip()) < 3:
            validation_errors.append("Witness Name must be at least 3 characters.")
        if witness_phone:
            digits = re.sub(r'\D', '', witness_phone)
            if len(digits) < 9:
                validation_errors.append("Witness Phone Number must be a valid phone number.")
        if marital_status:
            valid_statuses = ['single', 'married', 'divorced', 'widowed']
            if marital_status.lower().strip() not in valid_statuses:
                validation_errors.append("Marital Status must be Single, Married, Divorced, or Widowed.")
                
        if validation_errors:
            return "Validation failed. Please ask the user to correct the following details:\n" + "\n".join(f"- {err}" for err in validation_errors)

        # Attempt to send Flow only if NOT disabled and NOT all details collected
        if not settings.disable_whatsapp_flows and not has_all_details:
            if settings.registration_flow_id and "your_" not in settings.registration_flow_id and settings.registration_flow_id.strip():
                flow_token = f"registration_token_{user_id}_{package_id}"
                flow_sent = send_whatsapp_flow_message_sync(
                    to_phone_number=phone,
                    flow_id=settings.registration_flow_id,
                    flow_token=flow_token,
                    cta_text="Register Now",
                    body_text=f"Please tap the button below to complete your registration details for the {package['name']} package.",
                    flow_screen="REG_SCREEN",
                    flow_data={"package_id": str(package_id), "user_id": str(user_id)}
                )
                if flow_sent:
                    return f"I have sent the registration form for the '{package['name']}' package to your WhatsApp. Please tap 'Register Now' to enter your details."

        # If Flow is disabled or failed to send, and we don't have all details yet, return chat fallback message
        if not has_all_details:
            return (
                f"To register the user for the {package['name']} package, you need to collect the following missing details:\n"
                f"- Full Name\n"
                f"- Date of Birth (DD/MM/YYYY)\n"
                f"- Ghana Card Number (Must be exactly GHA-XXXXXXXXX-X)\n"
                f"- Place of Birth\n"
                f"- Witness Name\n"
                f"- Witness Phone Number\n"
                f"- Marital Status (Single/Married/Divorced/Widowed)\n"
                f"- Preferred Branch\n\n"
                f"Gather these details naturally in conversation. If the user already provided their town, recommend the closest branch."
            )

        # --- Confirmation Step ---
        # If we have all details but user has NOT yet confirmed, show summary for review
        if has_all_details and not confirmed:
            branch_info = _get_branch_info(location)
            branch_display = branch_info['name'] if branch_info else location
            return (
                f"Please review your registration details before I submit:\n\n"
                f"*Package:* {package['name']}\n"
                f"*Full Name:* {name}\n"
                f"*Date of Birth:* {dob}\n"
                f"*Ghana Card:* {ghana_card}\n"
                f"*Place of Birth:* {place_of_birth}\n"
                f"*Witness Name:* {witness_name}\n"
                f"*Witness Phone:* {witness_phone}\n"
                f"*Marital Status:* {marital_status}\n"
                f"*Branch:* {branch_display}\n\n"
                f"Is everything correct? Reply *Yes* to confirm or tell me what you would like to change."
            )

        # Create registration with all fields
        reg_id = Repository.create_registration(
            user_id=user_id,
            package_id=package_id,
            status='pending',
            name=name,
            dob=dob,
            ghana_card=ghana_card,
            place_of_birth=place_of_birth,
            witness_name=witness_name,
            witness_phone=witness_phone,
            marital_status=marital_status,
            location=location
        )

        # Update the user's location in the users table to the chosen branch
        Repository.update_user_location(user_id, location)

        # Look up the branch details for the confirmation message
        branch_info = _get_branch_info(location)
        branch_footer = ""
        if branch_info:
            branch_footer = (
                f"\n*Branch Details:*\n"
                f"Branch: {branch_info['name']} (Branch #{branch_info['id']})\n"
                f"Address: {branch_info.get('address', 'N/A')}\n"
                f"Contact: {branch_info.get('contact_numbers', 'N/A')}\n"
                f"Google Maps: {branch_info.get('google_maps_link', 'N/A')}"
            )
        else:
            branch_footer = f"\nBranch: {location}"

        if settings.use_paystack:
            # Initialize Paystack transaction (amount in pesewas)
            amount_in_pesewas = int(package["price"] * 100)
            headers = {
                "Authorization": f"Bearer {settings.paystack_secret_key}",
                "Content-Type": "application/json"
            }
            email = f"{phone}@example.com"
            payload = {
                "email": email,
                "amount": amount_in_pesewas,
                "reference": f"wa_reg_{reg_id}",
                "metadata": {
                    "registration_id": reg_id,
                    "package_name": package["name"],
                    "user_id": user_id
                }
            }
            
            try:
                response = httpx.post(
                    "https://api.paystack.co/transaction/initialize",
                    json=payload,
                    headers=headers,
                    timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get("status"):
                    payment_link = data["data"]["authorization_url"]
                    reference = data["data"]["reference"]
                    
                    # Store the payment reference on the registration
                    Repository.update_registration_status(reg_id, "pending", payment_reference=reference)
                    
                    return (
                        f"Registration successful!\n"
                        f"Package: {package['name']}\n"
                        f"Registration ID: {reg_id}\n"
                        f"Amount Due: {package['price']} GHS\n"
                        f"Status: Pending Payment\n"
                        f"{branch_footer}\n\n"
                        f"Please complete payment using this secure link: {payment_link}"
                    )
                else:
                    logger.error("Paystack transaction initialize status was false: %s", data.get("message"))
            except Exception as pe:
                logger.error("Failed to initialize Paystack transaction: %s", pe)
            
            # Fallback if paystack initialization failed
            return (
                f"Registration successful!\n"
                f"Package: {package['name']}\n"
                f"Registration ID: {reg_id}\n"
                f"Amount Due: {package['price']} GHS\n"
                f"Status: Pending payment\n"
                f"{branch_footer}\n\n"
                f"Our team will send you payment instructions shortly."
            )
        else:
            visit_text = f"our {branch_info['name']}" if branch_info else "your chosen branch"
            return (
                f"Registration successful!\n"
                f"Package: {package['name']}\n"
                f"Registration ID: {reg_id}\n"
                f"Amount Due: {package['price']} GHS\n"
                f"Status: Pending Payment\n"
                f"{branch_footer}\n\n"
                f"Please visit {visit_text} to make payment."
            )

    except Exception as e:
        logger.error("Error in register_user_for_package: %s", e)
        return f"Error processing registration: {str(e)}"
