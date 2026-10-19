"""
RAG Engine — ChromaDB vector store + Gemini embeddings for PDF document ingestion and search.
"""
import os
import shutil
import logging
from pathlib import Path

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

from config import settings

logger = logging.getLogger(__name__)

# --- Singleton Embeddings ---
_embeddings = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set. Cannot initialize Gemini embeddings.")
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
        _embeddings = GoogleGenerativeAIEmbeddings(model=settings.embedding_model)
        logger.info("Gemini embeddings initialized with model: %s", settings.embedding_model)
    return _embeddings


def get_chroma_db_dir() -> str:
    return settings.chroma_db_dir


def has_documents() -> bool:
    """Check if the vector database has any stored documents."""
    db_dir = get_chroma_db_dir()
    return os.path.exists(db_dir) and len(os.listdir(db_dir)) > 0


def ingest_pdf(file_path: str) -> dict:
    """
    Parse a PDF file, chunk it, embed with Gemini, and store in ChromaDB.
    Returns stats about the ingestion.
    """
    embeddings = get_embeddings()
    db_dir = get_chroma_db_dir()

    # 1. Load PDF
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    if not documents:
        raise ValueError("The PDF appears to be empty or unreadable.")

    # 2. Chunk
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(documents)

    # 3. Filter empty chunks
    chunks = [c for c in chunks if c.page_content and c.page_content.strip()]

    if not chunks:
        raise ValueError("The PDF produced no usable text content after processing.")

    # 4. Embed and persist
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=db_dir
    )

    logger.info("Ingested PDF %s: %d pages, %d chunks", file_path, len(documents), len(chunks))

    return {
        "pages_ingested": len(documents),
        "chunks_created": len(chunks)
    }


def search_documents(query: str, top_k: int = 3) -> list:
    """
    Perform similarity search against stored documents.
    Returns a list of dicts with content, source, and page.
    """
    db_dir = get_chroma_db_dir()
    if not has_documents():
        return []

    try:
        embeddings = get_embeddings()
        vector_store = Chroma(
            persist_directory=db_dir,
            embedding_function=embeddings
        )
        docs = vector_store.similarity_search(query, k=top_k)
        results = []
        for doc in docs:
            page = doc.metadata.get("page", 0) + 1
            src = os.path.basename(doc.metadata.get("source", "Unknown"))
            results.append({
                "content": doc.page_content,
                "source": src,
                "page": page
            })
        return results
    except Exception as e:
        logger.error("Error searching documents: %s", e)
        return []


def list_documents() -> list:
    """Get a list of unique document filenames in the vector store."""
    db_dir = get_chroma_db_dir()
    if not has_documents():
        return []

    try:
        embeddings = get_embeddings()
        vector_store = Chroma(
            persist_directory=db_dir,
            embedding_function=embeddings
        )
        data = vector_store.get(include=["metadatas"])
        sources = set()
        if data and "metadatas" in data:
            for m in data["metadatas"]:
                if m and "source" in m:
                    sources.add(os.path.basename(m["source"]))
        return sorted(list(sources))
    except Exception as e:
        logger.error("Error listing documents: %s", e)
        return []


def delete_document(filename: str) -> int:
    """Delete all chunks belonging to a specific document. Returns chunks deleted count."""
    db_dir = get_chroma_db_dir()
    if not has_documents():
        raise ValueError("The vector database is empty.")

    embeddings = get_embeddings()
    vector_store = Chroma(
        persist_directory=db_dir,
        embedding_function=embeddings
    )

    data = vector_store.get(include=["metadatas"])
    ids_to_delete = []
    if data and "ids" in data and "metadatas" in data:
        for doc_id, m in zip(data["ids"], data["metadatas"]):
            if m and "source" in m:
                src_name = os.path.basename(m["source"])
                if src_name == filename:
                    ids_to_delete.append(doc_id)

    if not ids_to_delete:
        raise ValueError(f"Document '{filename}' not found in the database.")

    vector_store.delete(ids=ids_to_delete)

    # If database is completely empty now, clean up directory
    data_after = vector_store.get(include=["metadatas"])
    if not data_after or not data_after.get("ids"):
        try:
            shutil.rmtree(db_dir)
        except Exception:
            pass

    logger.info("Deleted document '%s': %d chunks removed", filename, len(ids_to_delete))
    return len(ids_to_delete)


def clear_all() -> bool:
    """Wipe the entire vector database."""
    db_dir = get_chroma_db_dir()
    if os.path.exists(db_dir):
        shutil.rmtree(db_dir)
        logger.info("Vector database cleared.")
        return True
    return False


def get_stats() -> dict:
    """Return vector DB statistics."""
    db_dir = get_chroma_db_dir()
    if not has_documents():
        return {"total_chunks": 0, "total_documents": 0}

    try:
        embeddings = get_embeddings()
        vector_store = Chroma(
            persist_directory=db_dir,
            embedding_function=embeddings
        )
        data = vector_store.get(include=["metadatas"])
        sources = set()
        total = 0
        if data and "metadatas" in data:
            total = len(data["metadatas"])
            for m in data["metadatas"]:
                if m and "source" in m:
                    sources.add(os.path.basename(m["source"]))
        return {"total_chunks": total, "total_documents": len(sources)}
    except Exception as e:
        logger.error("Error getting stats: %s", e)
        return {"total_chunks": 0, "total_documents": 0}


def ingest_knowledge(kb_id: int, topic: str, content: str):
    """
    Parse a text knowledge entry, convert it into a LangChain document,
    embed it with Gemini, and store in ChromaDB.
    """
    embeddings = get_embeddings()
    db_dir = get_chroma_db_dir()

    from langchain_core.documents import Document
    doc_text = f"Topic: {topic}\nContent: {content}"
    doc = Document(
        page_content=doc_text,
        metadata={
            "source": f"Knowledge Base (Topic: {topic})",
            "kb_id": kb_id,
            "topic": topic
        }
    )

    Chroma.from_documents(
        documents=[doc],
        embedding=embeddings,
        persist_directory=db_dir
    )
    logger.info("Ingested knowledge entry ID %d (Topic: %s) into ChromaDB", kb_id, topic)


def delete_knowledge_entry(kb_id: int) -> int:
    """Delete a knowledge entry from ChromaDB by its ID. Returns chunks deleted count."""
    db_dir = get_chroma_db_dir()
    if not has_documents():
        return 0

    embeddings = get_embeddings()
    vector_store = Chroma(
        persist_directory=db_dir,
        embedding_function=embeddings
    )

    data = vector_store.get(include=["metadatas"])
    ids_to_delete = []
    if data and "ids" in data and "metadatas" in data:
        for doc_id, m in zip(data["ids"], data["metadatas"]):
            if m and m.get("kb_id") == kb_id:
                ids_to_delete.append(doc_id)

    if ids_to_delete:
        vector_store.delete(ids=ids_to_delete)
        logger.info("Deleted knowledge entry ID %d: %d chunks removed from ChromaDB", kb_id, len(ids_to_delete))
        
        # If database is completely empty now, clean up directory
        data_after = vector_store.get(include=["metadatas"])
        if not data_after or not data_after.get("ids"):
            try:
                import shutil
                shutil.rmtree(db_dir)
            except Exception:
                pass
                
    return len(ids_to_delete)
