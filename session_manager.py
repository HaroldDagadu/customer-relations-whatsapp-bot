"""
Per-user session management for the WhatsApp bot.
Each phone number gets its own LangChain agent with a sliding context window.
Sessions expire after 30 minutes of inactivity.
"""
import asyncio
import time
import logging
from typing import Dict, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent import build_agent, extract_text_response, get_chat_llm

logger = logging.getLogger(__name__)

# Maximum number of messages (user + assistant) to keep in the active context window.
MAX_CONTEXT_MESSAGES = 40

# Number of oldest messages to fold into a summary when the window overflows.
COMPACTION_BATCH_SIZE = 10

DEFAULT_SYSTEM_PROMPT = """You are the AI assistant managing WhatsApp conversations for a multi-branch service business.

Your capabilities:
- Provide branch locations, contact numbers, and directions using branch tools.
- Retrieve active packages, durations, and pricing using package tools.
- Guide users to register for packages (triggering the interactive registration flow form).
- Guide users to open support, feedback, or complaint tickets (triggering the support ticket flow form).
- Check the current status of users' package registrations or support tickets.
- Answer general questions about services, add-on fees, and other policies.

{user_context}

CRITICAL INSTRUCTIONS:
1. If the user asks about branches, locations, directions, or contact numbers, you MUST use the branch tools (get_active_branches, get_branch_details, search_branch_by_region, recommend_closest_branch). Specifically, if the user mentions their location, neighborhood, or asks which branch is closest to them, use recommend_closest_branch to recommend the nearest branch. Do not guess or use any branch names not returned by these tools.
2. If the user asks about packages, durations (weeks), or pricing, you MUST use the package tools (get_active_packages, get_package_details, search_packages).
3. If the user asks about optional or mandatory additional fees, add-on fees, rentals, or third-party pass-through costs, you MUST use the add-on fee tools (get_active_addons, get_addon_details, search_addons).
4. If the user asks general questions about school services, pricing policies, procedures, or company files, you MUST use the query_knowledge_base tool.
5. ALWAYS prioritize using your tools to find factual details. Do not state facts or assume details about branches, packages, prices, or addons unless retrieved from a tool.
6. If the answer cannot be found in the tools or knowledge base, say "I cannot find the answer in the provided documents or office records." and offer to connect the user with a human agent.

Guidelines:
- NEVER use emojis or emoticons in any response — plain text only.
- DO NOT give away branch phone numbers unless the user is already registered, explicitly asks for the numbers, or you are explicitly confirming a registration where numbers are to be shared.
- DO NOT mention mandatory fees when just listing branches or answering general questions. Only bring up fees when talking specifically about packages, costs, or registration summaries.
- When a user greets you (e.g. "Hello", "Hi", "Hey"), respond with your normal professional greeting. Do NOT ask for their town or location during greetings.
- When the user makes a substantive request (asking about packages, registration, branches, support tickets, or any other service enquiry) AND their profile shows town or closest branch as 'Not set', ask them: "By the way, which town or area do you stay in? This helps me recommend the closest branch for you." Then call the set_user_location tool with their answer before continuing with their request. Only ask once — after the tool confirms, proceed normally.
- If the user tells you they have moved or want to update their location, call set_user_location again with their new town.
- When a user states their town, boldly recommend the closest branch (using recommend_closest_branch or set_user_location), explicitly state the branch name to the user, and state you will use it for them unless they prefer another.
- Users do NOT need to provide Package IDs or Branch IDs. Let them use natural language (e.g., "regular course") and map their choice to the correct internal ID yourself. Do not ask users for IDs.
- When a user greets you, reply with a professional introduction stating exactly what you can do (e.g. show packages, help them register, locate branches, open support tickets, or check status) to guide them to the right flow, and ask what they need. Keep it under 60 words.
- Be professional, direct, and concise — no fluff.
- Keep responses short. Do not use asterisks, markdown, or any text formatting — plain text only.
- When registering a user, use their user ID directly — never ask them for it. Their ID is provided above.
- When a user wants to register, first use get_active_packages to show them options. Once they choose a package, call register_user_for_package. The tool will instruct you on what details to collect. Gather the details naturally. Call register_user_for_package again with confirmed=False to generate a summary. Show the summary and ALSO mention any mandatory or optional add-on fees (using get_active_addons) so they are aware of full costs. If the user confirms, call register_user_for_package one final time with confirmed=True. If the tool reports validation errors, ask the user to correct the specific invalid fields.
- When a user wants to lodge a complaint or open a support ticket, call open_support_ticket. If the tool indicates that the WhatsApp Flow failed to send, ask the user to provide the Subject and Description in the chat. Gather these details and call open_support_ticket again with the collected parameters.
- If the user asks about the status of their registrations, use the get_user_registrations tool.
- If the user asks about their support tickets, use the get_user_tickets tool."""


