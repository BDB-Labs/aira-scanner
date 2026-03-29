#!/usr/bin/env python3
"""
AIRA CLI — AI-Induced Risk Audit
Command-line interface for scanning codebases.

Usage:
    aira scan <path>
    aira scan <path> --output yaml
    aira scan <path> --output json
    aira scan <path> --output report
    aira scan <path> --exclude node_modules,dist
"""

import sys
import argparse
from pathlib import Path

# Ensure package importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from aira.scanner import AIRAScanner, result_to_yaml, result_to_json

# ── Terminal colors ─────────────────────────────────────────────
class C:
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    BLUE   = "\033[94m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"
    CYAN   = "\033[96m"


SEVERITY_COLOR = {
    "HIGH":   C.RED,
    "MEDIUM": C.YELLOW,
    "LOW":    C.DIM,
}

STATUS_COLOR = {
    "PASS":    C.GREEN,
    "FAIL":    C.RED,
    "UNKNOWN": C.YELLOW,
}

BANNER = f"""
{C.BOLD}{C.BLUE}  ╔═══════════════════════════════════════╗
  ║   AIRA — AI-Induced Risk Audit v1.2   ║
  ║   Bagelle Parris Vargas Consulting    ║
  ╚═══════════════════════════════════════╝{C.RESET}
"""


def print_banner():
    print(BANNER)


def print_summary(result):
    s = result.summary
    print(f"\n{C.BOLD}{'═'*55}{C.RESET}")
    print(f"{C.BOLD}  SCAN SUMMARY{C.RESET}")
    print(f"{'═'*55}")
    print(f"  Target:          {result.target}")
    print(f"  Scanned at:      {result.scanned_at}")
    print(f"  Files scanned:   {s['files_scanned']}")
    print(f"  Total findings:  {C.BOLD}{s['findings_total']}{C.RESET}")
    print()
    print(f"  Severity breakdown:")
    print(f"    {C.RED}HIGH  : {s['by_severity']['HIGH']}{C.RESET}")
    print(f"    {C.YELLOW}MEDIUM: {s['by_severity']['MEDIUM']}{C.RESET}")
    print(f"    {C.DIM}LOW   : {s['by_severity']['LOW']}{C.RESET}")
    print()
    print(f"  Check results:")
    print(f"    {C.GREEN}PASS   : {s['checks_passed']}{C.RESET}")
    print(f"    {C.RED}FAIL   : {s['checks_failed']}{C.RESET}")
    print(f"    {C.YELLOW}UNKNOWN: {s['checks_unknown']}{C.RESET}")
    print(f"{'═'*55}\n")


def print_check_results(result):
    print(f"{C.BOLD}  CHECK RESULTS{C.RESET}")
    print(f"{'─'*55}")
    for key, status in result.check_results.items():
        color = STATUS_COLOR.get(status, C.RESET)
        label = key.replace("_", " ").upper()
        print(f"  {color}{status:8}{C.RESET}  {label}")
    print()


def print_findings(result):
    findings = result.findings
    if not findings:
        print(f"  {C.GREEN}✓ No findings. All automated checks passed.{C.RESET}\n")
        print(f"  {C.YELLOW}Note: C07 (Parallel Logic Drift) and C12 (Source-to-Output Lineage)")
        print(f"  require human review and are marked UNKNOWN.{C.RESET}\n")
        return

    print(f"{C.BOLD}  FINDINGS ({len(findings)} total){C.RESET}")
    print(f"{'─'*55}")

    current_check = None
    for f in findings:
        if f["check_id"] != current_check:
            current_check = f["check_id"]
            print(f"\n  {C.BOLD}{C.CYAN}[{f['check_id']}] {f['check_name']}{C.RESET}")

        sev_color = SEVERITY_COLOR.get(f["severity"], C.RESET)
        print(f"    {sev_color}[{f['severity']:6}]{C.RESET}  {f['file']}:{f['line']}")
        print(f"             {f['description']}")
        if f.get("snippet"):
            print(f"             {C.DIM}→ {f['snippet']}{C.RESET}")
    print()


def print_human_review_notice():
    print(f"{C.YELLOW}{'─'*55}")
    print(f"  REQUIRES HUMAN REVIEW (cannot be automated):")
    print(f"    C07 — Parallel Logic Drift")
    print(f"         Check: Does batch/streaming/sync/async share identical governance?")
    print(f"    C12 — Source-to-Output Lineage")
    print(f"         Check: Do all derived objects carry source + location metadata?")
    print(f"{'─'*55}{C.RESET}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="aira",
        description="AIRA — AI-Induced Risk Audit scanner"
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan a file or directory")
    scan_parser.add_argument("target", help="File or directory to scan")
    scan_parser.add_argument(
        "--output", "-o",
        choices=["terminal", "yaml", "json"],
        default="terminal",
        help="Output format (default: terminal)"
    )
    scan_parser.add_argument(
        "--exclude", "-e",
        help="Comma-separated list of directories to exclude",
        default=""
    )
    scan_parser.add_argument(
        "--out-file", "-f",
        help="Write output to file instead of stdout",
        default=None
    )

    args = parser.parse_args()

    if args.command == "scan":
        target = args.target
        if not Path(target).exists():
            print(f"{C.RED}Error: Path not found: {target}{C.RESET}", file=sys.stderr)
            sys.exit(1)

        exclude = [d.strip() for d in args.exclude.split(",") if d.strip()]

        print_banner()
        print(f"  Scanning: {C.BOLD}{target}{C.RESET}")
        print(f"  {'─'*50}")

        scanner = AIRAScanner(target, exclude_dirs=exclude)
        result = scanner.scan()

        if args.output == "terminal":
            print_summary(result)
            print_check_results(result)
            print_findings(result)
            print_human_review_notice()

            # Exit code: 1 if any HIGH findings, 0 otherwise
            high_count = result.summary["by_severity"]["HIGH"]
            if high_count > 0:
                print(f"{C.RED}  ✗ Scan complete — {high_count} HIGH severity finding(s) require attention.{C.RESET}\n")
                sys.exit(1)
            else:
                print(f"{C.GREEN}  ✓ Scan complete — no HIGH severity findings.{C.RESET}\n")
                sys.exit(0)

        elif args.output == "yaml":
            output = result_to_yaml(result)
        elif args.output == "json":
            output = result_to_json(result)

        if args.output in ("yaml", "json"):
            if args.out_file:
                Path(args.out_file).write_text(output)
                print(f"  {C.GREEN}Output written to: {args.out_file}{C.RESET}\n")
            else:
                print(output)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
