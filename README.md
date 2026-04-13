# Hermes

Fast Python package manager with uv-like optimizations

Ever thought why uv is fast, most people attribute it to being written in Rust, but there are several other optimisations that uv does, which we have tried to implement here

[![PyPI version](https://badge.fury.io/py/hermes-pm.svg)](https://badge.fury.io/py/hermes-pm)
[![Python Versions](https://img.shields.io/pypi/pyversions/hermes-pm.svg)](https://pypi.org/project/hermes-pm/)


### Installation

```bash
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    hermes-pm
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

Hermes is designed as an **educational project** (Not a complete dependency manager)

**Inspired by:** [uv](https://github.com/astral-sh/uv) - A production-ready, blazing-fast package manager

### Testing

We have a shell file test suite that validates all core functionality

```bash
./test_core.sh
```

