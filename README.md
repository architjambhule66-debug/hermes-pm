# Hermes

Fast Python package manager with uv-like optimizations

Ever thought why uv is fast, most people attribute it to being written in Rust, but there are several other optimisations that uv does, which we have tried to implement here

IMPORTANT : Hermes is currently designed as an **educational project** (Not a complete dependency manager, while i would definitely like to make it prod grade, there is a long way to go for that)


[![PyPI version](https://badge.fury.io/py/hermes-pm.svg)](https://pypi.org/project/hermes-pm/)
[![Python Versions](https://img.shields.io/pypi/pyversions/hermes-pm.svg)](https://pypi.org/project/hermes-pm/)

## UV-Inspired Features

- **PubGrub Dependency Resolution** - Advanced SAT-based resolver (same algorithm as UV)
- **Parallel Async Downloads** - HTTP/2 support with configurable concurrency limits
- **Two-Tier Global Cache** - Separate wheels and unpacked package caches
- **Zero-Copy Installations** - Reflink → hardlink → copy fallback strategy (30% disk savings on APFS)
- **Lock File Support** - Reproducible builds with `hermes.lock`
- **Fast Metadata Fetching** - PEP 658 support for direct `.metadata` access
- **Virtual Environment Management** - Lightweight venv creation without pip
- **Parallel Installation** - ThreadPoolExecutor with 4 workers for concurrent package installs
- **SHA256 Verification** - Automatic integrity checking for all downloads
- **Platform-Aware Wheel Selection** - Intelligent matching for OS, architecture, and Python version
- **Security Auditing** - Built-in vulnerability scanning via OSV database
- **Rich CLI** - Colored output, progress indicators, and performance tracking


### Installation

```bash
pip install hermes-pm
```

### Initialize a Project

```bash
# Create a new project
mkdir my-project
cd my-project

# Initialize (creates .venv, pyproject.toml, hermes.lock)
hermes init
```

### Add Packages

```bash
# Add single package
hermes add requests

# Add multiple packages
hermes add httpx rich typer

# Add with version constraints
hermes add "requests>=2.28.0"
hermes add "httpx<1.0"
```

### Sync from Lock File

```bash
# Install from hermes.lock (fast!)
hermes sync
```

### List Packages

```bash
# Show all installed packages
hermes list
```

### Remove Packages

```bash
# Remove package and unused dependencies
hermes remove requests

# Remove package but keep its dependencies
hermes remove requests --keep-deps
```

### Security Audit

```bash
# Scan all installed packages for vulnerabilities
hermes audit
```

### Manage Cache

```bash
# View cache statistics
hermes cache info

# Clear cache
hermes cache clear
```

## Performance

Comprehensive benchmarks comparing Hermes against pip and Poetry can be found in the benchmarks directory (Tier  wise separation, you can add or remove any packages you want for benchmarking):

### Warm Cache Performance (vs pip)

| Tier | Packages | Hermes Speedup | Disk Savings |
|------|----------|---------------|--------------|
| Basic Data Science | 5 | **1.78x faster** | **32.8% smaller** |
| ML Engineering | 8 | **1.26x faster** | **29.3% smaller** |
| Full ML Stack | 12 | **1.09x faster** | **30.4% smaller** |

**Key Highlights:**
- **26-78% faster** than pip for cached reinstalls
- **~30% less disk space** through reflink copies (APFS/Btrfs)
- **4-12x cache effectiveness** - dramatically faster warm cache installs
- **Parallel installation** with ThreadPoolExecutor (4 workers)

*Benchmarked on Python 3.13.7, macOS (Darwin 23.5.0), packages: numpy, pandas, matplotlib, scikit-learn, scipy, etc.*

## 📖 Commands

| Command | Description |
|---------|-------------|
| `hermes init` | Initialize a new project (venv, pyproject.toml, hermes.lock) |
| `hermes add <packages>` | Add and install packages with dependency resolution |
| `hermes list` | Show all installed packages |
| `hermes remove <packages>` | Remove packages (includes orphaned dependencies by default) |
| `hermes remove <pkg> --keep-deps` | Remove package but keep its dependencies |
| `hermes sync` | Install all packages from hermes.lock |
| `hermes audit` | Scan installed packages for security vulnerabilities (OSV) |
| `hermes cache info` | Show cache location, size, and statistics |
| `hermes cache clear` | Clear the global package cache |
| `hermes --version` / `-V` | Show Hermes version |
| `hermes --help` | Show help message |


**Inspired by:** [uv](https://github.com/astral-sh/uv) - A production-ready, blazing-fast package manager

### Testing

We have a shell file test suite that validates all core functionality

```bash
./test_core.sh
```

