"""Knowledge base search tool for the LangChain agent (re-exported from document_tools)."""
# The query_knowledge_base tool is defined in document_tools.py
# This file exists so tools/__init__.py can import from knowledge_tools
from tools.document_tools import query_knowledge_base

__all__ = ["query_knowledge_base"]
