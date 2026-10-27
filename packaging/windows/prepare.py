"""Extract only redistributable runtime trees; no pgAdmin/StackBuilder payload."""
from pathlib import Path, PurePosixPath
import sys
import zipfile

python_zip, pg_zip, destination = map(Path, sys.argv[1:])
for archive_path, prefix, output in (
    (python_zip, None, destination / "python"),
    (pg_zip, "pgsql", destination / "postgresql"),
):
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            parts = PurePosixPath(entry.filename).parts
            if not parts or any(p in {"..", "."} or ":" in p or "\\" in p for p in parts) or entry.filename.startswith("/"):
                raise ValueError("Unsafe runtime archive path")
            if prefix:
                if parts[0] != prefix:
                    continue
                parts = parts[1:]
                if not parts or parts[0] not in {"bin", "lib", "share", "doc", "server_license.txt", "commandlinetools_3rd_party_licenses.txt"}:
                    continue
            if entry.is_dir():
                continue
            target = output.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("xb") as result:
                import shutil
                shutil.copyfileobj(source, result)
