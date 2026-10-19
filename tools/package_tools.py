"""Package lookup tools for the LangChain agent."""
from langchain_core.tools import tool
from database import get_db_connection

def _load_packages() -> list:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM packages")
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


@tool
def get_active_packages() -> str:
    """Retrieve the list of all packages with their schedule types, durations, and pricing in GHS."""
    packages = _load_packages()
    if not packages:
        return "No packages were found."
    
    categories = {}
    for p in packages:
        cat = p.get('category', 'Non-Students')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)
        
    result = "Packages & Pricing: (NOTE TO AI: Do not show the Internal IDs to the user. Format as bullet points.)\n"
    for cat, pkgs in categories.items():
        result += f"\n--- {cat} ---\n"
        for p in pkgs:
            result += f"- {p['name']} ({p.get('schedule_type', 'N/A')}): Duration {p.get('duration_weeks', '?')} weeks, Price: {p.get('price', '?')} GHS [Internal ID: {p['id']}]\n"
    return result


@tool
def get_package_details(package_id: int) -> str:
    """Get full details of a specific package using its Package ID."""
    packages = _load_packages()
    for p in packages:
        if p.get("id") == package_id:
            return (
                f"Package Name: {p['name']}\n"
                f"Package ID: {p['id']}\n"
                f"Category: {p.get('category', 'N/A')}\n"
                f"Description: {p.get('description', 'N/A')}\n"
                f"Schedule Type: {p.get('schedule_type', 'N/A')}\n"
                f"Duration: {p.get('duration_weeks', '?')} weeks\n"
                f"Price: {p.get('price', '?')} GHS\n"
            )
    return f"No package found with ID: {package_id}."


@tool
def search_packages(query: str) -> str:
    """Search packages matching a keyword like weekdays, weekends, or express."""
    packages = _load_packages()
    q_lower = query.lower()
    matches = []
    for p in packages:
        if (q_lower in p.get('name', '').lower() or
            q_lower in p.get('schedule_type', '').lower() or
            q_lower in p.get('category', '').lower() or
            q_lower in p.get('description', '').lower()):
            matches.append(p)

    if not matches:
        return f"No packages found matching '{query}'. Call get_active_packages to see all options."

    result = f"Packages matching '{query}':\n"
    for p in matches:
        result += f"[{p.get('category', 'Non-Students')}] {p['id']}. {p['name']} ({p.get('schedule_type', 'N/A')}): {p.get('duration_weeks', '?')} weeks, {p.get('price', '?')} GHS\n"
    return result
