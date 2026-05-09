import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from utils import BenchmarkResult, load_results, format_size, format_time


def generate_report(results: List[BenchmarkResult], output_file: Path) -> None:
    results_by_tier: Dict[str, Dict[str, BenchmarkResult]] = {}
    for result in results:
        if result.tier not in results_by_tier:
            results_by_tier[result.tier] = {}
        results_by_tier[result.tier][result.tool] = result

    lines = []
    lines.append("# Hermes Benchmarking Results")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    if results:
        first = results[0]
        lines.append("## System Information")
        lines.append("")
        lines.append(f"- **Python:** {first.python_version}")
        lines.append(f"- **OS:** {first.os_platform}")
        lines.append("")

    lines.append("## Executive Summary")
    lines.append("")

    all_speedups = []
    all_disk_savings = []

    for tier_name, tier_results in sorted(results_by_tier.items()):
        if "pip" in tier_results and "hermes" in tier_results:
            pip_res = tier_results["pip"]
            hermes_res = tier_results["hermes"]

            cold_speedup = (
                pip_res.cold_time / hermes_res.cold_time
                if hermes_res.cold_time > 0
                else 0
            )
            warm_speedup = (
                pip_res.warm_time / hermes_res.warm_time
                if hermes_res.warm_time > 0
                else 0
            )

            all_speedups.append(cold_speedup)
            all_speedups.append(warm_speedup)

            pip_total = pip_res.venv_size + pip_res.cache_size
            hermes_total = hermes_res.venv_size + hermes_res.cache_size
            disk_savings = (
                (pip_total - hermes_total) / pip_total * 100 if pip_total > 0 else 0
            )
            all_disk_savings.append(disk_savings)

    if all_speedups:
        avg_speedup = sum(all_speedups) / len(all_speedups)
        lines.append(f"- **Average speedup vs pip:** {avg_speedup:.2f}x")

    if all_disk_savings:
        avg_disk_savings = sum(all_disk_savings) / len(all_disk_savings)
        lines.append(f"- **Average disk savings:** {avg_disk_savings:.1f}%")

    lines.append(f"- **Tiers tested:** {len(results_by_tier)}")
    lines.append(f"- **Tools compared:** {len(set(r.tool for r in results))}")
    lines.append("")

    for tier_name in sorted(results_by_tier.keys()):
        tier_results = results_by_tier[tier_name]

        lines.append(f"## {tier_name.replace('_', ' ').title()}")
        lines.append("")

        baseline = tier_results.get("pip")
        if not baseline:
            lines.append("*No baseline (pip) results available*")
            lines.append("")
            continue

        lines.append("### Installation Time")
        lines.append("")
        lines.append("| Tool | Cold Cache | Warm Cache | Cold Speedup | Warm Speedup |")
        lines.append("|------|-----------|-----------|--------------|--------------|")

        for tool_name in ["pip", "hermes", "poetry"]:
            if tool_name not in tier_results:
                continue

            res = tier_results[tool_name]

            if res.tool == "pip":
                cold_speedup = "1.00x (baseline)"
                warm_speedup = "1.00x (baseline)"
            else:
                cold_sp = baseline.cold_time / res.cold_time if res.cold_time > 0 else 0
                warm_sp = baseline.warm_time / res.warm_time if res.warm_time > 0 else 0

                cold_speedup = (
                    f"**{cold_sp:.2f}x**" if cold_sp > 1.1 else f"{cold_sp:.2f}x"
                )
                warm_speedup = (
                    f"**{warm_sp:.2f}x**" if warm_sp > 1.1 else f"{warm_sp:.2f}x"
                )

            lines.append(
                f"| {res.tool} | {format_time(res.cold_time)} | "
                f"{format_time(res.warm_time)} | {cold_speedup} | {warm_speedup} |"
            )

        lines.append("")

        lines.append("### Disk Usage")
        lines.append("")
        lines.append("| Tool | Venv Size | Cache Size | Total | vs Pip |")
        lines.append("|------|-----------|------------|-------|--------|")

        for tool_name in ["pip", "hermes", "poetry"]:
            if tool_name not in tier_results:
                continue

            res = tier_results[tool_name]
            total = res.venv_size + res.cache_size

            if res.tool == "pip":
                comparison = "baseline"
            else:
                baseline_total = baseline.venv_size + baseline.cache_size
                diff_pct = (
                    (total - baseline_total) / baseline_total * 100
                    if baseline_total > 0
                    else 0
                )

                if diff_pct < -5:
                    comparison = f"**{diff_pct:.1f}%** (smaller)"
                elif diff_pct > 5:
                    comparison = f"+{diff_pct:.1f}% (larger)"
                else:
                    comparison = f"{diff_pct:.1f}%"

            lines.append(
                f"| {res.tool} | {format_size(res.venv_size)} | "
                f"{format_size(res.cache_size)} | {format_size(total)} | {comparison} |"
            )

        lines.append("")

        lines.append("### Package Count")
        lines.append("")
        for tool_name in ["pip", "hermes", "poetry"]:
            if tool_name not in tier_results:
                continue
            res = tier_results[tool_name]
            lines.append(f"- **{res.tool}:** {res.package_count} packages")

        lines.append("")

    # Interpretation guide
    lines.append("## Interpretation Guide")
    lines.append("")
    lines.append("### Speedup")
    lines.append("")
    lines.append("- **>1.5x**: Significantly faster")
    lines.append("- **1.1x-1.5x**: Moderately faster")
    lines.append("- **0.9x-1.1x**: Roughly equivalent")
    lines.append("- **<0.9x**: Slower")
    lines.append("")
    lines.append("### Disk Usage")
    lines.append("")
    lines.append("- **Negative %**: Uses less disk space (better)")
    lines.append("- **Positive %**: Uses more disk space")
    lines.append("")
    lines.append("### Cold vs Warm Cache")
    lines.append("")
    lines.append("- **Cold cache**: First install, packages downloaded from PyPI")
    lines.append("- **Warm cache**: Reinstall using cached packages")
    lines.append(
        "- Warm cache tests measure installation efficiency without network overhead"
    )
    lines.append("")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    print(f"Report generated: {output_file}")


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    benchmarks_dir = script_dir.parent
    results_dir = benchmarks_dir / "results" / "raw"
    output_file = benchmarks_dir / "results" / "report.md"

    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        print("Run benchmarks first!")
        sys.exit(1)

    print("Loading benchmark results...")
    results = load_results(results_dir)

    if not results:
        print("Error: No results found!")
        print(f"Expected JSON files in: {results_dir}")
        sys.exit(1)

    print(f"Found {len(results)} result(s)")
    for result in results:
        print(f"  - {result.tool} / {result.tier}")

    print("\nGenerating comparison report...")
    generate_report(results, output_file)

    print("\nDone!")


if __name__ == "__main__":
    main()
