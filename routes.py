import os

from aiohttp import web
from server import PromptServer

from .project_registry import DEFAULT_PROJECT_NAME, ensure_project, list_projects
from .state import get_latest_sequence
from .utils import build_sequence_zip

routes = PromptServer.instance.routes


@routes.get('/archviz_saver/projects')
async def archviz_saver_get_projects(request):
    return web.json_response({'projects': list_projects(), 'default_project': DEFAULT_PROJECT_NAME})


@routes.post('/archviz_saver/projects')
async def archviz_saver_create_project(request):
    data = await request.post()
    project_name = (data.get('project_name') or '').strip()
    if not project_name:
        return web.json_response({'error': 'Project name is required.'}, status=400)

    paths = ensure_project(project_name)
    return web.json_response({
        'project_name': paths.project_name,
        'projects': list_projects(),
        'default_project': DEFAULT_PROJECT_NAME,
    })


@routes.get('/archviz_saver/sequence/download')
async def archviz_saver_download_sequence(request):
    node_id = (request.query.get('node_id') or '').strip()
    if not node_id:
        return web.json_response({'error': 'node_id is required.'}, status=400)

    sequence_root = get_latest_sequence(node_id)
    if not sequence_root:
        return web.json_response({'error': 'No saved sequence found for this node yet. Run the node first.'}, status=404)
    if not os.path.isdir(sequence_root):
        return web.json_response({'error': 'The saved sequence folder no longer exists.'}, status=404)

    zip_path, zip_name = build_sequence_zip(sequence_root, os.path.basename(sequence_root))
    return web.FileResponse(
        zip_path,
        headers={'Content-Disposition': f'attachment; filename="{zip_name}"'},
    )
