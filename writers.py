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
