import os

import folder_paths

from .manifest import log_save_event
from .naming import (
    build_metadata_payload,
    image_stem,
    normalize_model_prefix,
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
from .writers import save_mp4, save_png, tensor_to_pil

CATEGORY_SAVE = 'Brick/Save'
CATEGORY_TOOLS = 'Brick/Tools'

MOVEMENT_STYLES = [
    'Linear',
    'Orbit',
    'Combined',
    'Static',
]

SPEED_MODIFIERS = [
    'Extremely slow and cinematic',
    'Slow and smooth',
    'Moderate tracking speed',
    'Dynamic',
]

SUBJECT_PRESETS = [
    'Custom',
    'building facade',
    'kitchen island',
    'living room space',
    'entry lobby',
    'staircase',
    'courtyard',
    'material texture',
    'window detail',
    'landscape approach',
]

MOVEMENT_ACTIONS = {
    'Linear': [
        'Push In',
        'Push Out',
        'Track Left-to-Right',
        'Track Right-to-Left',
        'Pan Left',
        'Pan Right',
        'Tilt Up',
        'Tilt Down',
        'Boom Up',
        'Boom Down',
    ],
    'Orbit': [
        '90-Degree Arc',
        '180-Degree Semi-Circle',
        '360-Degree Full Orbit',
        'Spiral In',
        'Spiral Out',
        'Continuous Orbit (Loop)',
    ],
    'Combined': [
        'Spiral Reveal',
        'Crane Orbit Reveal',
        'Parallax Push-In',
        'Diagonal Track and Pan',
        'Dolly Zoom',
    ],
    'Static': [
        'One-Point Perspective',
        'Macro Close-up',
        'Locked-Off Wide Shot',
        'Detail Framing',
    ],
}

ACTION_TYPES = [
    action
    for actions in MOVEMENT_ACTIONS.values()
    for action in actions
]

CAMERA_ACTION_TEMPLATES = {
    'Push In': (
        '{speed_modifier} forward dolly shot pushing directly toward the '
        '{target_subject}'
    ),
    'Push Out': (
        '{speed_modifier} camera pull-back establishing the scale of the '
        '{target_subject}'
    ),
    'Track Left-to-Right': (
        '{speed_modifier} lateral tracking shot moving from left to right '
        'parallel to the {target_subject}'
    ),
    'Track Right-to-Left': (
        '{speed_modifier} lateral tracking shot moving from right to left '
        'parallel to the {target_subject}'
    ),
    'Pan Left': (
        '{speed_modifier} controlled pan left scanning across the '
        '{target_subject}'
    ),
    'Pan Right': (
        '{speed_modifier} controlled pan right scanning across the '
        '{target_subject}'
    ),
    'Tilt Up': (
        '{speed_modifier} vertical tilt-up starting from the base of the '
        '{target_subject}'
    ),
    'Tilt Down': (
        '{speed_modifier} vertical tilt-down revealing the upper volume of '
        '{target_subject}'
    ),
    'Boom Up': (
        '{speed_modifier} vertical boom shot rising smoothly along the '
        'Z-axis of the {target_subject}'
    ),
    'Boom Down': (
        '{speed_modifier} vertical crane shot descending to establish a '
        'human eye-level view of the {target_subject}'
    ),
    '90-Degree Arc': (
        '{speed_modifier} 90-degree smooth arc move around the '
        '{target_subject}'
    ),
    '180-Degree Semi-Circle': (
        '{speed_modifier} 180-degree semi-circle orbit around the '
        '{target_subject}'
    ),
    '360-Degree Full Orbit': (
        '{speed_modifier} complete 360-degree full orbit around the '
        '{target_subject}'
    ),
    'Spiral In': (
        '{speed_modifier} inward spiral orbit gradually closing distance to '
        'the {target_subject}'
    ),
    'Spiral Out': (
        '{speed_modifier} outward spiral orbit gradually revealing the '
        'surrounding space around the {target_subject}'
    ),
    'Continuous Orbit (Loop)': (
        '{speed_modifier} continuous looping orbit around the '
        '{target_subject}'
    ),
    'Spiral Reveal': (
        '{speed_modifier} rising crane shot while simultaneously orbiting '
        'the {target_subject}'
    ),
    'Crane Orbit Reveal': (
        '{speed_modifier} crane-up reveal combined with a smooth orbit around '
        'the {target_subject}'
    ),
    'Parallax Push-In': (
        '{speed_modifier} forward push-in with subtle lateral parallax across '
        'the {target_subject}'
    ),
    'Diagonal Track and Pan': (
        '{speed_modifier} diagonal tracking move with a coordinated pan across '
        'the {target_subject}'
    ),
    'Dolly Zoom': (
        '{speed_modifier} architectural dolly zoom maintaining focus on the '
        '{target_subject}'
    ),
    'One-Point Perspective': (
        'Static tripod shot with precise one-point perspective centered on '
        'the {target_subject}, zero camera movement'
    ),
    'Macro Close-up': (
        'Fixed macro close-up shot focusing deeply on the texture and '
        'intricate details of the {target_subject}'
    ),
    'Locked-Off Wide Shot': (
        'Static locked-off wide architectural shot framing the '
        '{target_subject}, zero camera movement'
    ),
    'Detail Framing': (
        'Static detailed composition isolating the architectural form and '
        'surface qualities of the {target_subject}, zero camera movement'
    ),
}

MOVEMENT_STYLE_PROMPTS = {
    'Linear': 'linear camera movement style',
    'Orbit': 'orbital camera movement style',
    'Combined': 'cinematic combined camera movement style',
    'Static': 'locked-off architectural framing style',
}

MOVEMENT_STYLE_ALIASES = {
    'Linear (Dolly/Track)': 'Linear',
    'Rotational (Pan/Tilt/Orbit)': 'Orbit',
    'Combined (Cinematic)': 'Combined',
    'Static (Framing)': 'Static',
}

ACTION_TYPE_ALIASES = {
    'Push-In': 'Push In',
    'Pull-Back': 'Push Out',
    'Pedestal Up': 'Boom Up',
    'Pedestal Down': 'Boom Down',
    'Horizontal Pan': 'Pan Right',
    'Vertical Tilt': 'Tilt Up',
    '180-Degree Orbit': '180-Degree Semi-Circle',
}

STABILITY_REINFORCEMENT_PROMPT = (
    ', maintaining absolute camera stability, perfectly smooth motion curves, '
    'and zero organic handheld shaking.'
)


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
    CATEGORY = CATEGORY_SAVE
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
                'model_prefix': ('STRING', {'default': ''}),
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
        model_prefix='',
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
        prefix_token = normalize_model_prefix(model_prefix)
        version_item = f'{prefix_token}|{camera_token}' if prefix_token else camera_token
        key = build_version_key('image', paths.project_name, version_item)
        version = reserve_next_version(paths.metadata_root, key)
        stem = image_stem(date_str, paths.project_name, camera_token, version, model_prefix=model_prefix)

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
                model_prefix=model_prefix,
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
                'model_prefix': model_prefix,
                'model_prefix_token': metadata_payload['model_prefix_token'],
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
    CATEGORY = CATEGORY_SAVE
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
                'model_prefix': ('STRING', {'default': ''}),
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
        model_prefix='',
        shot_number=0,
        unique_id=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        project_name = validate_project_name(project_name)
        paths = ensure_project(project_name)
        date_str = today_compact()
        shot_token = normalize_shot_number(shot_number)

        prefix_token = normalize_model_prefix(model_prefix)
        version_item = f'{prefix_token}|{shot_token}' if prefix_token else shot_token
        key = build_version_key('sequence', paths.project_name, version_item)
        version = reserve_next_version(paths.metadata_root, key)

        sequence_name = sequence_stem(date_str, paths.project_name, shot_number, version, model_prefix=model_prefix)
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
                model_prefix=model_prefix,
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

        sequence_metadata_payload = build_metadata_payload(
            asset_type='sequence',
            project_name=paths.project_name,
            version=version,
            target_path=sequence_root,
            shot_number=shot_number,
            model_prefix=model_prefix,
        )

        log_save_event(paths.metadata_root, {
            'asset_type': 'sequence',
            'project_name': paths.project_name,
            'project_code': sequence_metadata_payload['project_code'],
            'shot_token': shot_token,
            'model_prefix': model_prefix,
            'model_prefix_token': sequence_metadata_payload['model_prefix_token'],
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


class SaveArchVizVideo:
    CATEGORY = CATEGORY_SAVE
    FUNCTION = 'save'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING', 'INT')
    RETURN_NAMES = ('project_root', 'saved_video_path', 'version')

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'images': ('IMAGE',),
                'project_name': (_project_choices(), {'default': DEFAULT_PROJECT_NAME}),
                'model_prefix': ('STRING', {'default': ''}),
                'shot_number': ('INT', {'default': 0, 'min': 0, 'max': 9999, 'step': 1}),
                'fps': ('FLOAT', {'default': 24.0, 'min': 1.0, 'max': 120.0, 'step': 1.0}),
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
        model_prefix='',
        shot_number=0,
        fps=24.0,
        unique_id=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        project_name = validate_project_name(project_name)
        paths = ensure_project(project_name)
        date_str = today_compact()
        shot_token = normalize_shot_number(shot_number)

        prefix_token = normalize_model_prefix(model_prefix)
        version_item = f'{prefix_token}|{shot_token}' if prefix_token else shot_token
        key = build_version_key('video', paths.project_name, version_item)
        version = reserve_next_version(paths.metadata_root, key)

        video_name = f'{sequence_stem(date_str, paths.project_name, shot_number, version, model_prefix=model_prefix)}.mp4'
        video_root = os.path.join(paths.videos_root, shot_token)
        os.makedirs(video_root, exist_ok=True)
        video_path = os.path.join(video_root, video_name)

        identity = get_runtime_identity()
        metadata_payload = build_metadata_payload(
            asset_type='video',
            project_name=paths.project_name,
            version=version,
            target_path=video_path,
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
            node_id=unique_id,
            identity=identity,
            shot_number=shot_number,
            model_prefix=model_prefix,
            project_root=paths.project_root,
        )

        save_mp4(video_path, images, fps=fps)

        log_save_event(paths.metadata_root, {
            'asset_type': 'video',
            'project_name': paths.project_name,
            'project_code': metadata_payload['project_code'],
            'shot_token': shot_token,
            'model_prefix': model_prefix,
            'model_prefix_token': metadata_payload['model_prefix_token'],
            'version': version,
            'file_path': video_path,
            'frame_count': len(images),
            'fps': float(fps),
            'node_id': unique_id,
        })

        return {
            'ui': {'text': [video_path]},
            'result': (paths.project_root, video_path, version),
        }


class BrickImageShortSide:
    CATEGORY = CATEGORY_TOOLS
    FUNCTION = 'measure'
    OUTPUT_NODE = True
    RETURN_TYPES = ('INT',)
    RETURN_NAMES = ('short_size',)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'image': ('IMAGE',),
            },
        }

    def measure(self, image):
        if image is None or len(image.shape) < 3:
            short_size = 0
        else:
            height = int(image.shape[-3])
            width = int(image.shape[-2])
            short_size = min(width, height)

        return {
            'ui': {'text': [str(short_size)]},
            'result': (short_size,),
        }


class ArchVizCameraPromptBuilder:
    CATEGORY = CATEGORY_TOOLS
    FUNCTION = 'generate_prompt'
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('CAMERA_PROMPT',)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'movement_style': (
                    MOVEMENT_STYLES,
                    {'default': 'Linear'},
                ),
                'action_type': (ACTION_TYPES, {'default': 'Push In'}),
                'speed_modifier': (
                    SPEED_MODIFIERS,
                    {'default': 'Slow and smooth'},
                ),
                'lock_target_subject': (
                    'BOOLEAN',
                    {'default': True},
                ),
                'stability_reinforcement': (
                    'BOOLEAN',
                    {'default': True},
                ),
            },
            'optional': {
                'target_subject_preset': (
                    SUBJECT_PRESETS,
                    {'default': 'Custom'},
                ),
                'target_subject': ('STRING', {'default': '[Subject]'}),
            },
        }

    def generate_prompt(
        self,
        movement_style,
        action_type,
        speed_modifier='Slow and smooth',
        lock_target_subject=True,
        target_subject_preset='Custom',
        target_subject='[Subject]',
        stability_reinforcement=True,
    ):
        clean_movement = MOVEMENT_STYLE_ALIASES.get(movement_style, movement_style)
        if clean_movement not in MOVEMENT_ACTIONS:
            clean_movement = 'Linear'

        requested_action = ACTION_TYPE_ALIASES.get(action_type, action_type)
        allowed_actions = MOVEMENT_ACTIONS[clean_movement]
        clean_action = (
            requested_action
            if requested_action in allowed_actions
            else allowed_actions[0]
        )

        if lock_target_subject:
            if target_subject_preset == 'Custom':
                clean_subject = target_subject.strip() or '[Subject]'
            else:
                clean_subject = target_subject_preset
        else:
            clean_subject = 'the architectural space'

        movement_prompt = MOVEMENT_STYLE_PROMPTS[clean_movement]
        template = CAMERA_ACTION_TEMPLATES[clean_action]
        camera_prompt = template.format(
            speed_modifier=speed_modifier,
            target_subject=clean_subject,
        )
        camera_prompt = f'{camera_prompt}, using a {movement_prompt}'

        if not lock_target_subject:
            camera_prompt += ', moving freely without locking onto a single subject'

        # Keep AI video models locked to intentional architectural camera moves.
        if stability_reinforcement:
            camera_prompt += STABILITY_REINFORCEMENT_PROMPT

        return (camera_prompt,)


NODE_CLASS_MAPPINGS = {
    'SaveArchVizImage': SaveArchVizImage,
    'SaveArchVizSequence': SaveArchVizSequence,
    'SaveArchVizVideo': SaveArchVizVideo,
    'BrickImageShortSide': BrickImageShortSide,
    'ArchVizCameraPromptBuilder': ArchVizCameraPromptBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'SaveArchVizImage': 'Save Brick Image',
    'SaveArchVizSequence': 'Save Brick Sequence',
    'SaveArchVizVideo': 'Save Brick Video',
    'BrickImageShortSide': 'Brick Image Short Size',
    'ArchVizCameraPromptBuilder': 'ArchViz Camera Prompt Builder',
}
