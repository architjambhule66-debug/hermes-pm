import subprocess
import sys
import shutil
import csv
import zipfile
from pathlib import Path
from typing import Dict, Optional, Any
from loguru import logger
from src.perf import perftester
from src.cache import cache_wheel, unpack_wheel_to_cache, install_with_reflink


def get_site_packages(venv_path: Path) -> Path:
    if sys.platform == "win32":
        site_packages = venv_path / "Lib" / "site-packages"
    else:
        py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = venv_path / "lib" / py_version / "site-packages"
    if not site_packages.exists():
        raise RuntimeError(f"site-packages not found: {site_packages}")
    return site_packages


def find_venv() -> Optional[Path]:
    venv_path = Path.cwd() / ".venv"
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    if venv_path.exists() and python_exe.exists():
        return venv_path
    return None


def parse_wheel_metadata(wheel_path: Path) -> Dict[str, str]:
    with zipfile.ZipFile(wheel_path, "r") as zf:
        wheel_files = [f for f in zf.namelist() if f.endswith(".dist-info/WHEEL")]

        if not wheel_files:
            raise RuntimeError(f"No metadata found in {wheel_path.name}")

        wheel_metadata_file = wheel_files[0]
        content = zf.read(wheel_metadata_file).decode("utf-8")

        metadata = {}
        for line in content.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return metadata


def get_dist_info_dir(site_packages: Path, package_name: str) -> Optional[Path]:
    pattern = f"{package_name}-*.dist-info"
    matches = list(site_packages.glob(pattern))
    if not matches:
        alt_name = package_name.replace("-", "_")
        pattern = f"{alt_name}-*.dist-info"
        matches = list(site_packages.glob(pattern))

    return matches[0] if matches else None


def install_wheel(
    wheel_path: Path, venv_path: Optional[Path] = None, use_cache: bool = True
) -> Dict[str, Any]:
    if venv_path is None:
        venv_path = find_venv()
        if venv_path is None:
            raise RuntimeError("No virtual env found")
    site_packages = get_site_packages(venv_path)
    stats = {
        "package": wheel_path.stem,
        "files_installed": 0,
        "used_cache": use_cache,
        "used_reflink": False,
    }
    if use_cache:
        with perftester.track(f"cache_wheel_{wheel_path.name}"):
            cached = cache_wheel(wheel_path)

        with perftester.track(f"unpack_wheel_to_cache_{wheel_path.name}"):
            unpacked_dir = unpack_wheel_to_cache(cached)

        with perftester.track(f"reflink_install_{wheel_path.name}"):
            files_installed = install_with_reflink(unpacked_dir, site_packages)
            stats["files_installed"] = files_installed
            stats["used_reflink"] = True
    else:
        with perftester.track(f"direct_install_{wheel_path.name}"):
            with zipfile.ZipFile(wheel_path, "r") as zf:
                zf.extractall(site_packages)
                stats["files_installed"] = len(zf.namelist())
    logger.info(f"Installed {wheel_path.stem} ({stats['files_installed']} files)")
    return stats


def install_packages(
    wheels: Dict[str, Path], venv_path: Optional[Path], use_cache: bool = True
) -> Dict[str, Dict]:
    results = {}
    for package, wheel_path in wheels.items():
        logger.info(f"Installing {package}...")
        stats = install_wheel(wheel_path, venv_path, use_cache)
        results[package] = stats
    return results


def verify_install(package_name: str, venv_path: Optional[Path] = None) -> bool:
    if venv_path is None:
        venv_path = find_venv()
        if venv_path is None:
            return False
    try:
        site_packages = get_site_packages(venv_path)
        dist_info = get_dist_info_dir(site_packages, package_name)
        return dist_info is not None and dist_info.exists()
    except Exception as e:
        logger.debug(f"Error verifying {package_name}: {e}")
        return False


def unlink_package(package: str, venv_path: Optional[Path] = None) -> bool:
    if venv_path is None:
        from .utils import find_venv

        venv_path = find_venv()

    if not venv_path:
        raise RuntimeError("No virtual environment found")

    try:
        site_packages = next((venv_path / "lib").glob("python*/site-packages"))
    except StopIteration:
        logger.error(f"site-packages not found in {venv_path}")
        return False

    canon_name = package.replace("-", "_")
    dist_info_dirs = list(site_packages.glob(f"{canon_name}*.dist-info"))

    if not dist_info_dirs:
        logger.warning(f"No .dist-info found for {package}")
        return False

    dist_info_dir = dist_info_dirs[0]
    record_file = dist_info_dir / "RECORD"

    if not record_file.exists():
        logger.warning(f"No RECORD file found in {dist_info_dir}")
        return False

    files_to_remove = []
    dirs_to_check = set()

    try:
        with open(record_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or not row[0]:
                    continue

                raw_path = Path(row[0])
                file_path = (
                    raw_path if raw_path.is_absolute() else site_packages / raw_path
                )

                if file_path.exists():
                    files_to_remove.append(file_path)
                    dirs_to_check.add(file_path.parent)
                    if file_path.suffix == ".py":
                        pycache_dir = file_path.parent / "__pycache__"
                        if pycache_dir.exists():
                            dirs_to_check.add(
                                pycache_dir
                            )  # Add __pycache__ for cleanup
                        for pyc in pycache_dir.glob(f"{file_path.stem}.*.pyc"):
                            files_to_remove.append(pyc)
    except Exception as e:
        logger.error(f"Failed to read RECORD file: {e}")
        return False

    removed_count = 0
    for file_path in files_to_remove:
        try:
            file_path.unlink()  # O(1) OS Unlink
            removed_count += 1
        except Exception as e:
            logger.debug(f"Failed to unlink {file_path}: {e}")

    sorted_dirs = sorted(dirs_to_check, key=lambda p: len(p.parts), reverse=True)
    for d in sorted_dirs:
        try:
            if d.exists() and d != site_packages:
                d.rmdir()
        except OSError:
            pass

    package_dir = site_packages / canon_name
    if package_dir.exists() and package_dir.is_dir():
        try:
            package_dir.rmdir()
        except OSError:
            pass

    try:
        if dist_info_dir.exists():
            shutil.rmtree(dist_info_dir)
        logger.info(f"Unlinked {package} ({removed_count} files)")
        return True
    except Exception as e:
        logger.error(f"Failed to remove .dist-info directory: {e}")
        return False


if __name__ == "__main__":
    from pathlib import Path

    venv = find_venv()
    print(f"Venv: {venv}")

    pkg = input("Enter package to unlink: ").strip()

    confirm = input(f"⚠️ This will DELETE files for '{pkg}'. Continue? (y/n): ")
    if confirm.lower() != "y":
        print("Aborted.")
        exit(0)

    success = unlink_package(pkg, venv)

    if success:
        print(f"✅ Successfully unlinked {pkg}")
    else:
        print(f"❌ Failed to unlink {pkg}")
