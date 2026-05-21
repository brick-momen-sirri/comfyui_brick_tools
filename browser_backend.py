import hashlib
import json
import math
import os
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import folder_paths
from PIL import Image, ImageOps, features

CACHE_TTL_SECONDS = 5.0
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
FRAME_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
DEFAULT_PROJECT_NAME = "0000_base"
INVALID_FILENAME_CHARS = r'<>:"/\|?*'
RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
IMAGE_NAME_RE = re.compile(r"^(?P<date>\d{8})_(?P<code>[A-Za-z0-9]{4})_(?P<camera>cam-[^_]+)_(?P<version>v\d{3})$", re.IGNORECASE)
SEQUENCE_NAME_RE = re.compile(r"^(?P<date>\d{8})_(?P<code>[A-Za-z0-9]{4})_(?P<shot>SHOT_\d{4})_(?P<version>v\d{3})$", re.IGNORECASE)

_LISTING_CACHE: Dict[Tuple[str, str], Tuple[float, List[dict]]] = {}

try:
    from comfyui_brick_tools.utils import sanitize_for_filename as _brick_sanitize_for_filename
except Exception:
    _brick_sanitize_for_filename = None


@dataclass
class ProjectPaths:
    root: str
    projects_root: str
    browser_cache_root: str


def get_paths() -> ProjectPaths:
    output_root = folder_paths.get_output_directory()
    projects_root = os.path.join(output_root, "projects")
    browser_cache_root = os.path.join(projects_root, ".archviz_browser_cache")
    os.makedirs(projects_root, exist_ok=True)
    os.makedirs(browser_cache_root, exist_ok=True)
    return ProjectPaths(root=output_root, projects_root=projects_root, browser_cache_root=browser_cache_root)


def _sanitize_project_name(value: str, fallback: str = DEFAULT_PROJECT_NAME, max_length: int = 120) -> str:
    if _brick_sanitize_for_filename is not None:
        return _brick_sanitize_for_filename(value, fallback=fallback, max_length=max_length)

    clean = (value or "").strip()
    if not clean:
        clean = fallback

    clean = re.sub(rf"[{re.escape(INVALID_FILENAME_CHARS)}]", "-", clean)
    clean = re.sub(r"\s+", " ", clean)
    clean = re.sub(r"-{2,}", "-", clean)
    clean = clean.strip(" .-_\t")

    if not clean:
        clean = fallback

    if clean.upper() in RESERVED_WINDOWS_NAMES:
        clean = f"_{clean}"

    return clean[:max_length].strip() or fallback


def _sanitize_asset_name(value: str, fallback: str, max_length: int = 180) -> str:
    clean = _sanitize_project_name(value, fallback=fallback, max_length=max_length)
    clean = clean.strip()
    if not clean:
        clean = fallback
    return clean


def list_projects(include_default: bool = True) -> List[str]:
    paths = get_paths()
    names = []
    for entry in os.listdir(paths.projects_root):
        if entry.startswith("."):
            continue
        full = os.path.join(paths.projects_root, entry)
        if os.path.isdir(full):
            names.append(entry)
    if include_default and DEFAULT_PROJECT_NAME not in names:
        names.append(DEFAULT_PROJECT_NAME)
    return sorted(names, key=lambda x: (x != DEFAULT_PROJECT_NAME, x.lower()))


def create_project(project_name: str) -> Dict[str, str | List[str]]:
    clean_name = _sanitize_project_name(project_name, fallback=DEFAULT_PROJECT_NAME)
    project_root = _project_path(clean_name)
    images_root = os.path.join(project_root, "images")
    sequences_root = os.path.join(project_root, "sequences")
    videos_root = os.path.join(project_root, "videos")
    metadata_root = os.path.join(project_root, "metadata")
    logs_root = os.path.join(project_root, "logs")

    for path in (project_root, images_root, sequences_root, videos_root, metadata_root, logs_root):
        os.makedirs(path, exist_ok=True)

    _invalidate_project_cache(clean_name)

    return {
        "project_name": clean_name,
        "project_root": project_root,
        "images_root": images_root,
        "sequences_root": sequences_root,
        "videos_root": videos_root,
        "metadata_root": metadata_root,
        "logs_root": logs_root,
        "projects": list_projects(),
        "default_project": DEFAULT_PROJECT_NAME,
    }


