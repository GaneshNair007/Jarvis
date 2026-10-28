"""
JARVIS Ingestors Package.
"""

from search.ingestors.base_ingestor import BaseIngestor
from search.ingestors.browser_page_ingestor import BrowserPageIngestor
from search.ingestors.chat_history_ingestor import ChatHistoryIngestor
from search.ingestors.code_repo_ingestor import CodeRepoIngestor
from search.ingestors.email_ingestor import EmailIngestor
from search.ingestors.file_ingestor import FileIngestor
from search.ingestors.markdown_ingestor import MarkdownIngestor
from search.ingestors.notes_ingestor import NotesIngestor
from search.ingestors.pdf_ingestor import PDFIngestor
from search.ingestors.web_cache_ingestor import WebCacheIngestor

__all__ = [
    "BaseIngestor",
    "FileIngestor",
    "PDFIngestor",
    "MarkdownIngestor",
    "CodeRepoIngestor",
    "BrowserPageIngestor",
    "EmailIngestor",
    "ChatHistoryIngestor",
    "NotesIngestor",
    "WebCacheIngestor",
]
