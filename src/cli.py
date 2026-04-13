import asyncio
import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table
from loguru import logger
from importlib.metadata import version, PackageNotFoundError
from .resolver import build_resolution
from .network import fetch_and_download
from .install import install_packages, unlink_package, verify_install
from .cache import cache_info, clear_cache
from .utils import create_venv, find_venv, venv_exists, parse_package_spec, configure_logging
from .project import load_pyproject, add_dependency, get_dependencies,create_pyproject, pyproject_exists, remove_dependency
from .lockfile import load_lockfile, update_lockfile, create_lockfile, lockfile_exists
from .perf import perftester
from .audit import scan_all

__version__ = version("hermes-pm")

app = typer.Typer(
    name="hermes",
    help="Fast Python package manager with uv-like optimizations",
    no_args_is_help=True,
    add_completion=False,
)

cache_app = typer.Typer(help="Cache management commands")
app.add_typer(cache_app, name="cache")
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"hermes version {__version__}")
        raise typer.Exit()


@app.callback()
def common(
    verbose: bool = typer.Option(False, "-v", "--verbose"),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
    version: bool = typer.Option(None, "--version", "-V", callback=version_callback, is_eager=True, help="Show version and exit",),):
    if verbose and quiet:
        typer.echo("Cannot use --verbose and --quiet together")
        raise typer.Exit(1)
    if verbose:
        configure_logging("DEBUG")
    elif quiet:
        configure_logging("WARNING")
    else:
        configure_logging("INFO")