def _project_path(project_name: str) -> str:
    paths = get_paths()
    safe_name = (project_name or "").strip()
    target = os.path.abspath(os.path.join(paths.projects_root, safe_name))
    projects_root = os.path.abspath(paths.projects_root)
    if not target.startswith(projects_root + os.sep) and target != projects_root:
        raise ValueError("Invalid project name")
    return target


def _rel_from_projects(path: str) -> str:
    paths = get_paths()
    rel = os.path.relpath(path, paths.projects_root).replace("\\", "/")
    return rel


def _abs_from_projects(rel_path: str) -> str:
    paths = get_paths()
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    target = os.path.abspath(os.path.join(paths.projects_root, rel))
    projects_root = os.path.abspath(paths.projects_root)
    if not target.startswith(projects_root + os.sep) and target != projects_root:
        raise ValueError("Invalid path")
    return target


def _split_rel_path(rel_path: str) -> List[str]:
    rel = (rel_path or "").replace("\\", "/").strip("/")
    parts = [part for part in rel.split("/") if part]
    if len(parts) < 3:
        raise ValueError("Invalid asset path")
    if parts[1] not in {"images", "sequences", "videos"}:
        raise ValueError("Assets can only be managed from images, sequences, or videos.")
    return parts


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _rename_path(src: str, dst: str) -> None:
    src_abs = os.path.abspath(src)
    dst_abs = os.path.abspath(dst)

    if src_abs == dst_abs:
        return

    if _same_path(src_abs, dst_abs):
        parent = os.path.dirname(src_abs)
        stem, ext = os.path.splitext(os.path.basename(dst_abs))
        temp_path = os.path.join(parent, f"{stem}.__archviz_rename__{int(time.time() * 1000)}{ext}")
        while os.path.exists(temp_path):
            temp_path = os.path.join(parent, f"{stem}.__archviz_rename__{time.time_ns()}{ext}")
        os.rename(src_abs, temp_path)
        os.rename(temp_path, dst_abs)
        return

    os.rename(src_abs, dst_abs)


def _invalidate_project_cache(project_name: str) -> None:
    _LISTING_CACHE.pop((project_name, "images"), None)
    _LISTING_CACHE.pop((project_name, "sequences"), None)
    _LISTING_CACHE.pop((project_name, "videos"), None)


def _parse_image_name(path: str) -> Dict[str, Optional[str]]:
    stem = Path(path).stem
    match = IMAGE_NAME_RE.match(stem)
    if not match:
        return {"date": None, "project_code": None, "camera": stem, "version": None}
    return {
        "date": match.group("date"),
        "project_code": match.group("code"),
        "camera": match.group("camera"),
        "version": match.group("version"),
    }


def _parse_sequence_name(path: str) -> Dict[str, Optional[str]]:
    path_obj = Path(path)
    stem = path_obj.stem if path_obj.suffix else path_obj.name
    match = SEQUENCE_NAME_RE.match(stem)
    if not match:
        return {"date": None, "project_code": None, "shot": stem, "version": None}
    return {
        "date": match.group("date"),
        "project_code": match.group("code"),
        "shot": match.group("shot"),
        "version": match.group("version"),
    }


def _collect_images(project_name: str) -> List[dict]:
    project_root = _project_path(project_name)
    images_root = os.path.join(project_root, "images")
    items: List[dict] = []
    if not os.path.isdir(images_root):
        return items

    for dirpath, _, filenames in os.walk(images_root):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in IMAGE_EXTS:
                continue
            full = os.path.join(dirpath, filename)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            width = None
            height = None
            workflow_available = False
            try:
                with Image.open(full) as im:
                    width, height = im.size
                    workflow_available = ext == ".png" and _extract_workflow_from_png_info(_png_text_info(im)) is not None
            except Exception:
                pass
            parsed = _parse_image_name(full)
            rel = _rel_from_projects(full)
            items.append({
                "asset_type": "image",
                "project": project_name,
                "name": os.path.basename(full),
                "display_name": os.path.basename(full),
                "relative_path": rel,
                "date": parsed.get("date"),
                "project_code": parsed.get("project_code"),
                "camera": parsed.get("camera"),
                "version": parsed.get("version"),
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}" if width and height else None,
                "mtime": stat.st_mtime,
                "size_bytes": stat.st_size,
                "thumb_url": f"/archviz_browser/thumb?path={rel}&kind=image&size=320",
                "full_url": f"/archviz_browser/file?path={rel}",
                "workflow_available": workflow_available,
            })
    items.sort(key=lambda x: (x.get("date") or "", x["mtime"]), reverse=True)
    return items


