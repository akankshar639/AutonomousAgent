"""agent/memory.py — checkpointer-based session memory."""

from config.settings import settings


def get_checkpointer():
    """
    Return a SqliteSaver checkpointer for persistent memory.
    Falls back to MemorySaver if SQLite setup fails.

    Returns:
        SqliteSaver | MemorySaver: Checkpointer instance.
    """
    settings.ensure_dirs()
    try:
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver
        db_path = str(settings.checkpoint_db_path)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            saver = SqliteSaver(conn)
            return saver
        except Exception:
            conn.close()
            raise
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


def build_thread_config(thread_id: str) -> dict:
    """
    Build a LangGraph thread config dict for a given session ID.

    Args:
        thread_id: Unique identifier for the conversation thread.

    Returns:
        dict: Config dict to pass into agent.invoke().
    """
    return {"configurable": {"thread_id": thread_id}}
