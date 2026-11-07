import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


class UploadError(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Artifact:
    key: str
    sha256: str
    byte_size: int


class Artifacts:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"(originals|results)/[a-f0-9]{32}\.(pdf|json)", key):
            raise ValueError("Invalid artifact key")
        return self.root / key

    def save_pdf(self, stream: BinaryIO, limit: int) -> Artifact:
        header = stream.read(5)
        if header != b"%PDF-":
            raise UploadError("Expected a PDF file", 415)
        stream.seek(0)
        return self._save(stream, "originals", "pdf", limit)

    def save_result(self, raw: dict) -> Artifact:
        from io import BytesIO

        payload = json.dumps(raw, ensure_ascii=False, allow_nan=False).encode()
        return self._save(BytesIO(payload), "results", "json", None)

    def _save(self, stream, folder, suffix, limit):
        directory = self.root / folder
        directory.mkdir(exist_ok=True)
        key = f"{folder}/{uuid4().hex}.{suffix}"
        destination = self.path(key)
        temporary = destination.with_suffix(".tmp")
        digest, count = hashlib.sha256(), 0
        try:
            with temporary.open("xb") as target:
                while block := stream.read(1024 * 1024):
                    count += len(block)
                    if limit is not None and count > limit:
                        raise UploadError("PDF exceeds the upload limit", 413)
                    digest.update(block)
                    target.write(block)
                target.flush()
                os.fsync(target.fileno())
            temporary.rename(destination)
            self._sync_directory(directory)
            self._sync_directory(self.root)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return Artifact(key, digest.hexdigest(), count)

    def verify(self, artifact: dict) -> Path:
        path = self.path(artifact["storage_key"])
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError("Stored PDF hash does not match its accepted identity")
        return path

    def discard(self, key: str):
        self.path(key).unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(directory):
        if os.name != "nt":
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
