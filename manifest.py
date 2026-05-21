import datetime as dt
import os
from typing import Dict

from .utils import append_jsonl


def manifest_path(metadata_root: str) -> str:
    return os.path.join(metadata_root, 'manifest.jsonl')


def log_save_event(metadata_root: str, record: Dict) -> str:
    payload = {
        'timestamp_utc': dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        **record,
    }
    path = manifest_path(metadata_root)
    append_jsonl(path, payload)
    return path
