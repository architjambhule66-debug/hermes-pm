import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class BenchmarkResult:
    tool: str
    tier: str
    cold_time: float
    warm_time: float
    venv_size: int
    cache_size: int
    package_count: int
    python_version: str
    os_platform: str
    timestamp: str


def create_temp_dir() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="hermes_bench_"))
    return temp_dir


def cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def measure_disk_usage(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass

    return total


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 3600,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )


def count_installed_packages(venv_path: Path) -> int:
    if not venv_path.exists():
        return 0

    pip_exe = venv_path / "bin" / "pip"
    if pip_exe.exists():
        try:
            result = subprocess.run(
                [str(pip_exe), "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return len(packages)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    site_packages = venv_path / "lib"
    if not site_packages.exists():
        return 0

    python_dirs = list(site_packages.glob("python*"))
    if not python_dirs:
        return 0

    site_packages = python_dirs[0] / "site-packages"
    if not site_packages.exists():
        return 0

    dist_info_dirs = list(site_packages.glob("*.dist-info"))
    return len(dist_info_dirs)


def read_requirements_file(req_file: Path) -> List[str]:
    packages = []
    with open(req_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                packages.append(line)
    return packages


def save_result(result: BenchmarkResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{result.tool}_{result.tier}.json"
    filepath = output_dir / filename

    with open(filepath, "w") as f:
        json.dump(asdict(result), f, indent=2)

    print(f"Results saved to: {filepath}")


def load_results(results_dir: Path) -> List[BenchmarkResult]:
    results = []

    if not results_dir.exists():
        return results

    for filepath in results_dir.glob("*.json"):
        with open(filepath) as f:
            data = json.load(f)
            results.append(BenchmarkResult(**data))

    return results


def format_size(bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"


def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.2f}s"


def get_system_info() -> Dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "os_platform": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
    }


def clear_cache(cache_dir: Path) -> None:
    if cache_dir.exists():
        print(f"Clearing cache: {cache_dir}")
        cleanup_dir(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
