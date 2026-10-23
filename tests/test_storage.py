import io
import os
import stat
from pathlib import Path

import pytest

from app.services import local_storage
from app.services.local_storage import (
    LocalStorageBackend,
    StorageInventoryError,
    StoredFileInfo,
)
from app.services.storage import (
    FileAlreadyExistsError,
    StorageBackend,
    StorageError,
    StorageKeyError,
    StoredFileNotFoundError,
)

KEY = "documents/42/9f1c2b3a-4d5e-4f60-8712-a3b4c5d6e7f8.pdf"


@pytest.fixture
def backend(tmp_path):
    return LocalStorageBackend(root_path=tmp_path / "storage")


class TestInterface:
    def test_local_backend_implements_interface(self, backend):
        assert isinstance(backend, StorageBackend)

    def test_interface_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            StorageBackend()

    def test_default_root_path_is_storage(self):
        assert LocalStorageBackend().root_path.name == "storage"

    def test_all_errors_share_base_class(self):
        for error in (StorageKeyError, FileAlreadyExistsError, StoredFileNotFoundError):
            assert issubclass(error, StorageError)


class TestSaveAndOpen:
    def test_save_creates_file_on_disk(self, backend, tmp_path):
        backend.save(KEY, io.BytesIO(b"hello"))
        assert (tmp_path / "storage" / KEY).is_file()

    def test_open_returns_stored_bytes(self, backend):
        backend.save(KEY, io.BytesIO(b"hello world"))
        with backend.open(KEY) as stream:
            assert stream.read() == b"hello world"

    def test_open_returns_binary_stream(self, backend):
        backend.save(KEY, io.BytesIO(b"abc"))
        with backend.open(KEY) as stream:
            data = stream.read()
        assert isinstance(data, bytes)
        assert data == b"abc"

    def test_open_missing_file_raises_clear_error(self, backend):
        with pytest.raises(StoredFileNotFoundError) as info:
            backend.open("documents/1/missing.pdf")
        assert "documents/1/missing.pdf" in str(info.value)

    def test_save_creates_nested_directories(self, backend, tmp_path):
        key = "documents/7/a/b/c/deep.pdf"
        backend.save(key, io.BytesIO(b"deep"))
        assert (tmp_path / "storage" / "documents" / "7" / "a" / "b" / "c" / "deep.pdf").is_file()

    def test_save_accepts_empty_content(self, backend):
        backend.save("documents/1/empty.pdf", io.BytesIO(b""))
        assert backend.exists("documents/1/empty.pdf")


class TestExists:
    def test_exists_false_before_save(self, backend):
        assert backend.exists(KEY) is False

    def test_exists_true_after_save(self, backend):
        backend.save(KEY, io.BytesIO(b"x"))
        assert backend.exists(KEY) is True

    def test_exists_false_after_delete(self, backend):
        backend.save(KEY, io.BytesIO(b"x"))
        backend.delete(KEY)
        assert backend.exists(KEY) is False

    def test_exists_returns_real_boolean(self, backend):
        assert backend.exists(KEY) is False


class TestDelete:
    def test_delete_removes_file(self, backend, tmp_path):
        backend.save(KEY, io.BytesIO(b"bye"))
        backend.delete(KEY)
        assert not (tmp_path / "storage" / KEY).exists()

    def test_repeated_delete_is_safe(self, backend):
        backend.save(KEY, io.BytesIO(b"bye"))
        backend.delete(KEY)
        backend.delete(KEY)
        backend.delete(KEY)
        assert backend.exists(KEY) is False

    def test_delete_missing_file_is_safe(self, backend):
        backend.delete("documents/999/never-existed.pdf")

    def test_delete_keeps_siblings(self, backend):
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        backend.save("documents/1/b.pdf", io.BytesIO(b"b"))
        backend.delete("documents/1/a.pdf")
        assert backend.exists("documents/1/b.pdf") is True


class TestNoOverwrite:
    def test_duplicate_storage_key_rejected(self, backend):
        backend.save(KEY, io.BytesIO(b"first"))
        with pytest.raises(FileAlreadyExistsError) as info:
            backend.save(KEY, io.BytesIO(b"second"))
        assert KEY in str(info.value)

    def test_original_content_survives_failed_overwrite(self, backend):
        backend.save(KEY, io.BytesIO(b"first"))
        with pytest.raises(FileAlreadyExistsError):
            backend.save(KEY, io.BytesIO(b"second"))
        with backend.open(KEY) as stream:
            assert stream.read() == b"first"

    def test_exists_reports_key_as_taken(self, backend):
        backend.save(KEY, io.BytesIO(b"first"))
        with pytest.raises(FileAlreadyExistsError):
            backend.save(KEY, io.BytesIO(b"second"))
        assert backend.exists(KEY) is True


