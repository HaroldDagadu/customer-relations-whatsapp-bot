"""Location and routing tools for the LangChain agent."""
import logging
from langchain_core.tools import tool
from database import get_db_connection
from repository import Repository

logger = logging.getLogger(__name__)


def _get_mapped_branch(town: str) -> str | None:
    try:
        from agent import extract_text_response, get_chat_llm
        
        # Load branches from DB
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, region, address FROM clients")
            branches = [dict(row) for row in cursor.fetchall()]
        
        if not branches:
            return None
            
        branches_str = ""
        for b in branches:
            branches_str += f"- ID: {b['id']}, Name: {b['name']}, Region: {b['region']}, Address: {b.get('address') or ''}\n"
            
        prompt = (
            "You are a geographical routing assistant for a multi-branch business.\n"
            "Given the active branches:\n"
            f"{branches_str}\n"
            f"And the user's town/area of residence: '{town}'\n\n"
            "Determine which of these branches is geographically closest/most convenient for this town.\n"
            "Return EXACTLY and ONLY the name of the closest branch from the list above (e.g. 'North Branch'). "
            "Do not include any other text, reasoning, ID, or punctuation. Just return the exact branch name."
        )
        
        llm = get_chat_llm(temperature=0.0)
        response = llm.invoke(prompt)
        matched_name = extract_text_response(response.content).strip()
        
        # Verify exact match
        for b in branches:
            if b['name'].strip().lower() == matched_name.lower():
                return b['name']
                
        # Try substring match
        for b in branches:
            if b['name'].lower() in matched_name.lower() or matched_name.lower() in b['name'].lower():
                return b['name']
                
        return branches[0]['name']
    except Exception as e:
        logger.error("Error in _get_mapped_branch: %s", e)
        return None


@tool
def set_user_location(user_id: int, town: str) -> str:
    """Register the user's town/area of residence (e.g. 'Madina', 'Kasoa', 'Lapaz') and automatically map it to the closest branch location. Use this tool immediately after the user provides their town or area of residence."""
    try:
        town_clean = town.strip()
        if not town_clean:
            return "Please provide a valid town name."
            
        branch_name = _get_mapped_branch(town_clean)
        if not branch_name:
            branch_name = "Central Branch"
            
        Repository.update_user_town_and_location(user_id, town_clean, branch_name)
        
        return (
            f"Thank you. I have set your residence as {town_clean}. "
            f"Your closest branch is {branch_name}."
        )
    except Exception as e:
        logger.error("Error in set_user_location: %s", e)
        return f"Error setting location: {str(e)}"
