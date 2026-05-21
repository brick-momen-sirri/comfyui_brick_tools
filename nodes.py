import os

import folder_paths

from .manifest import log_save_event
from .naming import (
    build_metadata_payload,
    image_stem,
    normalize_shot_number,
    resolve_camera_token,
    sequence_frame_name,
    sequence_stem,
    today_compact,
)
from .project_registry import DEFAULT_PROJECT_NAME, ensure_project, list_projects
from .state import record_latest_sequence
from .utils import get_runtime_identity
from .versioning import build_version_key, reserve_next_version
from .writers import save_png, tensor_to_pil

CATEGORY_BASE = 'Brick/Save'


def _project_choices():
    return list_projects()


def validate_project_name(project_name: str) -> str:
    clean_name = (project_name or '').strip()
    if not clean_name:
        raise ValueError(
            'Brick Saver: Project name is required. Choose or create the correct project before running.'
        )
    if clean_name == DEFAULT_PROJECT_NAME:
        raise ValueError(
            f'Brick Saver: "{DEFAULT_PROJECT_NAME}" is only a placeholder project. '
            'Choose or create the correct project before running.'
        )
    return clean_name


class SaveArchVizImage:
    CATEGORY = CATEGORY_BASE
    FUNCTION = 'save'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING', 'INT')
    RETURN_NAMES = ('project_root', 'saved_primary_path', 'version')

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'images': ('IMAGE',),
                'project_name': (_project_choices(), {'default': DEFAULT_PROJECT_NAME}),
                'camera_mode': (['camera_number', 'camera_name'], {'default': 'camera_number'}),
                'camera_number': ('INT', {'default': 1, 'min': 0, 'max': 9999, 'step': 1}),
                'camera_name': ('STRING', {'default': ''}),
            },
            'hidden': {
                'unique_id': 'UNIQUE_ID',
                'prompt': 'PROMPT',
                'extra_pnginfo': 'EXTRA_PNGINFO',
            },
        }

    def save(
        self,
        images,
        project_name=DEFAULT_PROJECT_NAME,
        camera_mode='camera_number',
        camera_number=1,
        camera_name='',
        unique_id=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        project_name = validate_project_name(project_name)
        paths = ensure_project(project_name)
        date_str = today_compact()
        image_day_root = os.path.join(paths.images_root, date_str)
        os.makedirs(image_day_root, exist_ok=True)

        camera_token = resolve_camera_token(camera_mode, camera_number, camera_name)
        key = build_version_key('image', paths.project_name, camera_token)
        version = reserve_next_version(paths.metadata_root, key)
        stem = image_stem(date_str, paths.project_name, camera_token, version)

        saved_files = []
        ui_images = []
        identity = get_runtime_identity()

        for idx, image_tensor in enumerate(images):
            pil_image = tensor_to_pil(image_tensor)
            file_name = f'{stem}.png' if len(images) == 1 else f'{stem}_{idx + 1:02d}.png'
            file_path = os.path.join(image_day_root, file_name)

            metadata_payload = build_metadata_payload(
                asset_type='image',
                project_name=paths.project_name,
                version=version,
                target_path=file_path,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
                node_id=unique_id,
                identity=identity,
                camera_mode=camera_mode,
                camera_number=camera_number,
                camera_name=camera_name,
                project_root=paths.project_root,
            )

            save_png(
                file_path,
                pil_image,
                metadata={
                    'archviz_saver': metadata_payload,
                    'prompt': prompt,
                    'extra_pnginfo': extra_pnginfo,
                },
            )

            saved_files.append(file_path)
            ui_images.append({
                'filename': os.path.basename(file_path),
                'subfolder': os.path.relpath(os.path.dirname(file_path), folder_paths.get_output_directory()).replace('\\', '/'),
                'type': 'output',
            })

            log_save_event(paths.metadata_root, {
                'asset_type': 'image',
                'project_name': paths.project_name,
                'project_code': metadata_payload['project_code'],
                'camera_mode': camera_mode,
                'camera_token': camera_token,
                'version': version,
                'file_path': file_path,
                'node_id': unique_id,
            })

        primary = saved_files[0] if saved_files else ''
        return {
            'ui': {'images': ui_images, 'text': [primary]},
            'result': (paths.project_root, primary, version),
        }


class SaveArchVizSequence:
    CATEGORY = CATEGORY_BASE
    FUNCTION = 'save'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING', 'INT')
    RETURN_NAMES = ('project_root', 'sequence_version_folder', 'version')

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'images': ('IMAGE',),
                'project_name': (_project_choices(), {'default': DEFAULT_PROJECT_NAME}),
                'shot_number': ('INT', {'default': 0, 'min': 0, 'max': 9999, 'step': 1}),
            },
            'hidden': {
                'unique_id': 'UNIQUE_ID',
                'prompt': 'PROMPT',
                'extra_pnginfo': 'EXTRA_PNGINFO',
            },
        }

    def save(
        self,
        images,
        project_name=DEFAULT_PROJECT_NAME,
        shot_number=0,
        unique_id=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        project_name = validate_project_name(project_name)
        paths = ensure_project(project_name)
        date_str = today_compact()
        shot_token = normalize_shot_number(shot_number)

        key = build_version_key('sequence', paths.project_name, shot_token)
        version = reserve_next_version(paths.metadata_root, key)

        sequence_name = sequence_stem(date_str, paths.project_name, shot_number, version)
        sequence_root = os.path.join(paths.sequences_root, shot_token, sequence_name)
        os.makedirs(sequence_root, exist_ok=True)

        identity = get_runtime_identity()
        saved_files = []
        ui_images = []

        for idx, image_tensor in enumerate(images):
            pil_image = tensor_to_pil(image_tensor)
            frame_name = sequence_frame_name(idx + 1, '.png')
            file_path = os.path.join(sequence_root, frame_name)

            metadata_payload = build_metadata_payload(
                asset_type='sequence_frame',
                project_name=paths.project_name,
                version=version,
                target_path=file_path,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
                node_id=unique_id,
                identity=identity,
                shot_number=shot_number,
                project_root=paths.project_root,
            )

            save_png(
                file_path,
                pil_image,
                metadata={
                    'archviz_saver': metadata_payload,
                    'prompt': prompt,
                    'extra_pnginfo': extra_pnginfo,
                },
            )

            saved_files.append(file_path)
            ui_images.append({
                'filename': os.path.basename(file_path),
                'subfolder': os.path.relpath(os.path.dirname(file_path), folder_paths.get_output_directory()).replace('\\', '/'),
                'type': 'output',
            })

        log_save_event(paths.metadata_root, {
            'asset_type': 'sequence',
            'project_name': paths.project_name,
            'project_code': build_metadata_payload(
                asset_type='sequence',
                project_name=paths.project_name,
                version=version,
                target_path=sequence_root,
                shot_number=shot_number,
            )['project_code'],
            'shot_token': shot_token,
            'version': version,
            'file_path': sequence_root,
            'frame_count': len(saved_files),
            'node_id': unique_id,
        })

        record_latest_sequence(unique_id, sequence_root)

        return {
            'ui': {'images': ui_images[: min(8, len(ui_images))], 'text': [sequence_root]},
            'result': (paths.project_root, sequence_root, version),
        }


NODE_CLASS_MAPPINGS = {
    'SaveArchVizImage': SaveArchVizImage,
    'SaveArchVizSequence': SaveArchVizSequence,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'SaveArchVizImage': 'Save Brick Image',
    'SaveArchVizSequence': 'Save Brick Sequence',
}
