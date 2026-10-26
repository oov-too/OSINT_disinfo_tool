"""The acquire layer (phase 3 of tools/platform-plan.md, 2026-10-22): adapters that fetch an item, hold it byte-for-byte in the hold
schema of tools/hold-schema.md, write its README and return a manifest row. See README.md in this folder.

    from ledger.acquire import youtube, web, document, bulk, canon, database, transcribe
"""
__version__ = "1.0"

ADAPTERS = {
    # name: (module, class, what it wraps)
    "youtube": ("ledger.acquire.youtube", "YouTubeAdapter", "tools/fetch_transcript.py (import), fetch_description.py (runpy), fetch_video.py's cleaning and gap"),
    "web": ("ledger.acquire.web", "WebAdapter", "tools/reddit_rss_patch.py (import: renderer, feed body, containment, prefix match)"),
    "document": ("ledger.acquire.document", "DocumentAdapter", "pypdf; PyMuPDF or pdftoppm; tools/ocr_vision.swift (compiled) or Tesseract; tools/stargate_index.py quality()"),
    "bulk": ("ledger.acquire.bulk", "BulkArchiveAdapter", "tools/stargate_mirror.py fetch() and tools/stargate_index.py quality() (import)"),
    "canon": ("ledger.acquire.canon", "CanonAdapter", "tools/fetch_kjv.py, fetch_tanakh.py, fetch_samaritan.py, fetch_isaiah_scroll.py (run with writes redirected)"),
    "database": ("ledger.acquire.database", "DatabaseAdapter", "sqlite3 and csv; the Engine extension point for other engines"),
    "transcribe": ("ledger.acquire.transcribe", "TranscribeAdapter", "openai-whisper or faster-whisper with local weights"),
    "published": ("ledger.acquire.published", "PublishedTranscriptAdapter", "the web adapter; a venue's own transcript with its recordings linked"),
}
