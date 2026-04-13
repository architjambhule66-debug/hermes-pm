from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import tomllib
import tomli_w
from loguru import logger

LOCKFILE_PATH = Path("hermes.lock")


@dataclass
class LockedPackage:
    name: str
    version: str
    source: str = "https://pypi.org/simple"
    wheel_url: str = ""
    wheel_hash: str = ""
    wheel_filename: str = ""


def load_lockfile() -> Dict[str, LockedPackage]:
    if not LOCKFILE_PATH.exists():
        logger.debug("No hermes.lock found")
        return {}
    try:
        with LOCKFILE_PATH.open("rb") as f:
            data = tomllib.load(f)

        locked_packages = {}
        for pkg_data in data.get("package", []):
            name = pkg_data["name"]
            locked_packages[name] = LockedPackage(
                name=name,
                version=pkg_data["version"],
                source=pkg_data.get("source", "https://pypi.org/simple"),
                wheel_url=pkg_data.get("wheel", {}).get("url", ""),
                wheel_hash=pkg_data.get("wheel", {}).get("hash", ""),
                wheel_filename=pkg_data.get("wheel", {}).get("filename", ""),
            )

        logger.debug(f"Loaded {len(locked_packages)} packages from hermes.lock")
        return locked_packages
    except Exception as e:
        logger.error(f"Failed to parse hermes.lock: {e}")
        raise RuntimeError(f"Invalid hermes.lock: {e}")


def create_lockfile() -> Path:
    if LOCKFILE_PATH.exists():
        logger.debug("hermes.lock already exists")
        return LOCKFILE_PATH

    data = {
        "version": 1,
        "package": [],
    }
    with LOCKFILE_PATH.open("wb") as f:
        tomli_w.dump(data, f)
    logger.info("Created hermes.lock")
    return LOCKFILE_PATH


def update_lockfile(resolved: Dict[str, str]) -> None:
    """Update lockfile with resolved package versions"""
    packages = []
    for name in sorted(resolved.keys()):
        version = resolved[name]
        pkg_data = {
            "name": name,
            "version": version,
            "source": "https://pypi.org/simple",
        }
        packages.append(pkg_data)

    lockfile_data = {
        "version": 1,
        "package": packages,
    }
    try:
        with LOCKFILE_PATH.open("wb") as f:
            tomli_w.dump(lockfile_data, f)
        logger.info(f"Updated hermes.lock with {len(packages)} packages")
    except Exception as e:
        raise RuntimeError(f"Failed to write hermes.lock: {e}")


def lockfile_exists() -> bool:
    return LOCKFILE_PATH.exists()