def _sequence_frames(sequence_root: str) -> List[str]:
    frames = []
    try:
        for entry in os.listdir(sequence_root):
            full = os.path.join(sequence_root, entry)
            if os.path.isfile(full) and os.path.splitext(entry)[1].lower() in FRAME_EXTS:
                frames.append(full)
    except OSError:
        return []
    frames.sort()
    return frames


def _collect_sequences(project_name: str) -> List[dict]:
    project_root = _project_path(project_name)
    sequences_root = os.path.join(project_root, "sequences")
    items: List[dict] = []
    if not os.path.isdir(sequences_root):
        return items

    for shot_dir_name in os.listdir(sequences_root):
        shot_dir = os.path.join(sequences_root, shot_dir_name)
        if not os.path.isdir(shot_dir):
            continue
        try:
            seq_dirs = [os.path.join(shot_dir, n) for n in os.listdir(shot_dir)]
        except OSError:
            continue
        for seq_dir in seq_dirs:
            if not os.path.isdir(seq_dir):
                continue
            frames = _sequence_frames(seq_dir)
            if not frames:
                continue
            try:
                stat = os.stat(seq_dir)
            except OSError:
                continue
            width = None
            height = None
            workflow_available = False
            try:
                with Image.open(frames[0]) as first_frame:
                    width, height = first_frame.size
                    workflow_available = _extract_workflow_from_png_info(_png_text_info(first_frame)) is not None
            except Exception:
                pass
            poster_rel = _rel_from_projects(frames[0])
            seq_rel = _rel_from_projects(seq_dir)
            parsed = _parse_sequence_name(seq_dir)
            items.append({
                "asset_type": "sequence",
                "project": project_name,
                "name": os.path.basename(seq_dir),
                "display_name": os.path.basename(seq_dir),
                "relative_path": seq_rel,
                "poster_frame": poster_rel,
                "date": parsed.get("date"),
                "project_code": parsed.get("project_code"),
                "shot": parsed.get("shot") or shot_dir_name,
                "version": parsed.get("version"),
                "frame_count": len(frames),
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}" if width and height else None,
                "mtime": stat.st_mtime,
                "size_bytes": sum(os.path.getsize(frame) for frame in frames if os.path.isfile(frame)),
                "thumb_url": f"/archviz_browser/thumb?path={seq_rel}&kind=sequence&size=320",
                "preview_url": f"/archviz_browser/sequence_preview?path={seq_rel}&size=420",
                "full_url": f"/archviz_browser/file?path={poster_rel}",
                "workflow_available": workflow_available,
            })
    items.sort(key=lambda x: (x.get("date") or "", x["mtime"]), reverse=True)
    return items


def _video_info(path: str) -> Dict[str, Optional[float]]:
    try:
        import cv2

        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            return {}
        try:
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0) or None
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or None
            return {"width": width, "height": height, "frame_count": frame_count, "fps": fps}
        finally:
            capture.release()
    except Exception:
        return {}


def _collect_videos(project_name: str) -> List[dict]:
    project_root = _project_path(project_name)
    videos_root = os.path.join(project_root, "videos")
    items: List[dict] = []
    if not os.path.isdir(videos_root):
        return items

    for dirpath, _, filenames in os.walk(videos_root):
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in VIDEO_EXTS:
                continue
            full = os.path.join(dirpath, filename)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            parsed = _parse_sequence_name(full)
            rel = _rel_from_projects(full)
            info = _video_info(full)
            width = info.get("width")
            height = info.get("height")
            fps = info.get("fps")
            items.append({
                "asset_type": "video",
                "project": project_name,
                "name": os.path.basename(full),
                "display_name": os.path.basename(full),
                "relative_path": rel,
                "date": parsed.get("date"),
                "project_code": parsed.get("project_code"),
                "shot": parsed.get("shot") or os.path.basename(os.path.dirname(full)),
                "version": parsed.get("version"),
                "frame_count": info.get("frame_count"),
                "fps": round(fps, 2) if fps else None,
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}" if width and height else None,
                "mtime": stat.st_mtime,
                "size_bytes": stat.st_size,
                "thumb_url": f"/archviz_browser/thumb?path={rel}&kind=video&size=320",
                "preview_url": f"/archviz_browser/file?path={rel}",
                "full_url": f"/archviz_browser/file?path={rel}",
                "workflow_available": False,
            })
    items.sort(key=lambda x: (x.get("date") or "", x["mtime"]), reverse=True)
    return items


