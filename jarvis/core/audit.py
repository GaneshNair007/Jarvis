"""
JARVIS Cryptographic Hash-Chained Audit Ledger
Produces an append-only, tamper-evident log where every entry is chained
via SHA-256 to the previous entry's cryptographic hash.
"""

import json
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from jarvis.config import settings

class AuditLedger:
    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or settings.audit_log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_hash = self._read_last_hash()

    def _read_last_hash(self) -> str:
        """Reads the latest entry hash from the file or returns GENESIS_HASH."""
        if not self.log_path.exists():
            return self.GENESIS_HASH

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return self.GENESIS_HASH
                last_line = lines[-1].strip()
                if last_line:
                    record = json.loads(last_line)
                    return record.get("entry_hash", self.GENESIS_HASH)
        except Exception:
            return self.GENESIS_HASH
        return self.GENESIS_HASH

    def log_event(
        self,
        event_type: str,
        task_id: str,
        power_id: str,
        status: str,
        inputs: Any,
        outputs: Any,
        user_id: str = "ganesh",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Appends a new cryptographically chained audit record."""
        timestamp = time.time()
        prev_hash = self.last_hash

        # Canonical representation for hashing
        payload_data = {
            "timestamp": timestamp,
            "prev_hash": prev_hash,
            "event_type": event_type,
            "task_id": task_id,
            "power_id": power_id,
            "user_id": user_id,
            "status": status,
            "inputs": inputs,
            "outputs": outputs,
            "details": details or {}
        }

        canonical_json = json.dumps(payload_data, sort_keys=True)
        entry_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        record = {
            **payload_data,
            "entry_hash": entry_hash
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        self.last_hash = entry_hash
        return record

    def verify_integrity(self) -> Tuple[bool, int, str]:
        """
        Walks the entire audit file from line 0 to EOF, verifying the SHA-256 chain.
        Returns (valid: bool, verified_count: int, message: str).
        """
        if not self.log_path.exists():
            return True, 0, "Audit log is empty (clean state)"

        current_prev_hash = self.GENESIS_HASH
        count = 0

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                recorded_hash = record.get("entry_hash")
                record_prev_hash = record.get("prev_hash")

                # Verify chain connection
                if record_prev_hash != current_prev_hash:
                    return False, count, f"Chain broken at entry #{line_idx}: expected prev_hash {current_prev_hash}, got {record_prev_hash}"

                # Recompute hash
                payload_copy = {k: v for k, v in record.items() if k != "entry_hash"}
                computed_hash = hashlib.sha256(json.dumps(payload_copy, sort_keys=True).encode("utf-8")).hexdigest()

                if computed_hash != recorded_hash:
                    return False, count, f"Hash mismatch at entry #{line_idx}: tampered payload detected!"

                current_prev_hash = recorded_hash
                count += 1

        return True, count, f"Audit chain verified successfully across {count} records."

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line.strip()))
        return entries[-limit:]

# Singleton Audit Ledger
audit_ledger = AuditLedger()