async def _summarize_messages(messages: List, model: ChatGoogleGenerativeAI) -> str:
    """Summarize a batch of older messages into a concise prose paragraph."""
    if not messages:
        return ""

    transcript = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in messages
    )

    prompt = (
        "Summarize the following conversation excerpt in a single concise paragraph "
        "(under 150 words). Capture key facts the user shared (name, location, "
        "preferences, issues) and any important conclusions or commitments made by "
        "the assistant. Write in past-tense prose, not a list.\n\n"
        f"{transcript}\n\nSummary:"
    )

    try:
        response = await model.ainvoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        return text.strip()
    except Exception as exc:
        logger.warning("Context summarization failed: %s", exc)
        return ""


class UserSession:
    """Manages a single user's agent session with a sliding context window."""

    def __init__(self, user_id: int = None, user_name: str = None):
        user_context = ""
        if user_id:
            user_context += f"\nCurrent user ID: {user_id}"
            try:
                from repository import Repository
                user_row = Repository.get_user_by_id(user_id)
                if user_row:
                    town = user_row.get("town") or ""
                    location = user_row.get("location") or ""
                    user_context += f"\nUser Town/Residence: {town if town else 'Not set'}"
                    user_context += f"\nUser Closest Branch: {location if location else 'Not set'}"
            except Exception as e:
                logger.error("Error loading user context: %s", e)
        if user_name:
            user_context += f"\nCurrent user name: {user_name}"

        system_prompt = DEFAULT_SYSTEM_PROMPT.format(user_context=user_context)
        self.executor = build_agent(system_prompt)
        self.context_window: List = []
        self._context_summary: str = ""
        self._lock = asyncio.Lock()
        self.last_accessed = time.time()

        # Lightweight LLM for summarization only — no tools, no agent loop.
        self._summary_llm = get_chat_llm(temperature=0.3)

        if user_id:
            try:
                from repository import Repository
                db_messages = Repository.get_recent_context_messages(
                    user_id, limit=MAX_CONTEXT_MESSAGES
                )
                for msg in db_messages:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    if role == "user":
                        self.context_window.append(HumanMessage(content=content))
                    elif role == "assistant":
                        self.context_window.append(AIMessage(content=content))
            except Exception as e:
                logger.error("Error loading context from DB for user %s: %s", user_id, e)

    async def _compact_context(self):
        """Fold the oldest messages into a running summary to keep the window
        within MAX_CONTEXT_MESSAGES."""
        if len(self.context_window) <= MAX_CONTEXT_MESSAGES:
            return

        # Take the oldest batch and summarize them.
        batch = self.context_window[:COMPACTION_BATCH_SIZE]
        self.context_window = self.context_window[COMPACTION_BATCH_SIZE:]

        new_summary = await _summarize_messages(batch, self._summary_llm)

        if new_summary:
            if self._context_summary:
                # Merge with existing summary by re-summarizing both.
                merged = (
                    f"Earlier summary: {self._context_summary}\n\n"
                    f"Newer excerpt: {new_summary}"
                )
                try:
                    merge_prompt = (
                        "Combine these two conversation summaries into one concise "
                        "paragraph (under 150 words) in past-tense prose:\n\n"
                        f"{merged}\n\nCombined summary:"
                    )
                    response = await self._summary_llm.ainvoke(merge_prompt)
                    self._context_summary = (
                        response.content if hasattr(response, "content")
                        else str(response)
                    ).strip()
                except Exception:
                    self._context_summary = new_summary
            else:
                self._context_summary = new_summary

        # If still too large after compaction, trim to the most recent messages.
        if len(self.context_window) > MAX_CONTEXT_MESSAGES:
            excess = len(self.context_window) - MAX_CONTEXT_MESSAGES
            trimmed = self.context_window[:excess]
            self.context_window = self.context_window[excess:]
            # Try to fold the trimmed messages as well.
            extra_summary = await _summarize_messages(trimmed, self._summary_llm)
            if extra_summary:
                self._context_summary = (
                    f"{self._context_summary}\n{extra_summary}"
                    if self._context_summary else extra_summary
                )

    def _build_context_for_agent(self) -> List:
        """Assemble the full context list that will be passed to the agent.
        Includes the running summary (if any) as a SystemMessage."""
        context: List = []
        if self._context_summary:
            context.append(SystemMessage(
                content=f"[Earlier conversation summary]\n{self._context_summary}"
            ))
        context.extend(self.context_window)
        return context

    async def send_message(self, user_text: str) -> str:
        """Process a user message and return the agent's response.

        The synchronous AgentExecutor.invoke() call is offloaded to a thread
        pool so it does not block the asyncio event loop.  This lets multiple
        users be processed concurrently.
        """
        async with self._lock:
            self.last_accessed = time.time()
            try:
                input_preview = user_text if len(user_text) <= 100 else user_text[:97] + "..."
                logger.debug("Session: invoking agent | input=%s | window_size=%d",
                             input_preview, len(self.context_window))

                agent_context = self._build_context_for_agent()
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.executor.invoke({
                        "input": user_text,
                        "chat_history": agent_context,
                    }),
                )
                response_text = extract_text_response(result.get("output", ""))

                # Append the new exchange to the sliding window.
                self.context_window.append(HumanMessage(content=user_text))
                self.context_window.append(AIMessage(content=response_text))

                # Compact if the window has grown too large.
                await self._compact_context()

                output_preview = response_text if len(response_text) <= 100 else response_text[:97] + "..."
                logger.debug("Session: agent response | output=%s | window_size=%d",
                             output_preview, len(self.context_window))

                return response_text
            except Exception as e:
                logger.error("Agent error for session: %s", e)
                return (
                    "Sorry, I encountered an error while processing your request. "
                    "Please try again."
                )


class SessionManager:
    """Manages per-phone-number agent sessions with TTL expiry."""

    def __init__(self, ttl_seconds: int = 1800):
        self.sessions: Dict[str, UserSession] = {}
        self.ttl_seconds = ttl_seconds

    def get_or_create_session(
        self, phone_number: str, user_id: int = None, user_name: str = None
    ) -> UserSession:
        current_time = time.time()

        if phone_number in self.sessions:
            session = self.sessions[phone_number]
            if current_time - session.last_accessed < self.ttl_seconds:
                session.last_accessed = current_time
                return session

        # Create new session
        session = UserSession(user_id=user_id, user_name=user_name)
        self.sessions[phone_number] = session
        return session

    def cleanup_expired_sessions(self):
        current_time = time.time()
        expired = [
            phone for phone, session in self.sessions.items()
            if current_time - session.last_accessed >= self.ttl_seconds
        ]
        for phone in expired:
            del self.sessions[phone]
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))

    def reset_session(self, phone_number: str):
        if phone_number in self.sessions:
            del self.sessions[phone_number]


session_manager = SessionManager()
