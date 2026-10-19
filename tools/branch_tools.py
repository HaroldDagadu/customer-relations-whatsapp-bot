"""Branch lookup tools for the LangChain agent."""
from langchain_core.tools import tool
from database import get_db_connection

def _load_branches() -> list:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients")
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


@tool
def get_active_branches() -> str:
    """Retrieve the list of all active office branches with their names, regions, and contact numbers."""
    branches = _load_branches()
    if not branches:
        return "No office branches were found."
    result = "Active Branches:\n"
    for b in branches:
        result += f"{b.get('id', '?')}. {b['name']} (Region: {b.get('region', 'N/A')}, Contact: {b.get('contact_numbers', 'N/A')})\n"
    return result


@tool
def get_branch_details(branch_id: int) -> str:
    """Get the full contact, address, and navigation link details of a specific branch using its ID number."""
    branches = _load_branches()
    for b in branches:
        if b.get("id") == branch_id:
            return (
                f"Branch Name: {b['name']}\n"
                f"Branch ID: {b['id']}\n"
                f"Region: {b.get('region', 'N/A')}\n"
                f"Physical Address: {b.get('address', 'N/A')}\n"
                f"Google Maps Link: {b.get('google_maps_link', 'N/A')}\n"
                f"Front Desk Contact: {b.get('contact_numbers', 'N/A')}\n"
            )
    return f"No branch found with ID: {branch_id}."


@tool
def search_branch_by_region(region: str) -> str:
    """Find active branches matching a specific geographic region, area, or location name."""
    branches = _load_branches()
    r_lower = region.lower()
    matches = []
    for b in branches:
        if (r_lower in b.get('region', '').lower() or
            r_lower in b.get('name', '').lower() or
            r_lower in b.get('address', '').lower()):
            matches.append(b)

    if not matches:
        return f"No branch found matching '{region}'. Call get_active_branches to check all available branches."

    result = f"Branch(es) found for '{region}':\n"
    for b in matches:
        result += (
            f"{b['id']}. {b['name']}\n"
            f"   Address: {b.get('address', 'N/A')}\n"
            f"   Maps: {b.get('google_maps_link', 'N/A')}\n"
            f"   Contact: {b.get('contact_numbers', 'N/A')}\n"
        )
    return result


@tool
def recommend_closest_branch(user_location: str) -> str:
    """Recommend the geographically closest branch based on the user's location description (e.g. neighborhood, landmark, suburb, or town). Use this when the user asks which branch is closest to them or specifies where they stay."""
    try:
        from agent import extract_text_response, get_chat_llm

        branches = _load_branches()
        if not branches:
            return "No branches found to recommend from."

        branches_str = ""
        for b in branches:
            branches_str += f"{b.get('id')}. {b.get('name')} | Address: {b.get('address', 'N/A')} | Region: {b.get('region', 'N/A')}\n"

        prompt = (
            "You are a geographical recommendation assistant for a multi-branch business.\n"
            "Given the following list of active branches and their physical details:\n"
            f"{branches_str}\n"
            f"And the user's current location description: '{user_location}'\n\n"
            "Determine which of these branches is geographically closest or most convenient for the user to visit.\n"
            "Your output must be clear, direct, and specify:\n"
            "1. Recommended Branch (including ID and Name)\n"
            "2. Brief geographical reason/explanation showing why this branch is closest to the user's location.\n"
            "Keep the response brief and professional, and do not use emojis."
        )

        llm = get_chat_llm(temperature=0.0)
        response = llm.invoke(prompt)
        return extract_text_response(response.content)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Error in recommend_closest_branch: %s", e)
        return f"Could not recommend a branch due to an error: {str(e)}"

