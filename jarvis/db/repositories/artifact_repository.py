"""
JARVIS Artifact Repository
Tracks persistent filesystem, document, and code outputs produced by task execution.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.artifact import ArtifactModel
from jarvis.db.repositories.base import BaseRepository


class ArtifactRepository(BaseRepository[ArtifactModel]):
    def __init__(self, session: Session):
        super().__init__(session, ArtifactModel)

    def create_artifact(
        self,
        artifact_type: str,
        location: str,
        task_id: Optional[uuid.UUID] = None,
        checksum: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        artifact_id: Optional[uuid.UUID] = None,
    ) -> ArtifactModel:
        """Records an artifact record, automatically computing SHA-256 checksum if file exists."""
        computed_checksum = checksum
        if not computed_checksum and Path(location).exists() and Path(location).is_file():
            try:
                content = Path(location).read_bytes()
                computed_checksum = hashlib.sha256(content).hexdigest()
            except Exception:
                pass

        art = ArtifactModel(
            id=artifact_id or uuid.uuid4(),
            task_id=task_id,
            artifact_type=artifact_type.lower(),
            location=location,
            checksum=computed_checksum,
            metadata_json=metadata or {},
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(art)
        return art

    def get_artifact(self, artifact_id: uuid.UUID) -> Optional[ArtifactModel]:
        return self.session.query(ArtifactModel).filter(ArtifactModel.id == artifact_id).first()

    def get_task_artifacts(self, task_id: uuid.UUID) -> List[ArtifactModel]:
        return (
            self.session.query(ArtifactModel)
            .filter(ArtifactModel.task_id == task_id)
            .order_by(ArtifactModel.created_at.asc())
            .all()
        )
