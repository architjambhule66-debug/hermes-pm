import asyncio
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from loguru import logger
from pubgrub_py import Resolver, ResolutionError
from src.network import fetch_multi
from typing import List, Dict, Any, Optional
import re

MAX_DEPTH = 5

def _normalize_version(version: str) -> str:
    version = version.strip()
    ver_parts = version.split(".")
    if len(ver_parts) > 3:
        return version
    while len(ver_parts) < 3:
        ver_parts.append("0")
    return ".".join(ver_parts)

def _normalize_constraint(constraint: str) -> str:
    parts = []
    for clause in constraint.split(","):
        clause = clause.strip()
        match = re.match(r"^([<>=!~]+)(.+)$", clause)
        if not match:
            parts.append(clause)
            continue
        op, ver = match.groups()
        normalized_ver = _normalize_version(ver)
        parts.append(f"{op}{normalized_ver}")
    return ",".join(parts)

def _parse_requires(requires_dict: List[str], extras: frozenset = frozenset()) -> Dict[str, str]:
    deps = {}
    for req_str in requires_dict:
        try:
            req = Requirement(req_str)
        except Exception:
            continue

        if not req.name or not req.name.replace("-", "").isalnum():
            continue

        if req.marker:
            env = {"extra": next(iter(extras), "")}
            try:
                if not req.marker.evaluate(env):
                    continue
            except Exception:
                continue

        name = canonicalize_name(req.name)
        spec = str(req.specifier) if req.specifier else ">=0.0.0"
        deps[name] = spec

    return deps

async def _fetch_dependency_tree(root_pkgs: List[str], max_depth: int = MAX_DEPTH) -> Dict[str, Dict[str, Dict[str, str]]]:
    package_versions: Dict[str, Dict[str, Dict]] = {}
    constraints_map: Dict[str, List[str]] = {}
    visited = set()
    queue = []

    for p in root_pkgs:
        canon = canonicalize_name(p)
        constraints_map[canon] = [">=0.0.0"]
        queue.append((canon, 0))
        visited.add((canon, 0))

    while queue:
        wave = []
        wave_pkgs = set()

        for pkg, depth in queue:
            if pkg not in wave_pkgs:
                wave.append((pkg, depth))
                wave_pkgs.add(pkg)

        queue.clear()

        if not wave:
            break

        to_fetch = [pkg for pkg, _ in wave]
        #logger.info(f"Fetching {len(to_fetch)} packages")
        w_results = await fetch_multi(to_fetch, limit=50)

        for pkg, parent_depth in wave:
            pkg_data = w_results.get(pkg, {})

            if pkg not in package_versions:
                package_versions[pkg] = {}

            merged_constraint = ",".join(constraints_map.get(pkg, [">=0.0.0"]))
            #logger.debug(f"{pkg} → merged constraint: {merged_constraint}")

            for version, raw_reqs in pkg_data.items():
                parsed_deps = _parse_requires(raw_reqs)
                package_versions[pkg][version] = parsed_deps

                if parent_depth < max_depth:
                    for dep, dep_constraint in parsed_deps.items():
                        canon_dep = canonicalize_name(dep)
                        constraints_map.setdefault(canon_dep, []).append(dep_constraint)

                        if (canon_dep, parent_depth + 1) not in visited:
                            queue.append((canon_dep, parent_depth + 1))
                            visited.add((canon_dep, parent_depth + 1))

    return package_versions

async def build_resolution(deps: Dict[str, str]) -> Dict[str, str]:
    canon_deps = {canonicalize_name(k): v for k, v in deps.items()}
    logger.info(f"Dependency resolution in progress (max depth={MAX_DEPTH})...")
    package_versions = await _fetch_dependency_tree(list(canon_deps.keys()))

    resolver = Resolver()
    skipped = 0
    pkg_version_counts = {}

    for pkg_name, versions in package_versions.items():
        pkg_version_counts[pkg_name] = 0
        for version_str, sub_deps in versions.items():
            try:
                normalized_version = _normalize_version(version_str)
                normalized_deps = {
                    dep: _normalize_constraint(constraint)
                    for dep, constraint in sub_deps.items()
                }
                resolver.add_package(pkg_name, normalized_version, normalized_deps)
                pkg_version_counts[pkg_name] += 1
            except Exception as e:
                skipped += 1
                continue

    if skipped:
        logger.warning(
            f"Skipped {skipped} malformed version entries during registration."
        )

    for req_pkg in canon_deps.keys():
        count = pkg_version_counts.get(req_pkg, 0)
        if count == 0:
            raise RuntimeError(
                f"No valid versions found for required package '{req_pkg}'. "
            )

    requirements = {}
    for pkg, ver in canon_deps.items():
        if ver == "latest":
            requirements[pkg] = ">=0.0.0"
        elif any(op in ver for op in "<>=!~"):
            requirements[pkg] = ver
        else:
            requirements[pkg] = f"=={ver}"

    logger.info(f"Running PubGrub solver over {len(package_versions)} packages...")
    for pkg_name, count in pkg_version_counts.items():
        logger.debug(f"  {pkg_name}: {count} versions registered")
    #logger.info(f"Total versions registered: {sum(pkg_version_counts.values())}")
    try:
        result = resolver.resolve(requirements)
        return result
    except ResolutionError as e:
        raise RuntimeError(f"Dependency resolution failed:{e}")

