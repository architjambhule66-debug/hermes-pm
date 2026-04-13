import asyncio
import httpx
from typing import List, Dict, Tuple
from loguru import logger
from src.lockfile import load_lockfile


async def check_vulnerabilities(package: str, version: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> Tuple[str, List[Dict]]:
    async with semaphore:
        try:
            url = "https://api.osv.dev/v1/query"
            payload = {"package": {"name": package, "ecosystem": "PyPI"},"version": version,}
            response = await client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            vulns = data.get("vulns", [])
            return (package, vulns)
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error checking {package}: {e}")
            return (package, [])
        except Exception as e:
            logger.error(f"Error checking {package}: {e}")
            return (package, [])

async def scan_all(max_concurrent: int = 10) -> Dict[str, List]:
    lockfile = load_lockfile()
    if not lockfile:
        logger.debug("Lockfile is empty, please install a package to use this command")
        return {}

    logger.info(f"Scanning {len(lockfile)} packages for vulnerabilities...")
    semaphore = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient() as client:
        tasks = [check_vulnerabilities(package_name, package_info.version, client, semaphore)for package_name, package_info in lockfile.items()]
        results_list = await asyncio.gather(*tasks)
    results = {package: vulns for package, vulns in results_list if vulns}
    logger.info(f"Scan complete: {len(results)} packages with vulnerabilities")
    return results


# async def main():
#     async with httpx.AsyncClient() as client:
#         semaphore = asyncio.Semaphore(5)
#         package, vulns = await check_vulnerabilities(
#             "litellm", "1.82.7", client, semaphore
#         )
#         print(f"{package}: {len(vulns)} vulnerabilities found")

#     print("\nScanning all packages from lockfile...")
#     results = await scan_all()
#     print(f"Found vulnerabilities in {len(results)} packages")
#     for pkg, vulns in results.items():
#         print(f"  {pkg}: {len(vulns)} vulnerabilities")


# if __name__ == "__main__":
#     asyncio.run(main())
