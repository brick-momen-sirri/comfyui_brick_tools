import os
from urllib.parse import quote

from aiohttp import web
from server import PromptServer

from .browser_backend import (
    _abs_from_projects,
    DEFAULT_PROJECT_NAME,
    create_project,
    delete_asset,
    ensure_export_image,
    ensure_sequence_preview,
    ensure_sequence_zip,
    ensure_thumbnail,
    extract_workflow_from_png,
    get_paths,
    list_projects,
    paged_assets,
    rename_asset,
)

routes = PromptServer.instance.routes


def _attachment_headers(filename: str, content_type: str) -> dict:
    safe_name = (filename or "download").replace('"', "")
    return {
        "Content-Type": content_type,
        "Content-Disposition": f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{quote(safe_name)}",
    }


@routes.get("/archviz_browser/projects")
async def archviz_browser_projects(request):
    projects = list_projects()
    default_project = DEFAULT_PROJECT_NAME if DEFAULT_PROJECT_NAME in projects else (projects[0] if projects else DEFAULT_PROJECT_NAME)
    return web.json_response({"projects": projects, "default_project": default_project})


@routes.post("/archviz_browser/projects")
async def archviz_browser_create_project(request):
    payload = {}
    try:
        if request.can_read_body:
            payload = await request.json()
    except Exception:
        try:
            payload = await request.post()
        except Exception:
            payload = {}

    project_name = (payload.get("project_name") or "").strip()
    if not project_name:
        return web.json_response({"error": "Project name is required."}, status=400)

    try:
        result = create_project(project_name)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(result)


@routes.get("/archviz_browser/assets")
async def archviz_browser_assets(request):
    project = (request.query.get("project") or DEFAULT_PROJECT_NAME).strip()
    category = (request.query.get("category") or "images").strip().lower()
    query = (request.query.get("query") or "").strip()
    sort = (request.query.get("sort") or "newest").strip().lower()
    workflow_only = (request.query.get("workflow_only") or "").strip().lower() in {"1", "true", "yes", "on"}
    page = int(request.query.get("page") or 1)
    page_size = int(request.query.get("page_size") or 48)
    payload = paged_assets(
        project,
        category,
        page=page,
        page_size=page_size,
        query=query,
        sort=sort,
        workflow_only=workflow_only,
    )
    return web.json_response(payload)


@routes.get("/archviz_browser/file")
async def archviz_browser_file(request):
    rel_path = (request.query.get("path") or "").strip()
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    try:
        abs_path = _abs_from_projects(rel_path)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    if not os.path.isfile(abs_path):
        return web.json_response({"error": "file not found"}, status=404)
    return web.FileResponse(abs_path)


@routes.get("/archviz_browser/thumb")
async def archviz_browser_thumb(request):
    rel_path = (request.query.get("path") or "").strip()
    kind = (request.query.get("kind") or "image").strip().lower()
    size = int(request.query.get("size") or 320)
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    try:
        cache_path, mime = ensure_thumbnail(rel_path, kind, size=size)
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.FileResponse(cache_path, headers={"Content-Type": mime, "Cache-Control": "public, max-age=3600"})


@routes.get("/archviz_browser/sequence_preview")
async def archviz_browser_sequence_preview(request):
    rel_path = (request.query.get("path") or "").strip()
    size = int(request.query.get("size") or 420)
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    try:
        preview_path, mime = ensure_sequence_preview(rel_path, size=size)
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.FileResponse(preview_path, headers={"Content-Type": mime, "Cache-Control": "public, max-age=3600"})


@routes.get("/archviz_browser/export_image")
async def archviz_browser_export_image(request):
    rel_path = (request.query.get("path") or "").strip()
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    try:
        export_path, mime = ensure_export_image(rel_path)
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.FileResponse(export_path, headers={"Content-Type": mime, "Cache-Control": "public, max-age=3600"})


@routes.get("/archviz_browser/download")
async def archviz_browser_download(request):
    rel_path = (request.query.get("path") or "").strip()
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)

    try:
        abs_path = _abs_from_projects(rel_path)
        base_name = os.path.basename(abs_path)
        stem, _ = os.path.splitext(base_name)
        if os.path.isdir(abs_path):
            download_path, mime = ensure_sequence_zip(rel_path)
            filename = f"{base_name}.zip"
        else:
            download_path, mime = ensure_export_image(rel_path)
            filename = f"{stem or base_name}.png"
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)

    return web.FileResponse(download_path, headers=_attachment_headers(filename, mime))


@routes.get("/archviz_browser/workflow")
async def archviz_browser_workflow(request):
    rel_path = (request.query.get("path") or "").strip()
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    try:
        payload = extract_workflow_from_png(rel_path)
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    if not payload.get("has_workflow"):
        return web.json_response({"error": "No workflow metadata found in this PNG."}, status=404)
    return web.json_response(payload)


@routes.post("/archviz_browser/delete")
async def archviz_browser_delete(request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    rel_path = (payload.get("path") or "").strip()
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    try:
        result = delete_asset(rel_path)
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(result)


@routes.post("/archviz_browser/rename")
async def archviz_browser_rename(request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    rel_path = (payload.get("path") or "").strip()
    new_name = (payload.get("new_name") or "").strip()
    if not rel_path:
        return web.json_response({"error": "path is required"}, status=400)
    if not new_name:
        return web.json_response({"error": "new_name is required"}, status=400)
    try:
        result = rename_asset(rel_path, new_name)
    except FileNotFoundError as exc:
        return web.json_response({"error": str(exc)}, status=404)
    except FileExistsError as exc:
        return web.json_response({"error": str(exc)}, status=409)
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)
    return web.json_response(result)


@routes.get("/archviz_browser/health")
async def archviz_browser_health(request):
    paths = get_paths()
    return web.json_response({
        "projects_root": paths.projects_root,
        "browser_cache_root": paths.browser_cache_root,
        "project_count": len(list_projects(include_default=False)),
    })
