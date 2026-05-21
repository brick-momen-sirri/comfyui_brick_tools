import os
from dataclasses import dataclass
from typing import List

import folder_paths

from .utils import safe_makedirs, sanitize_for_filename

DEFAULT_PROJECT_NAME = '0000_base'


@dataclass
class ProjectPaths:
    output_root: str
    projects_root: str
    project_name: str
    project_root: str
    images_root: str
    sequences_root: str
    videos_root: str
    metadata_root: str
    logs_root: str


def get_output_root() -> str:
    return folder_paths.get_output_directory()


def get_projects_root() -> str:
    return safe_makedirs(os.path.join(get_output_root(), 'projects'))


def list_projects(include_default: bool = True) -> List[str]:
    root = get_projects_root()
    projects = []
    if os.path.exists(root):
        for entry in os.listdir(root):
            full = os.path.join(root, entry)
            if os.path.isdir(full):
                projects.append(entry)
    if include_default and DEFAULT_PROJECT_NAME not in projects:
        projects.append(DEFAULT_PROJECT_NAME)
    return sorted(projects, key=lambda x: (x != DEFAULT_PROJECT_NAME, x.lower()))


def ensure_project(project_name: str) -> ProjectPaths:
    clean_name = sanitize_for_filename(project_name, fallback=DEFAULT_PROJECT_NAME)
    output_root = get_output_root()
    projects_root = get_projects_root()
    project_root = safe_makedirs(os.path.join(projects_root, clean_name))

    paths = ProjectPaths(
        output_root=output_root,
        projects_root=projects_root,
        project_name=clean_name,
        project_root=project_root,
        images_root=os.path.join(project_root, 'images'),
        sequences_root=os.path.join(project_root, 'sequences'),
        videos_root=os.path.join(project_root, 'videos'),
        metadata_root=os.path.join(project_root, 'metadata'),
        logs_root=os.path.join(project_root, 'logs'),
    )

    for path in (paths.images_root, paths.sequences_root, paths.videos_root, paths.metadata_root, paths.logs_root):
        safe_makedirs(path)

    return paths
