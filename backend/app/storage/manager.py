"""
File storage manager.

Handles safe temporary storage of uploaded and generated files.
Prevents path traversal and manages cleanup.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from typing import Optional


class StorageManager:
    """Manages uploaded and generated files safely."""

    # Maximum file size: 500 MB
    MAX_FILE_SIZE = 500 * 1024 * 1024

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.uploads_dir = os.path.join(self.base_dir, "uploads")
        self.simulations_dir = os.path.join(self.base_dir, "simulations")
        self.fixtures_dir = os.path.join(self.base_dir, "fixtures")
        
        for d in [self.uploads_dir, self.simulations_dir, self.fixtures_dir]:
            os.makedirs(d, exist_ok=True)

    def safe_filename(self, filename: str) -> str:
        """Sanitize a filename to prevent path traversal."""
        # Remove path components
        basename = os.path.basename(filename)
        # Remove non-safe characters
        safe = re.sub(r'[^\w\-._]', '_', basename)
        # Ensure non-empty
        if not safe:
            safe = "unnamed"
        return safe

    def store_upload(self, content: bytes, original_filename: str) -> tuple[str, str]:
        """
        Store an uploaded file safely.
        
        Returns:
            Tuple of (file_id, file_path)
        """
        file_id = str(uuid.uuid4())[:12]
        safe_name = self.safe_filename(original_filename)
        
        # Create a subdirectory for this upload
        upload_dir = os.path.join(self.uploads_dir, file_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, safe_name)
        
        # Verify path is within our storage
        real_path = os.path.realpath(file_path)
        if not real_path.startswith(os.path.realpath(self.uploads_dir)):
            raise ValueError("Invalid file path detected")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return file_id, file_path

    def get_upload_path(self, file_id: str) -> Optional[str]:
        """Get the path for a stored upload."""
        upload_dir = os.path.join(self.uploads_dir, file_id)
        if not os.path.isdir(upload_dir):
            return None
        
        files = os.listdir(upload_dir)
        if not files:
            return None
        
        return os.path.join(upload_dir, files[0])

    def get_file_hash(self, file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()[:16]

    def cleanup_upload(self, file_id: str) -> bool:
        """Remove an uploaded file and its directory."""
        upload_dir = os.path.join(self.uploads_dir, file_id)
        if os.path.isdir(upload_dir):
            shutil.rmtree(upload_dir)
            return True
        return False

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up files older than the specified age. Returns count removed."""
        import time
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        removed = 0
        
        for dirname in [self.uploads_dir, self.simulations_dir]:
            if not os.path.isdir(dirname):
                continue
            for name in os.listdir(dirname):
                path = os.path.join(dirname, name)
                try:
                    mtime = os.path.getmtime(path)
                    if now - mtime > max_age_seconds:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                        removed += 1
                except OSError:
                    pass
        
        return removed
