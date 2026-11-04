#!/usr/bin/env bash
set -u
cd /mnt/d/Antigravity/EquipmentDocumentationRegistry || exit 99
EV=docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/implementer

{
  .venv/bin/python -m py_compile app/windows_local.py tests/test_windows_local.py
  echo "EXIT=$?"
} > "$EV/py_compile.txt" 2>&1

{
  .venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config" -p no:cacheprovider
  echo "EXIT=$?"
} > "$EV/pytest-alembic_config.txt" 2>&1

{
  .venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config_cp1252_regression or alembic_config_reads_utf8 or alembic_config_head" -p no:cacheprovider
  echo "EXIT=$?"
} > "$EV/pytest-alembic_config-intersection.txt" 2>&1

for f in py_compile.txt pytest-alembic_config.txt pytest-alembic_config-intersection.txt; do
  echo "===== $f ====="
  cat "$EV/$f"
done
