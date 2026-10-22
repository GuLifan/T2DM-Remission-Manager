"""制作完整Sealos源码/页面分发，白名单排除私有配置、病例和依赖目录。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect() -> dict[str, bytes]:
    skipped = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "tests", "test", "dist"}
    files = {}
    for category in ["backend", "frontend"]:
        for folder, dirs, names in os.walk(ROOT / category, followlinks=False):
            dirs[:] = [n for n in dirs if n not in skipped]
            for name in names:
                path = Path(folder) / name
                if ".test." in name or name.endswith((".pyc", ".tsbuildinfo", ".log", ".db", ".key", ".pem")):
                    continue
                if name.startswith(".env") and name != ".env.example":
                    continue
                if path.is_symlink():
                    raise ValueError("发布源码不允许符号链接 / Symlink source")
                files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    dist = ROOT / "frontend/dist"
    if not (dist / "index.html").is_file():
        raise ValueError("请先构建前端 / Build frontend first")
    for path in dist.rglob("*"):
        if path.is_symlink():
            raise ValueError("前端构建不允许符号链接 / Symlink asset")
        if path.is_file():
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in [
        "README.md",
        "SECURITY.md",
        "start.sh",
        "entrypoint.sh",
        "_SPEC/CURRENT_SPEC.md",
        "scripts/setup.sh",
        "scripts/demo_service.py",
        "scripts/replace_deployment.py",
        "docs/DEPLOY_SEALOS.md",
        "docs/FRESH_INSTALL.md",
        "docs/USER_GUIDE.md",
        "docs/EVIDENCE.md",
        "docs/VALIDATION.md",
        "resources/evidence/README.md",
        "resources/evidence/manifest.json",
    ]:
        path = ROOT / name
        if path.is_symlink():
            raise ValueError("发布文件不允许符号链接 / Symlink file")
        files[name] = path.read_bytes()
    return files


def build(output: Path) -> Path:
    version = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))["version"]
    files = collect()
    manifest = {
        "format": "etmms-complete-release-1",
        "version": version,
        "clinical_contract": "v0.3",
        "input_schema": "v0.4",
        "database_head": "d04data001",
        "files": {n: digest(b) for n, b in sorted(files.items())},
    }
    files["release-manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"ETMMS-v{version}-sealos-full-{date.today():%Y%m%d}.zip"
    if archive.exists():
        raise ValueError("目标ZIP已存在，请选择新输出目录 / Choose a new output directory")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(f"ETMMS-v{version}/{name}")
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            z.writestr(info, content)
    (output / "SHA256SUMS.txt").write_text(f"{digest(archive.read_bytes())}  {archive.name}\n", encoding="utf-8")
    print(f"完整包 / Complete release: {archive}; {len(files)} files")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a complete ETMMS operating distribution")
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output.resolve())