@app.command()
def init(name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name")):
    console.print("\n[bold blue]Initializing project...[/bold blue]\n")
    try:
        if venv_exists():
            console.print("[green]Virtual environment already exists: .venv[/green]")
        else:
            create_venv()
            console.print("[green]Created virtual environment: .venv[/green]")

        if pyproject_exists():
            console.print("[green]pyproject.toml already exists[/green]")
        else:
            create_pyproject(name)
            console.print("[green]Created pyproject.toml[/green]")

        if lockfile_exists():
            console.print("[green]hermes.lock already exists[/green]")
        else:
            create_lockfile()
            console.print("[green]Created hermes.lock[/green]")

        console.print("\n[bold green]✓ Project initialized successfully![/bold green]")
        console.print("\nNext steps:")
        console.print("  [cyan]hermes add <package>[/cyan]  - Add a package")
        console.print("  [cyan]hermes sync[/cyan]           - Install from lockfile")
    except Exception as e:
        console.print(f"\n[bold red]✗ Initialization failed:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def add(packages: List[str] = typer.Argument(..., help="Packages to add (e.g., 'requests' or 'requests>=2.30.0')"),):
    console.print(f"\n[bold blue]Adding {len(packages)} package(s)...[/bold blue]\n")
    if not venv_exists():
        console.print("[bold red]✗ No virtual environment found.[/bold red]")
        console.print("Run [cyan]hermes init[/cyan] first to create a virtual environment.")
        raise typer.Exit(1)

    try:
        parsed_packs = {}
        for spec in packages:
            name, version = parse_package_spec(spec)
            parsed_packs[name] = version
            console.print(f"  • {name}: {version}")
        console.print()

        for name, version_spec in parsed_packs.items():
            add_dependency(name, version_spec)
        console.print("✓ [green]Updated pyproject.toml[/green]")

        all_deps = get_dependencies()
        console.print(f"\n[bold]Resolving dependencies ({len(all_deps)} total)...[/bold]")
        resolved = asyncio.run(build_resolution(all_deps))
        console.print(f"[green]Resolved {len(resolved)} packages[/green]")

        download_dir = Path.cwd() / ".hermes_downloads"
        download_dir.mkdir(exist_ok=True)

        console.print("\n[bold]Downloading wheels...[/bold]")
        wheels = asyncio.run(fetch_and_download(resolved, download_dir))
        console.print(f"[green]Downloaded {len(wheels)} wheels[/green]")

        console.print("\n[bold]Installing packages...[/bold]")
        venv_path = find_venv()
        results = install_packages(wheels, venv_path, use_cache=True)

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Package", style="yellow")
        table.add_column("Files", justify="right")
        table.add_column("Method", justify="center")

        for pkg, stats in sorted(results.items()):
            method = "reflink" if stats.get("used_reflink") else "copy"
            table.add_row(pkg, str(stats["files_installed"]), method)

        console.print(table)
        update_lockfile(resolved)
        console.print("\n [green]Updated hermes.lock[/green]")
        console.print(f"\n[bold green] Installed {len(results)} packages successfully![/bold green]")
        perftester.report()
    except Exception as e:
        console.print(f"\n[bold red] Installation failed:[/bold red] {e}")
        logger.exception("Detailed error:")
        raise typer.Exit(1)


@app.command()
def sync():
    console.print("\n[bold blue]Syncing from hermes.lock...[/bold blue]\n")
    if not venv_exists():
        console.print("[bold red]✗ No virtual environment found.[/bold red]")
        console.print("Run [cyan]hermes init[/cyan] first.")
        raise typer.Exit(1)

    if not lockfile_exists():
        console.print("[bold red]✗ No hermes.lock found.[/bold red]")
        console.print(
            "Run [cyan]hermes add <package>[/cyan] first to create a lockfile."
        )
        raise typer.Exit(1)

    try:
        locked_packages = load_lockfile()
        if not locked_packages:
            console.print("[yellow] hermes.lock is empty. Nothing to install.[/yellow]")
            return
        console.print(f"Found {len(locked_packages)} locked packages\n")
        locked_dict = {name: pkg.version for name, pkg in locked_packages.items()}

        download_dir = Path.cwd() / ".hermes_downloads"
        download_dir.mkdir(exist_ok=True)

        console.print("[bold]Downloading wheels...[/bold]")
        wheels = asyncio.run(fetch_and_download(locked_dict, download_dir))
        console.print(f"[green]Downloaded {len(wheels)} wheels[/green]")

        console.print("\n[bold]Installing packages...[/bold]")
        venv_path = find_venv()
        results = install_packages(wheels, venv_path, use_cache=True)

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Package", style="yellow")
        table.add_column("Version", style="green")
        table.add_column("Files", justify="right")

        for pkg, stats in sorted(results.items()):
            version = locked_dict.get(pkg, "unknown")
            table.add_row(pkg, version, str(stats["files_installed"]))

        console.print(table)
        console.print(f"\n[bold green] Synced {len(results)} packages![/bold green]")
        perftester.report()

    except Exception as e:
        console.print(f"\n[bold red] Sync failed:[/bold red] {e}")
        logger.exception("Detailed error:")
        raise typer.Exit(1)


@app.command("list")
def list_packages():
    console.print("\n[bold blue]Installed packages[/bold blue]\n")
    try:
        locked_pack = load_lockfile()
        if not locked_pack:
            console.print("[yellow]No packages installed.[/yellow]")
            return
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Package", style="yellow")
        table.add_column("Version", style="green")

        for name in sorted(locked_pack.keys()):
            package = locked_pack[name]
            table.add_row(name, package.version)
        console.print(table)
        console.print(f"\n[dim]{len(locked_pack)} packages installed[/dim]")
    except Exception as e:
        console.print(f"[bold red]✗ Failed to list packages:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def remove(packages: List[str] = typer.Argument(..., help="Packages to remove"), keep_deps: bool = typer.Option(False, "--keep-deps", help="Don't remove unused dependencies"),):
    console.print(f"\n[bold blue]Removing {len(packages)} package(s)...[/bold blue]\n")

    if not venv_exists():
        console.print("[bold red]✗ No virtual environment found.[/bold red]")
        raise typer.Exit(1)

    try:
        removed_from_deps = []
        for package in packages:
            console.print(f"  • {package}")
            if remove_dependency(package):
                removed_from_deps.append(package)
            else:
                console.print(f"[yellow] {package} not in dependencies[/yellow]")

        if not removed_from_deps:
            console.print(
                "\n[yellow]No packages were removed from dependencies.[/yellow]"
            )
            return
        console.print("\n✓ [green]Updated pyproject.toml[/green]")

        all_deps = get_dependencies()
        if all_deps:
            console.print(f"\n[bold]Re-resolving dependencies...[/bold]")
            resolved = asyncio.run(build_resolution(all_deps))
            still_needed = set(resolved.keys())
        else:
            still_needed = set()

        locked_file = load_lockfile()
        current = set(locked_file.keys())
        orphans = current - still_needed - set(removed_from_deps)
        logger.debug(f"Orphaned deps : {orphans}")

        venv_path = find_venv()
        if keep_deps:
            all_to_remove = list(removed_from_deps)
        else:
            all_to_remove = list(removed_from_deps) + list(orphans)
            if orphans:
                console.print(f"\n[dim]Also removing {len(orphans)} orphaned dependencies:[/dim]")
                for orphan in sorted(orphans):
                    console.print(f"  [dim]• {orphan}[/dim]")

        for package in all_to_remove:
            if unlink_package(package, venv_path):
                console.print(f"✓ [green]Removed {package}[/green]")
            else:
                console.print(f"[yellow]Failed to uninstall {package}[/yellow]")

        if all_deps:
            update_lockfile(resolved)
        elif keep_deps and orphans:
            orphan_dict = {pkg: locked_file[pkg].version for pkg in orphans if pkg in locked_file}
            update_lockfile(orphan_dict)
        else:
            update_lockfile({})

        console.print("\n✓ [green]Updated hermes.lock[/green]")
        console.print(f"\n[bold green]✓ Successfully removed {len(all_to_remove)} packages![/bold green]")
    except Exception as e:
        console.print(f"\n[bold red]✗ Remove failed:[/bold red] {e}")
        raise typer.Exit(1)

# @app.command("audit")
# def audit_pacakges():


@cache_app.command("info")
def cache_info_cmd():
    console.print("\n[bold blue]Cache Information[/bold blue]\n")
    try:
        info = cache_info()

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="yellow")
        table.add_column("Value", style="green")

        table.add_row("Cache location", info["location"])
        table.add_row("Total size", f"{info['size_mb']:.2f} MB")
        table.add_row("Wheels cached", str(info["wheels"]))
        table.add_row("Installed packages", str(info["unpacked"]))

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to get cache info:[/bold red] {e}")
        raise typer.Exit(1)


@cache_app.command("clear")
def cache_clear_cmd(force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),):
    console.print("\n[bold yellow] This will delete all cached wheels and installed packages[/bold yellow]")

    if not force:
        confirm = typer.confirm("Are you sure you want to continue?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    try:
        clear_cache()
        console.print("\n[bold green] Cache cleared successfully![/bold green]")
    except Exception as e:
        console.print(f"[bold red] Failed to clear cache:[/bold red] {e}")
        raise typer.Exit(1)


def main():
    "Entry point"
    app()


if __name__ == "__main__":
    main()
