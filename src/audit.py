import httpx
from typing import List, Dict
from loguru import logger
from src.lockfile import load_lockfile

async def check_vulnerabilities(package: str, version: str) -> List[Dict]:
    try:
        url = "https://api.osv.dev/v1/query"
        payload = {
            "package": {
                "name": package,
                "ecosystem": "PyPI"
            },
            "version": version
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            data = response.json()
            return data.get("vulns", [])
    except Exception as e:
        logger.error(f"Error during getting CVE Data from OSV : {e}")
        raise

async def scan_all() -> Dict[str, List]:
    lockfile = load_lockfile()
    results = {}

    for package_name, package_info in lockfile.items():
        vulns = await check_vulnerabilities(
            package_name,
            package_info.version
        )
        if vulns:
            results[package_name] = vulns

    return results

async def main():
    out = await check_vulnerabilities(package="litellm", version="1.82.7")
    print(out)

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())