def list_assets(project_name: str, category: str) -> List[dict]:
    category = (category or "images").lower()
    key = (project_name, category)
    now = time.time()
    cached = _LISTING_CACHE.get(key)
    if cached and now - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]

    if category == "sequences":
        items = _collect_sequences(project_name)
    elif category == "videos":
        items = _collect_videos(project_name)
    else:
        items = _collect_images(project_name)

    _LISTING_CACHE[key] = (now, items)
    return items


def _asset_search_blob(item: dict) -> str:
    fields = [
        item.get("display_name"),
        item.get("camera"),
        item.get("shot"),
        item.get("version"),
        item.get("date"),
        item.get("project"),
        item.get("project_code"),
        item.get("resolution"),
        item.get("relative_path"),
    ]
    return " ".join(str(value).lower() for value in fields if value)


def _sort_assets(items: List[dict], sort: str) -> List[dict]:
    mode = (sort or "newest").lower()
    if mode == "oldest":
        return sorted(items, key=lambda item: (item.get("date") or "", item.get("mtime") or 0, item.get("display_name") or ""))
    if mode == "name":
        return sorted(items, key=lambda item: ((item.get("display_name") or "").lower(), -(item.get("mtime") or 0)))
    if mode == "largest":
        return sorted(items, key=lambda item: (item.get("size_bytes") or 0, item.get("mtime") or 0), reverse=True)
    if mode == "smallest":
        return sorted(items, key=lambda item: (item.get("size_bytes") or 0, -(item.get("mtime") or 0)))
    return sorted(items, key=lambda item: (item.get("date") or "", item.get("mtime") or 0, item.get("display_name") or ""), reverse=True)


def paged_assets(project_name: str, category: str, page: int = 1, page_size: int = 48, query: str = "", sort: str = "newest", workflow_only: bool = False) -> Dict:
    items = list_assets(project_name, category)
    q = (query or "").strip().lower()
    if q:
        terms = [term for term in q.split() if term]
        items = [
            item for item in items
            if all(term in _asset_search_blob(item) for term in terms)
        ]
    if workflow_only:
        items = [item for item in items if item.get("workflow_available")]
    items = _sort_assets(items, sort)
    page = max(1, int(page or 1))
    page_size = min(120, max(12, int(page_size or 48)))
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    return {
        "project": project_name,
        "category": category,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": end < total,
        "sort": sort,
        "workflow_only": workflow_only,
        "items": page_items,
    }


def _cache_file_path(rel_key: str, variant: str, extension: str) -> str:
    paths = get_paths()
    digest = hashlib.sha1(f"{variant}|{rel_key}".encode("utf-8")).hexdigest()
    subdir = os.path.join(paths.browser_cache_root, digest[:2], digest[2:4])
    os.makedirs(subdir, exist_ok=True)
    return os.path.join(subdir, f"{digest}.{extension}")


def _source_mtime(abs_path: str) -> float:
    if os.path.isdir(abs_path):
        mtimes = [os.path.getmtime(abs_path)]
        for frame in _sequence_frames(abs_path)[:24]:
            try:
                mtimes.append(os.path.getmtime(frame))
            except OSError:
                pass
        return max(mtimes)
    return os.path.getmtime(abs_path)


def _fit_image(im: Image.Image, size: int) -> Image.Image:
    result = ImageOps.exif_transpose(im.convert("RGB"))
    result.thumbnail((size, size), Image.Resampling.LANCZOS)
    return result


