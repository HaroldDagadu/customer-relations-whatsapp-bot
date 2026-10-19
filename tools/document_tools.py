"""Document search and knowledge base tools for the LangChain agent."""
import os
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_uploaded_documents(query: str) -> str:
    """Search through uploaded PDF documents for policies, manuals, procedures, or general company information."""
    try:
        from rag_engine import search_documents, has_documents
        if not has_documents():
            return "The document database is empty. No PDF files have been uploaded yet."

        results = search_documents(query, top_k=3)
        if not results:
            return "No relevant information found in the uploaded documents."

        output = "Information from uploaded documents:\n"
        for i, doc in enumerate(results):
            output += f"[{doc['source']} Page {doc['page']}]: {doc['content']}\n\n"
        return output
    except Exception as e:
        logger.error("Error in search_uploaded_documents: %s", e)
        return f"Error querying documents: {str(e)}"


@tool
def query_knowledge_base(query: str) -> str:
    """Search the knowledge base for information about services, pricing, policies, and procedures."""
    try:
        from rag_engine import search_documents, has_documents
        
        # If ChromaDB has documents, use semantic similarity search
        if has_documents():
            results = search_documents(query, top_k=3)
            if results:
                output = "Knowledge Base Results:\n"
                for doc in results:
                    output += f"[Topic: {doc.get('source', 'General')}]\n{doc['content']}\n\n"
                return output

        # Fallback to database keyword search if ChromaDB is empty or has no matches
        from database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT topic, content FROM knowledge_base")
            rows = cursor.fetchall()

        if not rows:
            return "The knowledge base is empty."

        # Simple keyword matching across all knowledge entries
        q_lower = query.lower()
        matches = []
        for row in rows:
            content = row["content"]
            topic = row["topic"]
            if q_lower in content.lower() or q_lower in topic.lower():
                matches.append({"topic": topic, "content": content})

        # If no keyword match, return all entries (let the LLM filter)
        if not matches:
            matches = [{"topic": row["topic"], "content": row["content"]} for row in rows]

        # Truncate to top 3 most relevant
        output = "Knowledge Base Results (Keyword Match):\n"
        for m in matches[:3]:
            # Truncate very long entries
            content_preview = m["content"][:2000]
            output += f"[Topic: {m['topic']}]\n{content_preview}\n\n"
        return output
    except Exception as e:
        logger.error("Error in query_knowledge_base: %s", e)
        return f"Error querying knowledge base: {str(e)}"
