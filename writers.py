import json
import os
from typing import Dict

import numpy as np
from PIL import Image, PngImagePlugin

from .utils import safe_makedirs


def tensor_to_pil(image_tensor):
    arr = image_tensor.detach().cpu().numpy()
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def save_png(path: str, pil_image: Image.Image, metadata: Dict = None, compress_level: int = 4) -> str:
    safe_makedirs(os.path.dirname(path))
    pnginfo = None
    if metadata:
        pnginfo = PngImagePlugin.PngInfo()
        for key, value in metadata.items():
            try:
                pnginfo.add_text(str(key), json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)
            except Exception:
                pnginfo.add_text(str(key), str(value))
    pil_image.save(path, pnginfo=pnginfo, compress_level=compress_level)
    return path


def tensor_to_rgb_array(image_tensor):
    arr = image_tensor.detach().cpu().numpy()
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    if arr.ndim != 3:
        raise ValueError('Video frames must be HWC image tensors.')
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    if arr.shape[2] > 3:
        arr = arr[:, :, :3]
    return arr


def save_mp4(path: str, image_tensors, fps: float = 24.0, codec: str = 'mp4v') -> str:
    import cv2

    safe_makedirs(os.path.dirname(path))
    frames = [tensor_to_rgb_array(image_tensor) for image_tensor in image_tensors]
    if not frames:
        raise ValueError('At least one frame is required to save a video.')

    height, width = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(path, fourcc, float(fps), (width, height))
    if not writer.isOpened():
        raise RuntimeError('Could not open MP4 writer. Check that OpenCV video support is available.')

    try:
        for frame in frames:
            if frame.shape[:2] != (height, width):
                raise ValueError('All video frames must have the same resolution.')
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()

    return path