class TestPathTraversal:
    @pytest.mark.parametrize(
        "key",
        [
            "../escape.pdf",
            "documents/../../escape.pdf",
            "documents/42/../../../escape.pdf",
            "..",
            "documents/..",
        ],
    )
    def test_dotdot_rejected(self, backend, key):
        with pytest.raises(StorageKeyError):
            backend.save(key, io.BytesIO(b"x"))

    @pytest.mark.parametrize(
        "key",
        [
            "/etc/passwd",
            "/documents/42/file.pdf",
            "\\windows\\system32\\file.pdf",
            "//server/share/file.pdf",
        ],
    )
    def test_absolute_paths_rejected(self, backend, key):
        with pytest.raises(StorageKeyError):
            backend.save(key, io.BytesIO(b"x"))

    @pytest.mark.parametrize(
        "key",
        [
            "documents\\42\\file.pdf",
            "C:/documents/file.pdf",
            "C:\\documents\\file.pdf",
        ],
    )
    def test_windows_paths_rejected(self, backend, key):
        with pytest.raises(StorageKeyError):
            backend.save(key, io.BytesIO(b"x"))

    def test_nothing_written_outside_root(self, backend, tmp_path):
        with pytest.raises(StorageKeyError):
            backend.save("../escape.pdf", io.BytesIO(b"x"))
        assert not (tmp_path / "escape.pdf").exists()

    @pytest.mark.parametrize("key", ["", "   ", "."])
    def test_empty_or_dot_key_rejected(self, backend, key):
        with pytest.raises(StorageKeyError):
            backend.save(key, io.BytesIO(b"x"))

    def test_null_byte_rejected(self, backend):
        with pytest.raises(StorageKeyError):
            backend.save("documents/42/file\x00.pdf", io.BytesIO(b"x"))

    def test_non_string_key_rejected(self, backend):
        with pytest.raises(StorageKeyError):
            backend.save(42, io.BytesIO(b"x"))

    @pytest.mark.parametrize("operation", ["open", "exists", "delete"])
    def test_traversal_blocked_on_every_operation(self, backend, operation):
        with pytest.raises(StorageKeyError):
            if operation == "open":
                backend.open("../escape.pdf")
            elif operation == "exists":
                backend.exists("../escape.pdf")
            else:
                backend.delete("../escape.pdf")

    def test_symlink_out_of_root_is_not_followed(self, backend, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.pdf"
        secret.write_bytes(b"secret")
        link = tmp_path / "storage" / "link"
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(outside, link)
        # link/secret.pdf resolves outside the root and must be refused
        with pytest.raises(StorageKeyError):
            backend.save("link/secret.pdf", io.BytesIO(b"x"))


class TestBinaryFidelity:
    def test_all_byte_values_round_trip(self, backend):
        payload = bytes(range(256))
        backend.save("documents/1/all-bytes.bin", io.BytesIO(payload))
        with backend.open("documents/1/all-bytes.bin") as stream:
            assert stream.read() == payload

    def test_pdf_magic_bytes_preserved(self, backend):
        payload = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nbinary\x00data"
        backend.save("documents/1/doc.pdf", io.BytesIO(payload))
        with backend.open("documents/1/doc.pdf") as stream:
            assert stream.read() == payload

    def test_null_bytes_preserved(self, backend):
        payload = b"\x00" * 1024
        backend.save("documents/1/zeros.bin", io.BytesIO(payload))
        with backend.open("documents/1/zeros.bin") as stream:
            assert stream.read() == payload

    def test_reads_in_chunks_not_whole_file(self, backend):
        from app.services import local_storage

        sizes = []

        class CountingStream:
            def __init__(self, payload):
                self._buffer = io.BytesIO(payload)

            def read(self, size=-1):
                sizes.append(size)
                return self._buffer.read(size)

        backend.save(
            "documents/1/stream.bin", CountingStream(b"x" * 200_000)
        )

        assert sizes, "source.read was never called"
        assert all(size == local_storage.CHUNK_SIZE for size in sizes)
        assert len(sizes) > 1, "file was read in a single chunk"

    def test_large_stream_written_completely(self, backend):
        payload = os.urandom(3 * 1024 * 1024)
        backend.save("documents/1/large.bin", io.BytesIO(payload))
        path = backend.root_path / "documents" / "1" / "large.bin"
        assert path.stat().st_size == len(payload)
        with backend.open("documents/1/large.bin") as stream:
            assert stream.read() == payload

    def test_file_on_disk_is_regular_file(self, backend):
        backend.save(KEY, io.BytesIO(b"x"))
        mode = (backend.root_path / KEY).stat().st_mode
        assert stat.S_ISREG(mode)


class TestPartialWriteCleanup:
    def test_failed_stream_leaves_no_partial_file(self, backend):
        class BrokenStream:
            def __init__(self):
                self._sent = False

            def read(self, size=-1):
                if self._sent:
                    raise OSError("source stream failed")
                self._sent = True
                return b"partial"

        with pytest.raises(OSError):
            backend.save(KEY, BrokenStream())
        assert backend.exists(KEY) is False


class TestIterFiles:
    def test_yields_regular_files_recursively(self, backend):
        backend.save("documents/1/a.pdf", io.BytesIO(b"one"))
        backend.save("documents/1/nested/b.jpg", io.BytesIO(b"two"))
        backend.save("documents/2/c.png", io.BytesIO(b"three"))
        backend.save("other/ignored.pdf", io.BytesIO(b"outside"))

        found = {
            info.storage_key: info for info in backend.iter_files("documents")
        }

        assert set(found) == {
            "documents/1/a.pdf",
            "documents/1/nested/b.jpg",
            "documents/2/c.png",
        }
        assert all(isinstance(info, StoredFileInfo) for info in found.values())

    def test_uses_forward_slash_storage_keys(self, backend):
        backend.save("documents/7/x.pdf", io.BytesIO(b"x"))
        keys = [info.storage_key for info in backend.iter_files("documents")]
        assert keys == ["documents/7/x.pdf"]

    def test_reports_size_and_utc_timestamp(self, backend):
        backend.save("documents/1/size.pdf", io.BytesIO(b"123456789"))

        info = next(backend.iter_files("documents"))

        assert info.size_bytes == 9
        assert info.modified_at.tzinfo is not None
        assert info.modified_at.utcoffset().total_seconds() == 0

    def test_zero_byte_file_is_yielded(self, backend):
        backend.save("documents/1/zero.pdf", io.BytesIO(b""))
        info = next(backend.iter_files("documents"))
        assert info.size_bytes == 0

    def test_missing_prefix_yields_nothing(self, backend):
        backend.save("documents/1/a.pdf", io.BytesIO(b"x"))
        assert list(backend.iter_files("missing")) == []

    def test_trailing_slash_is_accepted(self, backend):
        backend.save("documents/1/a.pdf", io.BytesIO(b"x"))
        assert [i.storage_key for i in backend.iter_files("documents/")] == [
            "documents/1/a.pdf"
        ]

    def test_missing_root_raises(self, backend):
        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))
        assert info.value.code == "storage_root_missing"
        assert not backend.root_path.exists()

    def test_root_that_is_a_file_raises(self, tmp_path):
        root = tmp_path / "storage"
        root.write_bytes(b"not a directory")
        backend = LocalStorageBackend(root_path=root)

        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))

        assert info.value.code == "storage_root_not_directory"

    @pytest.mark.parametrize(
        "prefix",
        [
            "",
            " ",
            ".",
            "..",
            "/documents",
            "\\documents",
            "documents\\1",
            "C:/documents",
            "documents/../escape",
            "documents//nested",
            42,
        ],
    )
    def test_invalid_prefix_is_rejected(self, backend, prefix):
        backend.save("documents/1/a.pdf", io.BytesIO(b"x"))
        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files(prefix))
        assert info.value.code == "storage_prefix_invalid"

    def test_namespace_that_is_a_file_raises(self, backend):
        backend.root_path.mkdir(parents=True)
        (backend.root_path / "documents").write_bytes(b"not a directory")

        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))

        assert info.value.code == "storage_namespace_not_directory"

    def test_namespace_symlink_is_not_followed(self, tmp_path):
        root = tmp_path / "storage"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.pdf").write_bytes(b"secret")
        os.symlink(outside, root / "documents")
        backend = LocalStorageBackend(root_path=root)

        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))

        assert info.value.code == "storage_namespace_not_directory"

    def test_namespace_symlink_inside_root_is_not_followed(self, tmp_path):
        root = tmp_path / "storage"
        real = root / "real"
        real.mkdir(parents=True)
        (real / "inside.pdf").write_bytes(b"inside")
        os.symlink(real, root / "documents")
        backend = LocalStorageBackend(root_path=root)

        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))

        assert info.value.code == "storage_namespace_not_directory"

    def test_symlinked_file_is_not_yielded(self, backend, tmp_path):
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.pdf"
        secret.write_bytes(b"secret")
        os.symlink(secret, backend.root_path / "documents" / "1" / "secret.pdf")

        keys = [info.storage_key for info in backend.iter_files("documents")]

        assert keys == ["documents/1/a.pdf"]

    def test_symlinked_directory_is_not_followed(self, backend, tmp_path):
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.pdf").write_bytes(b"secret")
        os.symlink(outside, backend.root_path / "documents" / "link")

        keys = [info.storage_key for info in backend.iter_files("documents")]

        assert keys == ["documents/1/a.pdf"]

    def test_special_files_are_not_yielded(self, backend):
        if not hasattr(os, "mkfifo"):
            pytest.skip("os.mkfifo is unavailable")
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        os.mkfifo(backend.root_path / "documents" / "1" / "pipe.pdf")

        keys = [info.storage_key for info in backend.iter_files("documents")]

        assert keys == ["documents/1/a.pdf"]

    def test_unreadable_subdirectory_raises(self, backend):
        if not hasattr(os, "geteuid") or os.geteuid() == 0:
            pytest.skip("permission checks are not meaningful for this user")
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        locked = backend.root_path / "documents" / "locked"
        locked.mkdir()
        (locked / "hidden.pdf").write_bytes(b"hidden")
        locked.chmod(0)

        try:
            with pytest.raises(StorageInventoryError) as info:
                list(backend.iter_files("documents"))
        finally:
            locked.chmod(0o700)

        assert info.value.code == "storage_unreadable"

    def test_vanished_entry_raises(self, backend, monkeypatch):
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        real_listdir = os.listdir

        def listdir_with_ghost(directory_fd):
            return [*real_listdir(directory_fd), "ghost.pdf"]

        monkeypatch.setattr(local_storage.os, "listdir", listdir_with_ghost)

        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))

        assert info.value.code == "storage_entry_vanished"

    def test_directory_swapped_for_outside_symlink_is_not_followed(
        self, backend, tmp_path, monkeypatch
    ):
        if not hasattr(os, "symlink"):
            pytest.skip("os.symlink is unavailable")
        backend.save("documents/1/a.pdf", io.BytesIO(b"a"))
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.pdf").write_bytes(b"secret")
        documents = backend.root_path / "documents"
        moved = backend.root_path / "documents-real"

        real_open = local_storage.os.open
        real_stat = local_storage.os.stat
        real_listdir = local_storage.os.listdir
        real_read = local_storage.os.read
        opened_paths = {}
        external_access = []
        swapped = {"value": False}

        def is_within(candidate, base):
            return candidate == base or base in candidate.parents

        def record_external(kind, target):
            if target is None or not swapped["value"]:
                return
            if is_within(target, documents) or is_within(target, outside):
                external_access.append((kind, str(target)))

        def injected_open(path, flags, mode=0o777, *, dir_fd=None):
            if dir_fd is not None and path == "documents":
                if not swapped["value"]:
                    documents.rename(moved)
                    os.symlink(outside, documents)
                    swapped["value"] = True
            if dir_fd is None:
                target = None if isinstance(path, int) else Path(path)
                fd = real_open(path, flags, mode)
                opened_paths[fd] = target
                record_external("open", target)
            else:
                base = opened_paths.get(dir_fd)
                fd = real_open(path, flags, mode, dir_fd=dir_fd)
                target = base / path if base is not None else None
                opened_paths[fd] = target
                record_external("open", target)
            return fd

        def injected_stat(path, *args, **kwargs):
            dir_fd = kwargs.get("dir_fd")
            if isinstance(path, (str, os.PathLike)) and dir_fd is not None:
                base = opened_paths.get(dir_fd)
                if base is not None:
                    record_external("stat", base / path)
            elif isinstance(path, (str, os.PathLike)):
                record_external("stat", Path(path))
            return real_stat(path, *args, **kwargs)

        def injected_listdir(path="."):
            if isinstance(path, int):
                record_external("listdir", opened_paths.get(path))
            else:
                record_external("listdir", Path(path))
            return real_listdir(path)

        def injected_read(fd, size):
            record_external("read", opened_paths.get(fd))
            return real_read(fd, size)

        monkeypatch.setattr(local_storage.os, "open", injected_open)
        monkeypatch.setattr(local_storage.os, "stat", injected_stat)
        monkeypatch.setattr(local_storage.os, "listdir", injected_listdir)
        monkeypatch.setattr(local_storage.os, "read", injected_read)

        with pytest.raises(StorageInventoryError) as info:
            list(backend.iter_files("documents"))

        assert swapped["value"] is True
        assert external_access == []
        assert info.value.code == "storage_namespace_not_directory"

    def test_nothing_outside_root_is_read(self, tmp_path):
        root = tmp_path / "storage"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.pdf").write_bytes(b"secret")
        os.symlink(outside / "secret.pdf", root / "documents-link.pdf")
        (root / "documents").mkdir()
        os.symlink(outside, root / "documents" / "outside")

        backend = LocalStorageBackend(root_path=root)

        assert list(backend.iter_files("documents")) == []