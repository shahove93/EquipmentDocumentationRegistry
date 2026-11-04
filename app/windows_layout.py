"""Installed Windows paths and source-preserving legacy transition.

Installation metadata lives outside user-writable state. No drive aliases or
environment-supplied ProgramData/profile paths are used to locate installed data.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import stat
import uuid


def no_links(path: Path):
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Links/reparse points are not supported in EDR paths")


def product_root(install: Path) -> Path:
    product = (install / "windows-product.txt").read_text(encoding="ascii").strip()
    if product not in {"EDR", "EDR-Smoke"}:
        raise ValueError("Invalid Windows product identity")
    import ctypes
    output = ctypes.create_unicode_buffer(32768)
    # CSIDL_COMMON_APPDATA, read from Windows rather than a caller's environment.
    if ctypes.windll.shell32.SHGetFolderPathW(None, 35, None, 0, output):
        raise OSError("Cannot resolve Windows ProgramData")
    root = Path(output.value) / product
    if not str(root).isascii():
        raise ValueError("EDR requires an ASCII ProgramData path")
    no_links(root)
    return root


def installed_layout(install: Path):
    root = product_root(install)
    no_links(root / "owner.json")
    owner = json.loads((root / "owner.json").read_text(encoding="utf-8-sig"))
    from app.windows_local import current_sid
    if owner.get("format") != 1 or owner.get("sid") != current_sid():
        raise PermissionError("EDR belongs to another Windows account; use the intended account")
    if (root / "maintenance").exists():
        raise RuntimeError("Installer maintenance is in progress")
    return root, Path(owner["legacy"])


def migrate_legacy(source: Path, target: Path, install: Path):
    """Copy, hash-verify and start/validate a stopped clone before atomic publish.

    Caller holds the target sibling lock. Source is never moved, removed or
    modified. A failed stage is retained and cannot be mistaken for live data.
    """
    from app.windows_local import Runtime, exclusive, private_directory, digest
    no_links(source)
    no_links(target)
    if target.exists():
        if any(target.iterdir()):
            return
        if source.exists() and any(source.iterdir()):
            raise ValueError("Legacy transition requires an absent target; empty target preserved")
        return
    if not source.exists() or not any(source.iterdir()):
        return
    with exclusive(source):
        if not (source / "runtime.json").is_file() or not (source / "postgres/PG_VERSION").is_file():
            raise ValueError("Incomplete legacy EDR data; source preserved")
        # An orphan PostgreSQL must be recovered/stopped using the old runtime.
        if (source / "postgres/postmaster.pid").exists():
            raise ValueError("Legacy PostgreSQL may be running; stop/recover the old EDR first")
        stage = target.with_name(target.name + ".migrate-" + uuid.uuid4().hex)
        private_directory(stage)
        for entry in sorted(source.rglob("*")):
            no_links(entry)
            destination = stage / entry.relative_to(source)
            info = entry.lstat()
            if stat.S_ISDIR(info.st_mode):
                destination.mkdir(exist_ok=True)
            elif stat.S_ISREG(info.st_mode):
                shutil.copyfile(entry, destination)
                if entry.stat().st_size != destination.stat().st_size or digest(entry) != digest(destination):
                    raise ValueError("Legacy copy verification failed; source preserved")
            else:
                raise ValueError("Non-regular legacy data; source preserved")
        runtime = Runtime(stage, install)
        with runtime.database():
            if not runtime.config.get("active"):
                raise ValueError("Legacy database is not initialized; source preserved")
            runtime.validate_pair(runtime.config["active"])
        # Sibling rename is atomic on Windows and refuses replacement.
        stage.rename(target)


from contextlib import contextmanager


@contextmanager
def runtime_gate(install: Path):
    """Shared read handle; installer requires exclusive access before its marker.

    This contains no user content. The installer never opens state/data or its
    lock files under an alternate administrative identity.
    """
    import ctypes
    import ctypes.wintypes as wt
    root = product_root(install)
    gate = root / "control" / "gate"
    no_links(gate)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                   wt.DWORD, wt.DWORD, wt.HANDLE]
    kernel.CreateFileW.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    handle = kernel.CreateFileW(str(gate), 0x80000000, 1, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise RuntimeError("Maintenance gate unavailable; close installer or repair installation")
    try:
        # Checked while sharing excludes the installer's exclusive open. If
        # maintenance already published its marker, no command may proceed.
        if (root / "maintenance").exists():
            raise RuntimeError("Installer maintenance is in progress")
        yield
    finally:
        kernel.CloseHandle(handle)


def checked_backup_destination(root: Path, destination: Path) -> Path:
    no_links(destination)
    destination = destination.resolve()
    if destination.parent != (root / "state" / "backups").resolve():
        raise ValueError("Windows backups must be stored directly in protected state/backups")
    return destination
