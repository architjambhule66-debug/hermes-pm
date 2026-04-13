import os
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path
from typing import Dict
from loguru import logger

CACHE_DIR = Path.home() / ".miniuv_cache"

def get_cache_dir() -> Path:
    if sys.platform == "darwin":
        cache_dir = Path.home() / "Library" / "Caches" / "hermes"
    elif sys.platform.startswith("linux"):
        xdg_cache = os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")
        cache_dir = Path(xdg_cache) / "hermes"
    elif sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        cache_dir = Path(local_app_data) / "hermes" / "Cache"
    else:
        cache_dir = Path.home() / ".cache" / "hermes"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def cache_wheel(wheel_path: Path) -> Path:
    cache_dir = get_cache_dir() / "wheels"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = cache_dir / wheel_path.name
    if not cached_path.exists():
        logger.debug(f"Caching wheel: {wheel_path.name}")
        shutil.copy2(wheel_path, cached_path)
    else:
        logger.debug(f"Wheel already cached: {wheel_path.name}")
    return cached_path

def get_unpacked_cache_dir(wheel_path: Path) -> Path:
    cache_dir = get_cache_dir() / "installed"
    return cache_dir / wheel_path.stem

def unpack_wheel_to_cache(wheel_path: Path) -> Path:
    unpacked_dir = get_unpacked_cache_dir(wheel_path)
    if unpacked_dir.exists():
        logger.debug(f"Wheel already unpacked: {wheel_path.name}")
        return unpacked_dir
    unpacked_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel_path, "r") as zf:
        zf.extractall(unpacked_dir)
    logger.debug(f"Unpacked {wheel_path.name} to {unpacked_dir}")
    return unpacked_dir

def cache_info() -> Dict[str, any]:
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return {
            "location": str(cache_dir),
            "size": 0,
            "size_mb": 0.0,
            "wheels": 0,
            "unpacked": 0,
        }

    total_size = 0
    wheel_count = 0
    unpacked_count = 0

    wheels_dir = cache_dir / "wheels"
    if wheels_dir.exists():
        for wheel in wheels_dir.glob("*.whl"):
            total_size += wheel.stat().st_size
            wheel_count += 1

    installed_dir = cache_dir / "installed"
    if installed_dir.exists():
        for pkg_dir in installed_dir.iterdir():
            if pkg_dir.is_dir():
                unpacked_count += 1
                for file in pkg_dir.rglob("*"):
                    if file.is_file():
                        total_size += file.stat().st_size

    return {
        "location": str(cache_dir),
        "size": total_size,
        "size_mb": total_size / 1024 / 1024,
        "wheels": wheel_count,
        "unpacked": unpacked_count,
    }

def clear_cache():
    cache_dir = get_cache_dir()
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        logger.info(f"Cache cleared: {cache_dir}")
    cache_dir.mkdir(parents=True, exist_ok=True)

def install_with_reflink(src_dir: Path, dest_dir: Path) -> int:
    files_installed = 0
    reflinks_created = 0
    hardlinks_created = 0
    copies_created = 0

    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue

        rel_path = src_file.relative_to(src_dir)
        dest_file = dest_dir / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        if dest_file.exists():
            dest_file.unlink()

        installed = False
        if sys.platform == "darwin":
            try:
                result = subprocess.run(["cp", "-c", str(src_file), str(dest_file)], check=True, capture_output=True, text=True,)
                reflinks_created += 1
                installed = True 
            except subprocess.CalledProcessError as e:
                logger.debug(f"Reflink failed for {rel_path}: {e}")

        if not installed:
            try:
                os.link(src_file, dest_file)
                hardlinks_created += 1
                installed = True
            except OSError as e:
                logger.debug(f"Hardlink failed for {rel_path}: {e}")

        if not installed:
            try:
                shutil.copy2(src_file, dest_file)
                copies_created += 1
                installed = True
            except Exception as e:
                logger.error(f"Failed to install {rel_path}: {e}")
                raise

        files_installed += 1

    logger.debug(f"(reflinks: {reflinks_created}, hardlinks: {hardlinks_created}, copies: {copies_created})")
    return files_installed