def _load_poster(abs_path: str) -> Image.Image:
    if os.path.isdir(abs_path):
        frames = _sequence_frames(abs_path)
        if not frames:
            raise FileNotFoundError("No frames found in sequence.")
        with Image.open(frames[0]) as frame_im:
            return frame_im.convert("RGB")
    if os.path.splitext(abs_path)[1].lower() in VIDEO_EXTS:
        try:
            import cv2

            capture = cv2.VideoCapture(abs_path)
            if not capture.isOpened():
                raise FileNotFoundError("Video file could not be opened.")
            try:
                ok, frame = capture.read()
                if not ok or frame is None:
                    raise FileNotFoundError("Video has no readable frames.")
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return Image.fromarray(rgb).convert("RGB")
            finally:
                capture.release()
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise FileNotFoundError(f"Could not create video thumbnail: {exc}")
    with Image.open(abs_path) as im:
        return im.convert("RGB")


def ensure_thumbnail(rel_path: str, kind: str, size: int = 320) -> Tuple[str, str]:
    abs_path = _abs_from_projects(rel_path)
    size = max(96, min(1024, int(size or 320)))
    cache_path = _cache_file_path(rel_path, f"thumb:{kind}:{size}", "jpg")
    source_mtime = _source_mtime(abs_path)
    if os.path.isfile(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
        return cache_path, "image/jpeg"

    with _load_poster(abs_path) as poster:
        thumb = _fit_image(poster, size)
        thumb.save(cache_path, format="JPEG", quality=86, optimize=True)
    os.utime(cache_path, (source_mtime, source_mtime))
    return cache_path, "image/jpeg"


def ensure_sequence_preview(rel_path: str, size: int = 420) -> Tuple[str, str]:
    abs_path = _abs_from_projects(rel_path)
    if not os.path.isdir(abs_path):
        raise FileNotFoundError("Sequence folder not found.")

    size = max(128, min(768, int(size or 420)))
    prefer_webp = features.check("webp")
    primary_ext = "webp" if prefer_webp else "gif"
    primary_mime = "image/webp" if prefer_webp else "image/gif"
    cache_path = _cache_file_path(rel_path, f"preview:{size}:{primary_ext}", primary_ext)
    source_mtime = _source_mtime(abs_path)
    if os.path.isfile(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
        return cache_path, primary_mime

    frames = _sequence_frames(abs_path)
    if not frames:
        raise FileNotFoundError("No frames found in sequence.")

    max_frames = 24
    if len(frames) > max_frames:
        step = max(1, math.ceil(len(frames) / max_frames))
        frames = frames[::step][:max_frames]

    pil_frames: List[Image.Image] = []
    for frame_path in frames:
        with Image.open(frame_path) as im:
            pil_frames.append(_fit_image(im, size))

    first = pil_frames[0]

    if prefer_webp:
        try:
            first.save(
                cache_path,
                format="WEBP",
                save_all=True,
                append_images=pil_frames[1:],
                loop=0,
                duration=80,
                quality=82,
                method=4,
            )
            os.utime(cache_path, (source_mtime, source_mtime))
            return cache_path, primary_mime
        except Exception:
            pass

    cache_path = _cache_file_path(rel_path, f"preview:{size}:gif", "gif")
    if os.path.isfile(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
        return cache_path, "image/gif"
    first.save(
        cache_path,
        format="GIF",
        save_all=True,
        append_images=pil_frames[1:],
        loop=0,
        duration=80,
        optimize=False,
        disposal=2,
    )
    os.utime(cache_path, (source_mtime, source_mtime))
    return cache_path, "image/gif"


def ensure_export_image(rel_path: str) -> Tuple[str, str]:
    abs_path = _abs_from_projects(rel_path)
    if os.path.isfile(abs_path) and os.path.splitext(abs_path)[1].lower() == ".png":
        return abs_path, "image/png"

    source_mtime = _source_mtime(abs_path)
    cache_path = _cache_file_path(rel_path, "export:image:png", "png")
    if os.path.isfile(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
        return cache_path, "image/png"

    with _load_poster(abs_path) as source:
        exported = ImageOps.exif_transpose(source)
        exported.save(cache_path, format="PNG", optimize=True)
    os.utime(cache_path, (source_mtime, source_mtime))
    return cache_path, "image/png"


def ensure_sequence_zip(rel_path: str) -> Tuple[str, str]:
    abs_path = _abs_from_projects(rel_path)
    if not os.path.isdir(abs_path):
        raise FileNotFoundError("Sequence folder not found.")

    frames = _sequence_frames(abs_path)
    if not frames:
        raise FileNotFoundError("No frames found in sequence.")

    source_mtime = _source_mtime(abs_path)
    cache_path = _cache_file_path(rel_path, "export:sequence:zip", "zip")
    if os.path.isfile(cache_path) and os.path.getmtime(cache_path) >= source_mtime:
        return cache_path, "application/zip"

    root_name = os.path.basename(abs_path)
    with zipfile.ZipFile(cache_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for frame_path in frames:
            archive.write(frame_path, arcname=f"{root_name}/{os.path.basename(frame_path)}")
    os.utime(cache_path, (source_mtime, source_mtime))
    return cache_path, "application/zip"


def _clear_browser_cache() -> None:
    paths = get_paths()
    cache_root = os.path.abspath(paths.browser_cache_root)
    projects_root = os.path.abspath(paths.projects_root)
    if not cache_root.startswith(projects_root + os.sep):
        raise ValueError("Invalid browser cache root")
    if not os.path.isdir(cache_root):
        return
    for entry in os.listdir(cache_root):
        target = os.path.join(cache_root, entry)
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target, ignore_errors=True)
        else:
            try:
                os.remove(target)
            except OSError:
                pass


def _prune_empty_parents(start_path: str, stop_path: str) -> None:
    current = os.path.abspath(start_path)
    stop = os.path.abspath(stop_path)
    while current.startswith(stop + os.sep) and current != stop:
        try:
            if os.listdir(current):
                break
            os.rmdir(current)
        except OSError:
            break
        current = os.path.dirname(current)


def delete_asset(rel_path: str) -> Dict:
    parts = _split_rel_path(rel_path)
    abs_path = _abs_from_projects(rel_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError("Asset not found.")
    if os.path.isdir(abs_path) and not os.path.islink(abs_path):
        if parts[1] != "sequences":
            raise ValueError("Only sequence folders can be deleted as directories.")
        if len(parts) < 4:
            raise ValueError("Sequence path is too broad.")

    category_root = _abs_from_projects("/".join(parts[:2]))
    project_name = parts[0]
    if os.path.isdir(abs_path) and not os.path.islink(abs_path):
        asset_type = "sequence"
    elif parts[1] == "videos":
        asset_type = "video"
    else:
        asset_type = "image"

    if os.path.isdir(abs_path) and not os.path.islink(abs_path):
        shutil.rmtree(abs_path)
        prune_from = os.path.dirname(abs_path)
    else:
        os.remove(abs_path)
        prune_from = os.path.dirname(abs_path)

    _prune_empty_parents(prune_from, category_root)
    _invalidate_project_cache(project_name)
    _clear_browser_cache()

    return {
        "relative_path": rel_path.replace("\\", "/").strip("/"),
        "asset_type": asset_type,
        "project": project_name,
        "deleted": True,
    }


def _rename_image(abs_path: str, requested_name: str) -> Tuple[str, str]:
    current_name = os.path.basename(abs_path)
    current_stem, current_ext = os.path.splitext(current_name)
    requested = (requested_name or "").strip()
    if not requested:
        raise ValueError("New name is required.")

    requested_stem, requested_ext = os.path.splitext(requested)
    if requested_ext and requested_ext.lower() != current_ext.lower():
        raise ValueError(f"Asset extension must remain {current_ext or 'unchanged'}.")

    base_name = requested_stem if requested_ext else requested
    if not base_name.strip():
        raise ValueError("New name is required.")

    clean_name = f"{_sanitize_asset_name(base_name, fallback=current_stem)}{current_ext}"
    target_path = os.path.join(os.path.dirname(abs_path), clean_name)
    return clean_name, target_path


def _rename_sequence(parts: List[str], abs_path: str, requested_name: str) -> Tuple[str, str]:
    if len(parts) < 4:
        raise ValueError("Sequence path is too broad.")

    current_name = os.path.basename(abs_path)
    clean_name = _sanitize_asset_name(requested_name, fallback=current_name)
    sequences_root = _abs_from_projects("/".join(parts[:2]))
    shot_match = SEQUENCE_NAME_RE.match(clean_name)
    shot_name = shot_match.group("shot") if shot_match else parts[2]
    target_dir = os.path.join(sequences_root, shot_name)
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, clean_name)
    return clean_name, target_path


def rename_asset(rel_path: str, new_name: str) -> Dict:
    parts = _split_rel_path(rel_path)
    abs_path = _abs_from_projects(rel_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError("Asset not found.")

    project_name = parts[0]
    if os.path.isdir(abs_path) and not os.path.islink(abs_path):
        asset_type = "sequence"
    elif parts[1] == "videos":
        asset_type = "video"
    else:
        asset_type = "image"

    if asset_type == "sequence":
        if parts[1] != "sequences":
            raise ValueError("Only sequence folders can be renamed as directories.")
        clean_name, target_path = _rename_sequence(parts, abs_path, new_name)
        prune_from = os.path.dirname(abs_path)
        prune_root = _abs_from_projects("/".join(parts[:2]))
    else:
        clean_name, target_path = _rename_image(abs_path, new_name)
        prune_from = None
        prune_root = None

    if os.path.exists(target_path) and not _same_path(abs_path, target_path):
        raise FileExistsError("An asset with that name already exists.")

    _rename_path(abs_path, target_path)
    if prune_from and prune_root:
        _prune_empty_parents(prune_from, prune_root)

    _invalidate_project_cache(project_name)
    _clear_browser_cache()

    return {
        "asset_type": asset_type,
        "project": project_name,
        "old_relative_path": rel_path.replace("\\", "/").strip("/"),
        "relative_path": _rel_from_projects(target_path),
        "display_name": clean_name,
        "renamed": True,
    }


def _try_parse_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value or value.lower() in {"null", "none"}:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _png_text_info(image: Image.Image) -> Dict:
    info = dict(getattr(image, "info", {}) or {})
    info.update(dict(getattr(image, "text", {}) or {}))
    return info


def _looks_like_workflow_graph(value) -> bool:
    return isinstance(value, dict) and any(key in value for key in ("nodes", "groups", "links", "last_node_id", "last_link_id"))


def _extract_workflow_graph(value, seen: Optional[set] = None):
    if value is None:
        return None

    seen = seen or set()
    value = _try_parse_json(value)

    if isinstance(value, str):
        return None

    value_id = id(value)
    if value_id in seen:
        return None
    seen.add(value_id)

    if _looks_like_workflow_graph(value):
        return value

    if isinstance(value, dict):
        for key in ("workflow", "graph", "workflow_data", "graph_data"):
            workflow = _extract_workflow_graph(value.get(key), seen)
            if workflow is not None:
                return workflow

        for key in ("extra_pnginfo", "pnginfo", "metadata", "archviz_saver", "comfyui"):
            workflow = _extract_workflow_graph(value.get(key), seen)
            if workflow is not None:
                return workflow

    return None


def _extract_workflow_from_png_info(info: Dict):
    for key in ("workflow", "extra_pnginfo", "archviz_saver", "prompt"):
        workflow = _extract_workflow_graph(info.get(key))
        if workflow is not None:
            return workflow
    return None


def extract_workflow_from_png(rel_path: str) -> Dict:
    abs_path = _abs_from_projects(rel_path)
    if os.path.isdir(abs_path):
        frames = _sequence_frames(abs_path)
        if not frames:
            raise FileNotFoundError("Sequence has no frames.")
        abs_path = frames[0]

    if os.path.splitext(abs_path)[1].lower() != ".png":
        raise ValueError("Workflow loading is only supported for PNG files with embedded metadata.")

    with Image.open(abs_path) as im:
        info = _png_text_info(im)

    raw_prompt = info.get("prompt")
    raw_extra = info.get("extra_pnginfo")
    raw_archviz_saver = info.get("archviz_saver")

    prompt = _try_parse_json(raw_prompt)
    extra = _try_parse_json(raw_extra)
    archviz_saver = _try_parse_json(raw_archviz_saver)
    workflow = _extract_workflow_from_png_info(info)

    return {
        "relative_path": rel_path,
        "workflow": workflow,
        "prompt": prompt,
        "extra_pnginfo": extra,
        "archviz_saver": archviz_saver,
        "has_workflow": workflow is not None,
    }
