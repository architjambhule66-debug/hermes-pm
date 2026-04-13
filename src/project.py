import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import tomllib
import tomli_w
from loguru import logger

PYPROJECT_PATH = Path("pyproject.toml")

def pyproject_exists() -> bool:
    return PYPROJECT_PATH.exists()

def create_empty_structure() -> Dict[str, Any]:
    cwd_name = Path.cwd().name
    return {
        "project": {
            "name": cwd_name or "my-project",
            "version": "0.1.0",
            "description": "",
            "requires-python": f">={sys.version_info.major}.{sys.version_info.minor}",
            "dependencies": [],
        }
    }

def save_pyproject(data: Dict[str, Any]) -> None:
    try:
        with PYPROJECT_PATH.open("wb") as f:
            tomli_w.dump(data, f)
        logger.debug("Saved pyproject.toml")
    except Exception as e:
        raise RuntimeError(f"Failed to write pyproject.toml: {e}")

def load_pyproject() -> Dict[str, Any]:
    if not PYPROJECT_PATH.exists():
        logger.debug("No pyproject.toml found, returning empty structure")
        return create_empty_structure()
    try:
        with PYPROJECT_PATH.open("rb") as f:
            data = tomllib.load(f)
        logger.debug(f"Loaded pyproject.toml with {len(data.get('project', {}).get('dependencies', []))} dependencies")
        return data
    except Exception as e:
        logger.error(f"Failed to parse pyproject.toml: {e}")
        raise RuntimeError(f"Invalid pyproject.toml: {e}")

def create_pyproject(name: Optional[str] = None) -> Path:
    if PYPROJECT_PATH.exists():
        logger.debug("pyproject.toml already exists")
        return PYPROJECT_PATH
    data = create_empty_structure()
    if name:
        data["project"]["name"] = name
    save_pyproject(data)
    logger.info("Created pyproject.toml")
    return PYPROJECT_PATH

def get_dependencies() -> Dict[str, str]:
    data = load_pyproject()
    deps_list = data.get("project", {}).get("dependencies", [])
    deps_dict = {}
    for dep_str in deps_list:
        if ">=" in dep_str or "<=" in dep_str or "==" in dep_str or "~=" in dep_str:
            name = (dep_str.split(">=")[0].split("<=")[0].split("==")[0].split("~=")[0].strip())
            version = dep_str.replace(name, "").strip()
        else:
            name = dep_str.strip()
            version = "*"
        deps_dict[name] = version if version else "*"

    return deps_dict

def add_dependency(package: str, version_spec: str = "*") -> None:
    data = load_pyproject()

    if "project" not in data:
        data["project"] = create_empty_structure()["project"]
    if "dependencies" not in data["project"]:
        data["project"]["dependencies"] = []

    deps_list = data["project"]["dependencies"]
    dep_str = package if version_spec == "*" else f"{package}{version_spec}"

    existing_idx = None
    for i, dep in enumerate(deps_list):
        dep_name = (dep.split(">=")[0].split("<=")[0].split("==")[0].split("~=")[0].strip())
        if dep_name == package:
            existing_idx = i
            break

    if existing_idx is not None:
        deps_list[existing_idx] = dep_str
        logger.debug(f"Updated {package} in dependencies")
    else:
        deps_list.append(dep_str)
        logger.debug(f"Added {package} to dependencies")

    save_pyproject(data)

def remove_dependency(package: str) -> bool:
    data = load_pyproject()
    if "project" not in data or "dependencies" not in data["project"]:
        return False
    deps = data["project"]["dependencies"]
    removed = False

    for i, dep in enumerate(deps):
        name = dep.split(">=")[0].split("<=")[0].split("==")[0].split("~=")[0].strip()
        if name == package:
            deps.pop(i)
            removed = True
            logger.debug(f"Removed {package} from dependencies")
            break
    
    if removed:
        save_pyproject(data)
    return removed