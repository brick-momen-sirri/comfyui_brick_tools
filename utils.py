import json
import os
import platform
import re
import shutil
import socket
import tempfile
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict

INVALID_FILENAME_CHARS = r'<>:"/\|?*'
RESERVED_WINDOWS_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}


def sanitize_for_filename(value: str, fallback: str = 'UNTITLED', max_length: int = 120) -> str:
    value = (value or '').strip()
    if not value:
        value = fallback

    value = re.sub(rf'[{re.escape(INVALID_FILENAME_CHARS)}]', '-', value)
    value = re.sub(r'\s+', ' ', value)
    value = re.sub(r'-{2,}', '-', value)
    value = value.strip(' .-_	')

    if not value:
        value = fallback

    if value.upper() in RESERVED_WINDOWS_NAMES:
        value = f'_{value}'

    return value[:max_length].strip() or fallback


def safe_makedirs(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path: str, payload: Any) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix='.tmp_archviz_', suffix='.json', dir=parent or None)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def append_jsonl(path: str, record: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


@contextmanager
def file_lock(lock_path: str, timeout_seconds: float = 10.0, poll_seconds: float = 0.1):
    start = time.time()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode('utf-8'))
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - start > timeout_seconds:
                raise TimeoutError(f'Timed out waiting for lock: {lock_path}')
            time.sleep(poll_seconds)

    try:
        yield
    finally:
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass


def get_runtime_identity() -> Dict[str, str]:
    return {
        'user': os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown',
        'machine': socket.gethostname() or platform.node() or 'unknown',
        'platform': platform.platform(),
    }


def build_sequence_zip(sequence_root: str, suggested_name: str | None = None, max_age_seconds: int = 86400) -> tuple[str, str]:
    if not os.path.isdir(sequence_root):
        raise FileNotFoundError(sequence_root)

    temp_root = safe_makedirs(os.path.join(tempfile.gettempdir(), 'archviz_saver_downloads'))
    now = time.time()
    for entry in os.listdir(temp_root):
        path = os.path.join(temp_root, entry)
        try:
            if os.path.isfile(path) and (now - os.path.getmtime(path)) > max_age_seconds:
                os.remove(path)
            elif os.path.isdir(path) and (now - os.path.getmtime(path)) > max_age_seconds:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass

    base_name = sanitize_for_filename(suggested_name or os.path.basename(sequence_root), fallback='sequence')
    zip_path = os.path.join(temp_root, f'{base_name}.zip')
    counter = 1
    while os.path.exists(zip_path):
        zip_path = os.path.join(temp_root, f'{base_name}_{counter:02d}.zip')
        counter += 1

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for current_root, _, files in os.walk(sequence_root):
            for filename in sorted(files):
                full_path = os.path.join(current_root, filename)
                arcname = os.path.relpath(full_path, sequence_root)
                zf.write(full_path, arcname)

    return zip_path, os.path.basename(zip_path)
