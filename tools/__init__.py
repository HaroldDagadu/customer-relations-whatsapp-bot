"""LangChain tool definitions for the WhatsApp agent."""
from tools.branch_tools import *
from tools.package_tools import *
from tools.addon_tools import *
from tools.document_tools import *
from tools.registration_tools import *
from tools.knowledge_tools import *
from tools.ticket_tools import *
from tools.location_tools import *

ALL_TOOLS = [
    get_active_branches,
    get_branch_details,
    search_branch_by_region,
    get_active_packages,
    get_package_details,
    search_packages,
    get_active_addons,
    get_addon_details,
    search_addons,
    query_knowledge_base,
    get_user_registrations,
    register_user_for_package,
    open_support_ticket,
    get_user_tickets,
    recommend_closest_branch,
    set_user_location,
]
