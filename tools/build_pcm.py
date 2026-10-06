"""Build the KiCad Plugin and Content Manager (PCM) package.

    python tools/build_pcm.py 1.0.0

Writes to dist/:
  io.github.roshan-0907.pofv-via-3d-<version>.zip   upload this to the GitHub release
  metadata.json                                      submit this to kicad/addons/metadata
  icon.png                                           64x64 icon for the same submission

Needs Pillow.
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "pofv_via_3d"
DIST = ROOT / "dist"

IDENTIFIER = "io.github.roshan-0907.pofv-via-3d"
REPO = "https://github.com/Roshan-0907/Kicad-capped-and-filled-via-veiwer"

# Files of the plugin that go into the package (plugins/ in the archive).
PLUGIN_FILES = ["plugin.json", "pofv.py", "apply_pofv.py", "clear_pofv.py",
                "unmark_vias.py", "requirements.txt"]


def package_metadata(version: str) -> dict:
    return {
        "$schema": "https://go.kicad.org/pcm/schemas/v2",
        "name": "Filled & Capped Vias (POFV)",
        "description": "Show filled and capped (POFV) vias under solder mask in the 3D viewer",
        "description_full": (
            "Sets the selected vias (or all vias) to filled, capped and tented in one undoable "
            "step. KiCad 10.0.6+ then draws them in the 3D viewer without a hole and covered by "
            "solder mask, looking like a trace, which matches how JLCPCB capped and filled vias "
            "come out. Fixes the case where the via dialog's Type VII preset leaves vias not "
            "tented, so they show as bare copper even with Tent vias enabled."
        ),
        "identifier": IDENTIFIER,
        "type": "plugin",
        "author": {"name": "Roshan-0907", "contact": {"web": "https://github.com/Roshan-0907"}},
        "license": "MIT",
        "resources": {"homepage": REPO, "issues": REPO + "/issues"},
        "tags": ["via", "viewer-3d", "ipc-4761", "jlcpcb", "manufacturing"],
        "versions": [
            {
                "version": version,
                "status": "stable",
                "kicad_version": "10.0",
                "runtime": "ipc",
            }
        ],
    }


def build(version: str) -> None:
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / f"{IDENTIFIER}-{version}.zip"

    icon = DIST / "icon.png"
    Image.open(PLUGIN / "icons" / "apply_light_48.png").convert("RGBA").resize(
        (64, 64), Image.LANCZOS).save(icon)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("metadata.json", json.dumps(package_metadata(version), indent=2) + "\n")
        z.write(icon, "resources/icon.png")

        for name in PLUGIN_FILES:
            z.write(PLUGIN / name, f"plugins/{name}")

        for png in sorted((PLUGIN / "icons").glob("*.png")):
            z.write(png, f"plugins/icons/{png.name}")

    with zipfile.ZipFile(zip_path) as z:
        install_size = sum(i.file_size for i in z.infolist() if not i.is_dir())

    repo_meta = package_metadata(version)
    v = repo_meta["versions"][0]
    v.update(
        download_url=f"{REPO}/releases/download/v{version}/{zip_path.name}",
        download_sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        download_size=zip_path.stat().st_size,
        install_size=install_size,
    )
    (DIST / "metadata.json").write_text(json.dumps(repo_meta, indent=2) + "\n")
    print(f"built {zip_path} ({zip_path.stat().st_size} bytes)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "1.0.0")
