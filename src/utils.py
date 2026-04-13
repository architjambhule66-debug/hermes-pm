import sys
import venv
import platform
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

@dataclass
class PlatformInfo:
    os: str
    arch: str 
    python_version: str 
    implementation: str 
    abi: str 

@dataclass
class WheelInfo:
    url: str 
    filename: str
    hash: str 
    size: int

def configure_logging(level: str = "INFO"):
    logger.remove()

    if level == "DEBUG":
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level>"
        )
    else:
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <7}</level> | "
                   "<level>{message}</level>"
        )

def get_platform() -> PlatformInfo:
    if sys.platform == "darwin":
        os_name = "macosx"
    elif sys.platform.startswith("linux"):
        os_name = "linux"
    elif sys.platform == "win32":
        os_name = "win32"
    else:
        os_name = sys.platform

    machine = platform.machine()
    if machine in ("arm64", "aarch64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64"):
        arch = "x86_64"
    else:
        arch = machine

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    impl = sys.implementation.name
    if impl == "cpython":
        impl_short = "cp"
    elif impl == "pypy":
        impl_short = "pp"
    else:
        impl_short = impl[:2]

    abi = f"{impl_short}{sys.version_info.major}{sys.version_info.minor}"

    return PlatformInfo(os=os_name, arch=arch, python_version=py_ver, implementation=impl_short, abi=abi)

def get_tags() -> List[str]:
    return [str(tag) for tag in sys_tags()]

def select_best_wheel(availabel_wheels: List[WheelInfo], compatible_tags: List[str]) -> Optional[WheelInfo]:
    for tag in compatible_tags:
        for wheel in availabel_wheels:
            try:
                name, version, build , wheel_tags = parse_wheel_filename(wheel.filename)
                for wheel_tag in wheel_tags:
                    if str(wheel_tag) == tag:
                        logger.debug(f"Selected Wheel: {wheel.filename}, tag : {tag}")
                        return wheel
            except Exception as e:
                logger.debug(f"Error parsing wheel {wheel.filename}: {e}")
                continue

def verify_hash(file_path: Path, expected: str) -> bool:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    actual = hasher.hexdigest()
    return actual == expected


class VenvBuilder(venv.EnvBuilder):
    def __init__(self):
        super().__init__(with_pip=False)

def create_venv(path: Path = Path(".venv")) -> Path:
    if path.exists():
        logger.debug(f"venv already exists: {path}")
        return path
    try:
        builder = venv.EnvBuilder(with_pip=False)
        builder.create(str(path))
        logger.info(f"Created venv: {path}")
        return path
    except Exception as e:
        raise RuntimeError(f"Failed to create venv: {e}")

def find_venv() -> Optional[Path]:
    venv_path = Path.cwd() / ".venv"
    if not venv_path.exists():
        return None
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    if python_exe.exists():
        return venv_path
    return None

def venv_exists() -> bool:
    return find_venv() is not None

def get_venv_python(venv_path: Path) -> Path:
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"

def get_site_packages(venv_path: Path) -> Path:
    if sys.platform == "win32":
        site_packages = venv_path / "Lib" / "site-packages"
    else:
        py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = venv_path / "lib" / py_version / "site-packages"
    if not site_packages.exists():
        raise RuntimeError(f"site-packages not found: {site_packages}")
    return site_packages

def parse_package_spec(spec: str) -> tuple[str, str]:
    if "@" in spec:
        name, version = spec.split("@", 1)
        return name.strip(), f"=={version.strip()}"
    for op in [">=", "<=", "==", "~=", ">", "<", "!="]:
        if op in spec:
            parts = spec.split(op, 1)
            return parts[0].strip(), f"{op}{parts[1].strip()}"
    return spec.strip(), ">=0.0.0"

