from pathlib import Path

import pytest
from google.api_core.exceptions import PreconditionFailed

from ingestion.gcs_uploader import file_md5_base64, upload_file_idempotent


class FakeBlob:
    def __init__(self, size: int, md5_hash: str, exists: bool = False) -> None:
        self.size = size
        self.md5_hash = md5_hash
        self.exists = exists

    def upload_from_filename(self, filename: Path, **kwargs: object) -> None:
        if self.exists:
            raise PreconditionFailed("already exists")
        self.exists = True

    def reload(self) -> None:
        if not self.exists:
            raise AssertionError("fake blob should exist")


class FakeBucket:
    name = "test-bucket"

    def __init__(self, blob: FakeBlob) -> None:
        self._blob = blob

    def blob(self, name: str) -> FakeBlob:
        return self._blob


def test_file_md5_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("data", encoding="utf-8")
    assert file_md5_base64(path) == file_md5_base64(path)


def test_upload_creates_object_with_create_only_precondition(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("data", encoding="utf-8")
    blob = FakeBlob(size=path.stat().st_size, md5_hash=file_md5_base64(path))

    result = upload_file_idempotent(FakeBucket(blob), path, "prefix/file.txt")

    assert result["status"] == "uploaded"


def test_upload_accepts_existing_object_with_same_content(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("data", encoding="utf-8")
    blob = FakeBlob(
        size=path.stat().st_size,
        md5_hash=file_md5_base64(path),
        exists=True,
    )

    result = upload_file_idempotent(FakeBucket(blob), path, "prefix/file.txt")

    assert result["status"] == "already_exists_same_content"


def test_upload_rejects_existing_object_with_different_content(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("data", encoding="utf-8")
    blob = FakeBlob(size=999, md5_hash="different", exists=True)

    with pytest.raises(RuntimeError, match="conteúdo diferente"):
        upload_file_idempotent(FakeBucket(blob), path, "prefix/file.txt")
