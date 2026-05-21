# ComfyUI Brick Tools

A focused custom-node pack for **organized Brick saving and browsing** in ComfyUI.

## Included

- **Save Brick Image**
- **Save Brick Sequence**
- **Save Brick Video**
- **Brick Browser** sidebar tab for browsing saved project images, sequences, and videos

## Naming rules

### Images

- camera number mode: `YYYYMMDD_PROJECTCODE_cam-02_v004.png`
- camera name mode: `YYYYMMDD_PROJECTCODE_lobby-view_v004.png`
- with model prefix: `YYYYMMDD_flux-2-dev_PROJECTCODE_cam-02_v004.png`

Examples:

- `20260312_8140_cam-02_v004.png`
- `20260312_8140_lobby-view_v004.png`

### Sequences

Sequence folder:

`YYYYMMDD_PROJECTCODE_SHOT_0007_v001`

With model prefix:

`YYYYMMDD_flux-2-dev_PROJECTCODE_SHOT_0007_v001`

Frames inside:

`0001.png`, `0002.png`, `0003.png` ...

### Videos

Video file:

`YYYYMMDD_PROJECTCODE_SHOT_0007_v001.mp4`

With model prefix:

`YYYYMMDD_flux-2-dev_PROJECTCODE_SHOT_0007_v001.mp4`

Saved under:

`videos/SHOT_0007/`

## Project behavior

- Both saver nodes default to the project **`0000_base`**.
- Existing projects appear in the `project_name` dropdown.
- Each saver node has a **Create Project** button.
- Clicking the button opens a popup dialog where you type the project name.
- The project folder is created immediately under `ComfyUI/output/projects/`.
- The dropdown refreshes and switches to the new project automatically.

## Image node behavior

- `model_prefix` is optional. Leave it empty to keep the original naming.
- When filled, it is sanitized and inserted after the date, for example `20260521_flux-2-dev_8140_cam-02_v004.png`.
- `camera_mode` can be switched between **camera_number** and **camera_name**.
- The node UI shows the integer widget when `camera_number` is selected.
- The node UI shows the text widget when `camera_name` is selected.
- `camera_number` is formatted as `cam-02`.
- `camera_name` is sanitized into a filename-safe lowercase token with spaces converted to hyphens.

## Sequence node behavior

- `model_prefix` is optional and uses the same prefix behavior as images.
- `shot_number` is an integer formatted as `SHOT_0007`.
- The node includes a **Download ZIP** button.
- After the node has saved a sequence once, the button downloads the latest sequence from that node as a ZIP archive.

## Video node behavior

- `model_prefix` is optional and uses the same prefix behavior as images.
- `shot_number` is an integer formatted as `SHOT_0007`.
- The node accepts ComfyUI's standard `VIDEO` input, matching the default **Save Video** node save path.
- `format` and `codec` use the same choices as ComfyUI's default **Save Video** node.
- If you start from image frames, create the `VIDEO` first with ComfyUI's video nodes, then connect it here.
- The video is saved with the same project/date/shot/version naming logic as sequences.

## Browser behavior

- Browse saved assets under `ComfyUI/output/projects/`.
- Filter by project, images, sequences, videos, search text, sort order, and workflow availability.
- Preview image assets, sequence posters, and playable videos.
- Load embedded ComfyUI workflows from Brick Saver PNG metadata.
- Download, copy, rename, or delete saved assets from the sidebar.

## Project code extraction

The filename uses a short project code taken from the project name:

1. first four detected digits if the project name contains at least four digits
2. otherwise first four alphanumeric characters as a fallback

So a project like `8140 Riverside Tower` becomes code `8140`.

## Folder structure

```text
ComfyUI/output/
└── projects/
    └── 8140 Riverside Tower/
        ├── images/
        │   └── 20260312/
        │       └── 20260312_8140_cam-02_v004.png
        ├── sequences/
        │   └── SHOT_0007/
        │       └── 20260312_8140_SHOT_0007_v001/
        │           ├── 0001.png
        │           ├── 0002.png
        │           └── ...
        ├── videos/
        │   └── SHOT_0007/
        │       └── 20260312_8140_SHOT_0007_v001.mp4
        ├── metadata/
        │   ├── latest_versions.json
        │   └── manifest.jsonl
        └── logs/
```

## Install

Copy this folder into:

```text
ComfyUI/custom_nodes/comfyui_brick_tools
```

Then restart ComfyUI and reload the browser.

## Notes

- The pack uses frontend extensions in `web/js` so the saver nodes and Brick Browser sidebar can run from the same custom-node package.
- Images are always saved as PNG.
- Image batches larger than one are saved with `_01`, `_02`, `_03` suffixes after the version token.
- The older standalone `comfyui_brick_saver` and `comfyui_brick_browser` packages are no longer needed once this package is installed.
