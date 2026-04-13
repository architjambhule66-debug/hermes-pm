from struct import pack
from sys import version
import httpx
import asyncio
from typing import Dict, List, Any
from email.parser import Parser
from packaging.version import parse as parse_version
from packaging.version import Version
from packaging.utils import canonicalize_name, parse_wheel_filename
from dataclasses import dataclass
from loguru import logger
from pathlib import Path
from src.utils import get_platform, select_best_wheel, verify_hash, WheelInfo, get_tags
from src.perf import perftester

MAX_VERSIONS = 30

async def fetch_meta(client : httpx.AsyncClient, url:str) -> List[str]:
    try:
        response = await client.get(url, timeout=5.0)
        response.raise_for_status()
        msg = Parser().parsestr(response.text)
        return msg.get_all("Requires-Dist") or []
    except Exception as e:
        logger.debug(f"Failed to fetch metadata from {url}: {e}")
        return []

async def fetch_versions(client : httpx.AsyncClient, pkg_name : str, sema : asyncio.Semaphore) -> Dict[str, Any]:
    async with sema:
        try:
            url = f"https://pypi.org/simple/{pkg_name}/"
            headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Package '{pkg_name}' not found on PyPI")
                return {pkg_name: {}}
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error for {pkg_name}: {e}")
            raise

        metadata_urls = {}

        for file_info in data.get("files", []):
            filename = file_info["filename"]
            if not filename.endswith(".whl"):
                continue

            if file_info.get("core-metadata"):
                try:
                    _, version, _, _ = parse_wheel_filename(filename)
                    version_str = str(version)
                    if version_str not in metadata_urls:
                        metadata_urls[version_str] = file_info["url"] + ".metadata"
                except Exception:
                    continue

        # 30, so pypi doesnt rate limit us 
        recent_versions = sorted(metadata_urls.keys(), key=parse_version, reverse=True)[:MAX_VERSIONS]
        filtered_urls = {v: metadata_urls[v] for v in recent_versions}

        tasks = [fetch_meta(client, url) for url in filtered_urls.values()]
        meta_results = await asyncio.gather(*tasks, return_exceptions=True)

        version_deps = {}
        for version, reqs in zip(filtered_urls.keys(), meta_results):
            if not isinstance(reqs, Exception):
                version_deps[version] = reqs
            else:
                version_deps[version] = []

        return {
            pkg_name : version_deps
        }

async def fetch_multi(pkg_names : List[str], limit: int = 50) -> Dict[str, Dict[str, List[str]]]:
    sema = asyncio.Semaphore(limit)
    async with httpx.AsyncClient(http2=True) as client:
        tasks = [fetch_versions(client, pkg, sema) for pkg in pkg_names]
        results = await asyncio.gather(*tasks)
        merged = {}
        for result in results:
            merged.update(result)
        return merged

async def fetch_whl(client: httpx.AsyncClient, package: str, version: str)-> List[WheelInfo]:
    url = f"https://pypi.org/simple/{package}/"
    headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
    target_version = Version(version)
    try:
        response = await client.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.error(f"Package '{package}' not found on PyPI")
            return []
        raise
    except httpx.RequestError as e:
        logger.error(f"Network error fetching {package}: {e}")
        raise

    wheels = []
    for file_info in data.get("files", []):
        filename = file_info["filename"]
        if not filename.endswith(".whl"):
            continue

        try:
            p_name, p_version, p_tag, p_tags = parse_wheel_filename(filename)
            if str(p_version) == version or p_version == Version(version):
                wheels.append(
                    WheelInfo(
                        url=file_info["url"],
                        filename=filename,
                        hash=file_info["hashes"]["sha256"],
                        size=file_info.get("size", 0),
                    )
                )
        except Exception as e:
            logger.debug(f"Skipped malformed wheel filename: {filename} ({e})")
            continue

    return wheels

async def download_whl(client: httpx.AsyncClient, wheel: WheelInfo, dest: Path, sema: asyncio.Semaphore) -> Path:
    async with sema:
        dest_p = dest / wheel.filename
        if dest_p.exists():
            if verify_hash(dest_p, wheel.hash):
                logger.debug(f"Using cached download: {wheel.filename}")
                return dest_p
            else:
                logger.warning(f"Hash mismatch for cached file downloading again: {wheel.filename}")
                dest_p.unlink()

        size_mb = wheel.size / 1024 / 1024
        logger.info(f"Downloading {wheel.filename} ({size_mb:.2f} MB)")
        try:
            response = await client.get(wheel.url, timeout=60.0)
            response.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"Failed to download {wheel.filename}: {e}")
            raise

        dest_p.write_bytes(response.content)
        if not verify_hash(dest_p, wheel.hash):
            dest_p.unlink()
            raise RuntimeError(f"Hash verification failed: {wheel.filename}")
        logger.info(f"Downloaded {wheel.filename}")
        return dest_p

async def download_multi_whls(packages: Dict[str, str], dest_dir: Path, max_c: int = 10,) -> Dict[str, Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    sema = asyncio.Semaphore(max_c)

    async with httpx.AsyncClient(http2=True, timeout=60.0) as client:
        platform = get_platform()
        c_tags = get_tags()
        logger.info(f"Platform: {platform}")

        logger.info(f"Fetching wheel info for {len(packages)} packages")
        fetch_tasks = []
        package_list = []

        for package, version in packages.items():
            c_name = canonicalize_name(package)
            fetch_tasks.append(fetch_whl(client, c_name, version))
            package_list.append(package)

        wheels_info = await asyncio.gather(*fetch_tasks)
        selected_wheels = {}
        for package, available_wheels in zip(package_list, wheels_info):
            if not available_wheels:
                raise RuntimeError(f"No wheels found for :{package}")
            best_wheel = select_best_wheel(available_wheels, c_tags)
            if best_wheel is None:
                raise RuntimeError(f"No compatible wheel for {package}")
            selected_wheels[package] = best_wheel
            logger.debug(f"{package}: selected {best_wheel.filename}")

        download_tasks = [download_whl(client, wheel, dest_dir, sema)for wheel in selected_wheels.values()]
        download_paths = await asyncio.gather(*download_tasks)
        return {package: path for package, path in zip(package_list, download_paths)}

async def fetch_and_download(dependencies: Dict[str, str],download_dir: Path,) -> Dict[str, Path]:
    with perftester.track("platform_detect"):
        platform = get_platform()
        tags = get_tags()
        logger.info(f"Platform: {platform}")
        logger.debug(f"Compatible tags: {len(tags)} total")

    with perftester.track("wheels_download"):
        wheels = await download_multi_whls(dependencies, download_dir)

    logger.info(f"Downloaded {len(wheels)} wheels")
    return wheels

# if __name__ == "__main__":
#     import asyncio
#     from pathlib import Path

#     async def main():
#         deps = {
#             "requests": "2.31.0",
#             "urllib3": "2.2.1",
#             "idna": "3.7",
#         }
#         download_dir = Path("./downloads")
#         results = await fetch_and_download(deps, download_dir)

#         print("\n✅ Final Results:")
#         for pkg, path in results.items():
#             print(f"{pkg} -> {path}")

#     asyncio.run(main())




