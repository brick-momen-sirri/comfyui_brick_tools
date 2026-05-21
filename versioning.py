import os

from .utils import atomic_write_json, file_lock, read_json


def get_latest_versions_path(metadata_root: str) -> str:
    return os.path.join(metadata_root, 'latest_versions.json')


def build_version_key(asset_type: str, project_name: str, item_name: str) -> str:
    return f'{asset_type}|{project_name}|{item_name}'


def reserve_next_version(metadata_root: str, key: str) -> int:
    versions_path = get_latest_versions_path(metadata_root)
    lock_path = versions_path + '.lock'

    with file_lock(lock_path):
        data = read_json(versions_path, default={})
        current = int(data.get(key, 0))
        next_version = current + 1
        data[key] = next_version
        atomic_write_json(versions_path, data)

    return next_version
