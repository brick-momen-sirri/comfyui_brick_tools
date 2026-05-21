import datetime as _dt
import re
from typing import Dict, Optional

from .utils import sanitize_for_filename


def today_compact() -> str:
    return _dt.date.today().strftime('%Y%m%d')


def normalize_version(version: int) -> str:
    return f'v{int(version):03d}'


def normalize_camera_number(camera_number: int) -> str:
    return f'cam-{int(camera_number):02d}'


def normalize_camera_name(camera_name: str) -> str:
    clean = sanitize_for_filename(camera_name, fallback='name')
    clean = clean.replace(' ', '-').replace('_', '-')
    clean = re.sub(r'-{2,}', '-', clean).strip('-').lower()
    clean = clean or 'name'
    if clean.startswith('cam-'):
        return clean
    return f'cam-{clean}'


def normalize_shot_number(shot_number: int) -> str:
    return f'SHOT_{int(shot_number):04d}'


def normalize_model_prefix(model_prefix: str) -> str:
    clean = sanitize_for_filename(model_prefix, fallback='', max_length=48)
    clean = clean.replace(' ', '-')
    clean = re.sub(r'_{2,}', '_', clean)
    clean = re.sub(r'-{2,}', '-', clean)
    clean = clean.strip(' .-_').lower()
    return clean


def apply_model_prefix(date_str: str, stem_after_date: str, model_prefix: str = '') -> str:
    prefix = normalize_model_prefix(model_prefix)
    return f'{date_str}_{prefix}_{stem_after_date}' if prefix else f'{date_str}_{stem_after_date}'


def project_code(project_name: str) -> str:
    raw = (project_name or '').strip()
    leading_digits = re.match(r'\D*(\d{4,})', raw)
    if leading_digits:
        return leading_digits.group(1)[:4]

    any_digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(any_digits) >= 4:
        return any_digits[:4]

    alnum = ''.join(ch for ch in sanitize_for_filename(raw, fallback='PROJ').upper() if ch.isalnum())
    return (alnum[:4] or 'PROJ').ljust(4, '0')


def image_stem(date_str: str, project_name: str, camera_token: str, version: int, model_prefix: str = '') -> str:
    stem_after_date = f'{project_code(project_name)}_{camera_token}_{normalize_version(version)}'
    return apply_model_prefix(date_str, stem_after_date, model_prefix)


def sequence_stem(date_str: str, project_name: str, shot_number: int, version: int, model_prefix: str = '') -> str:
    stem_after_date = f'{project_code(project_name)}_{normalize_shot_number(shot_number)}_{normalize_version(version)}'
    return apply_model_prefix(date_str, stem_after_date, model_prefix)


def sequence_frame_name(frame_index: int, extension: str = '.png') -> str:
    return f'{frame_index:04d}{extension}'


def resolve_camera_token(camera_mode: str, camera_number: int, camera_name: str) -> str:
    if str(camera_mode or '').lower() == 'camera_name':
        return normalize_camera_name(camera_name)
    return normalize_camera_number(camera_number)


def build_metadata_payload(
    *,
    asset_type: str,
    project_name: str,
    version: int,
    target_path: str,
    prompt=None,
    extra_pnginfo=None,
    node_id=None,
    identity=None,
    camera_mode: Optional[str] = None,
    camera_number=None,
    camera_name=None,
    shot_number=None,
    model_prefix=None,
    project_root=None,
) -> Dict:
    payload = {
        'asset_type': asset_type,
        'project_name': project_name,
        'project_code': project_code(project_name),
        'date': today_compact(),
        'version': normalize_version(version),
        'version_int': int(version),
        'target_path': target_path,
        'project_root': project_root,
        'node_id': node_id,
        'identity': identity or {},
        'prompt': prompt,
        'extra_pnginfo': extra_pnginfo,
    }
    if camera_mode is not None:
        payload['camera_mode'] = str(camera_mode)
    if camera_number is not None:
        payload['camera_number'] = int(camera_number)
        payload['camera_number_token'] = normalize_camera_number(camera_number)
    if camera_name is not None:
        payload['camera_name'] = str(camera_name)
        payload['camera_name_token'] = normalize_camera_name(camera_name)
    if shot_number is not None:
        payload['shot_number'] = int(shot_number)
        payload['shot_token'] = normalize_shot_number(shot_number)
    if model_prefix is not None:
        payload['model_prefix'] = str(model_prefix)
        payload['model_prefix_token'] = normalize_model_prefix(model_prefix)
    if camera_mode is not None and (camera_name is not None or camera_number is not None):
        payload['camera_token'] = resolve_camera_token(camera_mode, camera_number or 0, camera_name or '')
    return payload
