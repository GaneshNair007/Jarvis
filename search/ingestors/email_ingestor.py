"""
JARVIS Email Ingestor.
Ingests email threads, drafts, and communications with sender,
recipient, subject, and date provenance.
"""

from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class EmailIngestor(BaseIngestor):
    async def ingest_email(
        self,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        recipients: List[str],
        date_str: Optional[str] = None,
    ) -> bool:
        """Ingest email thread with sender/date metadata."""
        content = f"Subject: {subject}\nFrom: {sender}\nTo: {', '.join(recipients)}\nDate: {date_str or 'Recent'}\n\n{body}"
        doc_id = f"email:{email_id}"

        prov = self.build_provenance(
            source_type="email",
            author=sender,
            extra={
                "email_id": email_id,
                "recipients": recipients,
                "date": date_str,
            },
        )

        return await self.index_document(
            doc_id=doc_id,
            title=f"Email: {subject}",
            content=content,
            source_type="email",
            source_url=f"email://{email_id}",
            metadata={"sender": sender, "subject": subject},
            provenance=prov,
        )
