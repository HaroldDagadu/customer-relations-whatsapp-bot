"""Add-on fee lookup tools for the LangChain agent."""
from langchain_core.tools import tool
from database import get_db_connection

def _load_addons() -> list:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fees")
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


@tool
def get_active_addons() -> str:
    """Retrieve the list of all add-on fees including costs (GHS), whether mandatory or optional, and descriptions."""
    addons = _load_addons()
    if not addons:
        return "No add-on fees were found."
    result = "Add-On Fees:\n"
    for a in addons:
        mandatory = "Mandatory" if a.get("mandatory") else "Optional"
        third_party = "Paid to Third Party" if a.get("pass_through") else "Internal Fee"
        desc = a.get("description", "")
        desc_str = f" - {desc}" if desc else ""
        result += f"{a['id']}. {a['name']}: {a.get('amount', '?')} GHS ({mandatory}, {third_party}){desc_str}\n"
    return result


@tool
def get_addon_details(fee_id: int) -> str:
    """Get full details of a specific add-on fee using its Fee ID."""
    addons = _load_addons()
    for a in addons:
        if a.get("id") == fee_id:
            mandatory = "Yes" if a.get("mandatory") else "No"
            third_party = "Yes" if a.get("pass_through") else "No"
            return (
                f"Fee Name: {a['name']}\n"
                f"Fee ID: {a['id']}\n"
                f"Amount: {a.get('amount', '?')} GHS\n"
                f"Is Mandatory: {mandatory}\n"
                f"Paid to Third Party: {third_party}\n"
                f"Description: {a.get('description', 'N/A')}\n"
            )
    return f"No add-on fee found with ID: {fee_id}."


@tool
def search_addons(query: str) -> str:
    """Search for add-on fees matching a keyword like registration, documentation, rental, or equipment."""
    addons = _load_addons()
    q_lower = query.lower()
    matches = []
    for a in addons:
        if (q_lower in a.get('name', '').lower() or
            q_lower in a.get('description', '').lower()):
            matches.append(a)

    if not matches:
        return f"No add-on fees found matching '{query}'. Call get_active_addons to see all."

    result = f"Add-on fees matching '{query}':\n"
    for a in matches:
        mandatory = "Mandatory" if a.get("mandatory") else "Optional"
        result += f"{a['id']}. {a['name']}: {a.get('amount', '?')} GHS ({mandatory})\n"
    return result
