import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from utils import BenchmarkResult, create_temp_dir, cleanup_dir, measure_disk_usage, count_installed_packages, read_requirements_file, save_result, get_system_info, clear_cache, format_time

def get_hermes_cache_dir() -> Path:
    cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return Path(cache_home) / "hermes"

def benchmark_hermes(tier: str, requirements_file: Path) -> BenchmarkResult:
    print(f"\n{'=' * 60}")
    print(f"Benchmarking Hermes - {tier}")
    print(f"{'=' * 60}\n")
    sys_info = get_system_info()

    packages = read_requirements_file(requirements_file)
    print(f"Packages to install: {len(packages)}")
    print(f"  {', '.join(pkg.split('==')[0] for pkg in packages[:5])}")
    if len(packages) > 5:
        print(f"  ... and {len(packages) - 5} more")

    bench_dir = create_temp_dir()
    project_dir = bench_dir / "project"
    project_dir.mkdir()

    print(f"\nBenchmark directory: {bench_dir}")

    try:
        cache_dir = get_hermes_cache_dir()
        print(f"\n--- Cold Cache Benchmark ---")
        print("Clearing Hermes cache...")
        clear_cache(cache_dir)

        print("Initializing Hermes project")
        result = subprocess.run(
            ["hermes", "init"], cwd=project_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error initializing project: {result.stderr}")
            raise RuntimeError("Hermes init failed")

        print(f"Installing {len(packages)} packages (cold cache)")
        cold_start = time.time()

        for package in packages:
            result = subprocess.run(
                ["hermes", "add", package],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"Error adding {package}: {result.stderr}")
                raise RuntimeError(f"Failed to add {package}")

        cold_time = time.time() - cold_start
        print(f"Cold installation completed in {format_time(cold_time)}")

        venv_path = project_dir / ".venv"
        venv_size_cold = measure_disk_usage(venv_path)
        package_count = count_installed_packages(venv_path)
        print(f"Virtual environment size: {venv_size_cold / (1024**2):.2f} MB")
        print(f"Packages installed: {package_count}")

        print(f"\n--- Warm Cache Benchmark ---")
        print("Removing virtual environment")
        cleanup_dir(venv_path)

        print("Recreating virtual environment...")
        result = subprocess.run(
            ["python3", "-m", "venv", str(venv_path)], capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error creating venv: {result.stderr}")
            raise RuntimeError("Failed to recreate venv")

        print(f"Reinstalling {len(packages)} packages (warm cache)...")
        warm_start = time.time()

        result = subprocess.run(
            ["hermes", "sync"], cwd=project_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error syncing: {result.stderr}")
            raise RuntimeError("Hermes sync failed")

        warm_time = time.time() - warm_start
        print(f"Warm installation completed in {format_time(warm_time)}")

        venv_size = measure_disk_usage(venv_path)
        cache_size = measure_disk_usage(cache_dir)

        print(f"\nFinal measurements:")
        print(f"  Venv size: {venv_size / (1024**2):.2f} MB")
        print(f"  Cache size: {cache_size / (1024**2):.2f} MB")
        print(f"  Total: {(venv_size + cache_size) / (1024**2):.2f} MB")
        print(f"  Speedup (warm/cold): {cold_time / warm_time:.2f}x")

        result = BenchmarkResult(
            tool="hermes",
            tier=tier,
            cold_time=cold_time,
            warm_time=warm_time,
            venv_size=venv_size,
            cache_size=cache_size,
            package_count=package_count,
            python_version=sys_info["python_version"],
            os_platform=sys_info["os_platform"],
            timestamp=datetime.now().isoformat(),
        )

        return result

    finally:
        print(f"\nCleaning up benchmark directory...")
        cleanup_dir(bench_dir)


def main():
    if len(sys.argv) != 2:
        print("Usage: bench_hermes.py <tier>")
        print("Example: bench_hermes.py tier1_basic")
        sys.exit(1)

    tier = sys.argv[1]

    script_dir = Path(__file__).parent
    benchmarks_dir = script_dir.parent
    requirements_file = benchmarks_dir / "requirements" / f"{tier}.txt"

    if not requirements_file.exists():
        print(f"Error: Requirements file not found: {requirements_file}")
        sys.exit(1)

    if shutil.which("hermes") is None:
        print("Error: hermes command not found in PATH")
        sys.exit(1)

    try:
        result = benchmark_hermes(tier, requirements_file)
        results_dir = benchmarks_dir / "results" / "raw"
        save_result(result, results_dir)

        print(f"\n{'=' * 60}")
        print("Benchmark completed successfully!")
        print(f"{'=' * 60}\n")

    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
