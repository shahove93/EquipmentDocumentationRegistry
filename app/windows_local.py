"""Per-user Windows supervisor, offline backup/restore and copy-on-migrate.

No services, global PATH edits or system PostgreSQL instances are used. Only this
module starts the packaged API; configuration is not read from a developer .env.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import zipfile

API_PORT = 18765
PG_PORT = 55432
PG_MAJOR = "18"
INSTALL = Path(__file__).resolve().parents[1]
is_windows_reserved = getattr(ntpath, "isreserved", lambda name: PureWindowsPath(name).is_reserved())


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + ".new")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Busy(RuntimeError):
    pass


@contextmanager
def exclusive(data: Path):
    """A persistent sibling lock also guards restore into an empty directory."""
    data.parent.mkdir(parents=True, exist_ok=True)
    with data.with_name(data.name + ".lock").open("a+b") as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("EDR is running or maintenance is in progress; stop it first") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def checked_data(path: Path, install: Path = INSTALL) -> Path:
    data = path.resolve()
    installation = install.resolve()
    if data == installation or installation in data.parents or data in installation.parents:
        raise ValueError("Data and installation directories must be separate")
    if data == data.parent:
        raise ValueError("A filesystem root cannot be a data directory")
    return data


def private_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        # Numeric SID works with non-English Windows and Cyrillic user names.
        import ctypes
        import ctypes.wintypes as wt
        token = wt.HANDLE()
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wt.HANDLE
        kernel.CloseHandle.argtypes = [wt.HANDLE]
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        advapi.OpenProcessToken.argtypes = [wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE)]
        advapi.GetTokenInformation.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise OSError("Cannot read user token")
        try:
            size = wt.DWORD()
            advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
                raise OSError("Cannot read user SID")
            sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
            sid_text = wt.LPWSTR()
            advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.LPWSTR)]
            if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
                raise OSError("Cannot convert user SID")
            try:
                subprocess.run(["icacls.exe", str(path), "/inheritance:r", "/grant:r",
                                f"*{sid_text.value}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
                               check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            finally:
                kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        finally:
            kernel.CloseHandle(token)
    else:
        path.chmod(0o700)


def ensure_port_free(port):
    with socket.socket() as sock:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", port))


def postgres_path(path: Path) -> str:
    """EDB's initdb embeds Windows ANSI paths in bootstrap SQL; use ASCII aliases.

    Never change Windows' system locale or move existing data to work around it.
    On volumes without 8.3 aliases, fail before invoking PostgreSQL and explain
    that an ASCII installation/data path is required.
    """
    if os.name != "nt":
        return str(path)
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    kernel.GetShortPathNameW.restype = ctypes.c_uint
    existing = path.resolve()
    suffix = []
    while not existing.exists():
        if existing.parent == existing:
            raise OSError("PostgreSQL filesystem root is unavailable")
        suffix.insert(0, existing.name)
        existing = existing.parent
    output = ctypes.create_unicode_buffer(32768)
    if not kernel.GetShortPathNameW(str(existing), output, len(output)):
        raise OSError("Cannot resolve PostgreSQL filesystem path")
    result = str(Path(output.value).joinpath(*suffix))
    if not result.isascii():
        raise ValueError("PostgreSQL requires ASCII installation/data paths or available Windows 8.3 aliases; existing data preserved")
    return result


class Runtime:
    def __init__(self, data: Path, install: Path = INSTALL, *, restoring=False):
        self.data = checked_data(data, install)
        self.install = install
        self.pg = install / "postgresql" / "bin"
        self.cluster = data / "postgres"
        self.config = None
        self.restoring = restoring

    def run(self, program, *args, database="postgres", check=True):
        env = os.environ.copy()
        env.update(PGHOST="127.0.0.1", PGPORT=str(PG_PORT), PGUSER="edr",
                   PGDATABASE=database, PGPASSWORD=self.config["password"] if self.config else "",
                   PGCONNECT_TIMEOUT="10", PGCLIENTENCODING="UTF8")
        # Never trust external libpq service/options configuration.
        for name in ("PGSERVICE", "PGSERVICEFILE", "PGOPTIONS"):
            env.pop(name, None)
        # On Windows pg_ctl's server can inherit stdout even with -l. PIPE would
        # keep communicate() waiting for EOF until the server itself exits.
        with (self.data / "logs" / "runtime.log").open("a", encoding="utf-8") as log:
            log.write(f"\n{program}\n")
            log.flush()
            result = subprocess.run([postgres_path(self.pg / (program + ".exe")),
                                     *(postgres_path(arg) if isinstance(arg, Path) else str(arg) for arg in args)],
                                    env=env, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=0x08000000 if os.name == "nt" else 0)
        if check and result.returncode:
            # No command/env/password echo; full DB diagnostic stays in local PG logs.
            raise RuntimeError(f"{program} failed (exit {result.returncode}); see {self.data / 'logs'}")
        return result

    def initialize(self):
        settings = self.data / "runtime.json"
        if (self.data.exists() and any(self.data.iterdir()) and not settings.exists()
                and not self.restoring):
            raise ValueError("Refusing a nonempty directory without EDR runtime.json")
        private_directory(self.data)
        (self.data / "logs").mkdir(exist_ok=True)
        (self.data / "attachments").mkdir(exist_ok=True)
        if settings.exists():
            self.config = read_json(settings)
        else:
            if self.cluster.exists():
                raise RuntimeError("Cluster exists without runtime.json; data preserved, recovery required")
            self.config = {"format": 1, "password": secrets.token_hex(32), "active": None, "revision": None}
            atomic_json(settings, self.config)
        if not self.cluster.exists():
            if self.config["active"]:
                raise RuntimeError("Active database cluster is missing; restore a backup")
            password = self.data / "init-password.tmp"
            try:
                password.write_text(self.config["password"], encoding="utf-8")
                self.run("initdb", "-D", self.cluster, "--username=edr", "--encoding=UTF8",
                         "--locale=C", "--auth-host=scram-sha-256", "--auth-local=scram-sha-256",
                         "--pwfile", password)
            finally:
                password.unlink(missing_ok=True)
        if (self.cluster / "PG_VERSION").read_text().strip() != PG_MAJOR:
            raise RuntimeError("Unsupported PostgreSQL major version; original cluster preserved")
        # Always restrict startup, including after configuration was changed externally.
        (self.cluster / "pg_hba.conf").write_text(
            "host all edr 127.0.0.1/32 scram-sha-256\nhost all all 0.0.0.0/0 reject\nhost all all ::/0 reject\n",
            encoding="ascii")

    @contextmanager
    def database(self):
        self.initialize()
        # Exclusive supervisor lock proves that an existing process is an orphan.
        if self.run("pg_ctl", "-D", self.cluster, "status", check=False).returncode == 0:
            self.run("pg_ctl", "-D", self.cluster, "-m", "fast", "-w", "stop")
        ensure_port_free(PG_PORT)
        options = f"-h 127.0.0.1 -p {PG_PORT} -c unix_socket_directories= -c password_encryption=scram-sha-256"
        self.run("pg_ctl", "-D", self.cluster, "-l", self.data / "logs" / "postgres.log",
                 "-o", options, "-w", "-t", "60", "start")
        try:
            yield
        finally:
            self.run("pg_ctl", "-D", self.cluster, "-m", "fast", "-w", "-t", "60", "stop")

    def configure_app(self, database):
        # Credentials are generated as hex; URL escaping is unnecessary.
        os.environ["DATABASE_URL"] = f"postgresql+psycopg://edr:{self.config['password']}@127.0.0.1:{PG_PORT}/{database}"
        os.environ["STORAGE_ROOT"] = str(self.data / "attachments")
        os.environ["LOG_FILE"] = str(self.data / "logs" / "app.log")

    def query(self, database, sql):
        import psycopg
        with psycopg.connect(host="127.0.0.1", port=PG_PORT, user="edr",
                             password=self.config["password"], dbname=database) as connection:
            return connection.execute(sql).fetchall()

    def validate_pair(self, database):
        from app.services.local_storage import LocalStorageBackend
        storage = LocalStorageBackend(self.data / "attachments")
        for key, size, sha in self.query(database, "SELECT storage_key, size_bytes, sha256 FROM files"):
            path = storage._resolve(key)
            if not path.is_file() or path.stat().st_size != size or digest(path) != sha:
                raise ValueError("Database/attachment pair is incomplete or corrupt; original data preserved")

    def migrate(self):
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(str(self.install / "alembic.ini"))
        head = ScriptDirectory.from_config(cfg).get_current_head()
        if self.config["active"] and self.config["revision"] == head:
            return
        candidate = "edr_" + uuid.uuid4().hex
        # TEMPLATE clones the stopped API's DB with no mutation of the original.
        args = ["--template", self.config["active"]] if self.config["active"] else []
        self.run("createdb", *args, candidate)
        self.configure_app(candidate)
        command.upgrade(cfg, "head")
        updated = dict(self.config, active=candidate, revision=head)
        atomic_json(self.data / "runtime.json", updated)
        self.config = updated
        # Old/candidate databases are deliberately retained for manual recovery.

    def start(self, open_browser=True):
        ensure_port_free(API_PORT)
        with self.database():
            self.migrate()
            self.configure_app(self.config["active"])
            from app.main import app
            from app.local_web import LocalWeb
            import uvicorn
            server = uvicorn.Server(uvicorn.Config(
                LocalWeb(app, self.install / "ui", API_PORT), host="127.0.0.1", port=API_PORT,
                proxy_headers=False, access_log=False, log_config=None, lifespan="on"))
            nonce = uuid.uuid4().hex
            request = self.data / "stop.json"
            request.unlink(missing_ok=True)
            atomic_json(self.data / "running.json", {"nonce": nonce, "pid": os.getpid()})
            def monitor():
                while not server.should_exit:
                    if request.exists() and read_json(request).get("nonce") == nonce:
                        server.should_exit = True
                        return
                    if server.started and open_browser:
                        webbrowser.open(f"http://127.0.0.1:{API_PORT}/")
                        break
                    time.sleep(.2)
                while not server.should_exit:
                    if request.exists() and read_json(request).get("nonce") == nonce:
                        server.should_exit = True
                    time.sleep(.2)
            threading.Thread(target=monitor, daemon=True).start()
            try:
                server.run()
            finally:
                (self.data / "running.json").unlink(missing_ok=True)
                request.unlink(missing_ok=True)

    def backup(self, destination: Path):
        if destination.exists() or self.data == destination or self.data in destination.parents:
            raise ValueError("Backup must be a new file outside the data directory")
        with self.database():
            if not self.config["active"]:
                raise RuntimeError("There is no initialized application database")
            self.validate_pair(self.config["active"])
            # No API runs while this exclusive lock is held: rows and blobs cannot change.
            dump = self.data / ("backup-" + uuid.uuid4().hex + ".dump")
            temporary = destination.with_name(destination.name + ".partial-" + uuid.uuid4().hex)
            try:
                self.run("pg_dump", "-Fc", "--no-owner", "--no-acl", "-f", dump,
                         database=self.config["active"])
                files = {"database.dump": dump}
                for source in regular_files(self.data / "attachments"):
                    files["attachments/" + source.relative_to(self.data / "attachments").as_posix()] = source
                manifest = {"format": 1, "postgres_major": PG_MAJOR,
                            "revision": self.config["revision"], "files": {}}
                with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                    for name, source in files.items():
                        manifest["files"][name] = {"sha256": digest(source), "size": source.stat().st_size}
                        archive.write(source, name)
                    archive.writestr("manifest.json", json.dumps(manifest))
                # Windows rename refuses replacement of an existing destination.
                if destination.exists():
                    raise FileExistsError(destination)
                temporary.rename(destination)
            finally:
                dump.unlink(missing_ok=True)
                temporary.unlink(missing_ok=True)


def regular_files(root: Path):
    root_info = root.lstat()
    if root.is_symlink() or getattr(root_info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Links/reparse points are not supported in backup data")
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Links/reparse points are not supported in backup data")
        if stat.S_ISREG(info.st_mode):
            yield path
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError("Only regular attachment files can be backed up")


def digest(path: Path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def unpack_backup(backup: Path, stage: Path):
    """Validate a closed archive before any live data directory is published."""
    with zipfile.ZipFile(backup) as archive:
        names = archive.namelist()
        if len(names) != len(set(n.casefold() for n in names)):
            raise ValueError("Duplicate backup entries")
        if archive.getinfo("manifest.json").file_size > 16 * 1024 * 1024:
            raise ValueError("Backup manifest is too large")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest["format"] != 1 or manifest["postgres_major"] != PG_MAJOR:
            raise ValueError("Unsupported backup format/PostgreSQL major")
        if set(names) != {"manifest.json", *manifest["files"]} or "database.dump" not in names:
            raise ValueError("Incomplete backup")
        for name, metadata in manifest["files"].items():
            parts = PurePosixPath(name).parts
            if (name != "database.dump" and not name.startswith("attachments/")) or (
                not parts or any(p in {"..", ".", ""} or ":" in p or "\\" in p or is_windows_reserved(p)
                                 or p.endswith((".", " ")) for p in parts)
                or name.startswith("/") or str(PurePosixPath(name)) != name
            ):
                raise ValueError("Unsafe backup entry")
            info = archive.getinfo(name)
            if info.file_size != metadata["size"] or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Invalid backup entry")
            target = stage.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            if digest(target) != metadata["sha256"]:
                raise ValueError("Backup checksum mismatch")
    return manifest


def restore(backup: Path, target: Path, install: Path = INSTALL):
    if target.exists() and any(target.iterdir()):
        raise ValueError("Restore requires an empty/new data directory; existing data is never replaced")
    stage = target.with_name(target.name + ".restore-" + uuid.uuid4().hex)
    private_directory(stage)
    # Failure retains the staging directory for diagnosis; target stays untouched.
    manifest = unpack_backup(backup, stage)
    runtime = Runtime(stage, install, restoring=True)
    with runtime.database():
        candidate = "edr_" + uuid.uuid4().hex
        runtime.run("createdb", candidate)
        runtime.run("pg_restore", "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl",
                    "-d", candidate, stage / "database.dump")
        versions = runtime.query(candidate, "SELECT version_num FROM alembic_version")
        if versions != [(manifest["revision"],)]:
            raise ValueError("Backup schema revision does not match its database")
        runtime.validate_pair(candidate)
        runtime.config.update(active=candidate, revision=manifest["revision"])
        atomic_json(stage / "runtime.json", runtime.config)
    (stage / "database.dump").unlink()
    if target.exists():
        target.rmdir()  # only the already-verified empty directory; never recurse
    stage.rename(target)


def stop(data: Path):
    try:
        with exclusive(data):
            return  # stale running.json does not prove a running supervisor
    except Busy:
        running = data / "running.json"
        if not running.exists():
            raise Busy("Startup/maintenance in progress; wait and retry") from None
        atomic_json(data / "stop.json", {"nonce": read_json(running)["nonce"]})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with exclusive(data):
                return
        except Busy:
            time.sleep(.2)
    raise Busy("EDR has not stopped; update/uninstall must not proceed")


def main(argv=None):
    parser = argparse.ArgumentParser(description="EDR Windows local runtime")
    parser.add_argument("command", choices=["start", "stop", "backup", "restore"])
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--data-dir", type=Path,
                        default=Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "EDR" / "data")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    data = checked_data(args.data_dir)
    try:
        if args.command == "stop":
            stop(data)
        else:
            try:
                with exclusive(data):
                    runtime = Runtime(data)
                    if args.command == "start":
                        runtime.start(not args.no_browser)
                    elif args.command == "backup":
                        if args.file is None:
                            raise ValueError("Specify a new backup ZIP path")
                        runtime.backup(args.file.resolve())
                    else:
                        if args.file is None:
                            raise ValueError("Specify a backup ZIP path")
                        restore(args.file.resolve(), data)
            except Busy:
                if args.command != "start":
                    raise
                # Only open the existing instance after its supervisor announces readiness.
                if not (data / "running.json").exists():
                    raise Busy("EDR is starting or maintenance is in progress") from None
                if not args.no_browser:
                    webbrowser.open(f"http://127.0.0.1:{API_PORT}/")
        return 0
    except Exception as error:
        message = f"EDR: {type(error).__name__}: {error}"
        if sys.stderr is not None:
            print(message, file=sys.stderr)
        if os.name == "nt" and sys.stderr is None:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "EDR", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
