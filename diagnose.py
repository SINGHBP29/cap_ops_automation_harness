#!/usr/bin/env python3
import sys
import os
import asyncio
import json

# Add 'app' directory to the path so we can resolve imports
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from config import settings
from services.rca_engine import RCAEngine

# Custom Terminal Color Code support
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    banner = f"""
{Colors.BOLD}{Colors.CYAN}======================================================================
     🌐  AI SEARCH OBSERVABILITY PLATFORM - DIAGNOSTICS & RCA ENGINE  🌐
======================================================================{Colors.ENDC}
"""
    print(banner)

def get_status_badge(status: str) -> str:
    status = status.upper()
    if status in ("HEALTHY", "CONNECTED", "REACHABLE"):
        return f"{Colors.GREEN}[● ONLINE]{Colors.ENDC}"
    elif status in ("DEGRADED", "WARNING", "PORT_OPEN_PRODUCER_FAILED"):
        return f"{Colors.WARNING}[▲ DEGRADED]{Colors.ENDC}"
    elif status in ("OFFLINE", "UNREACHABLE", "CRITICAL"):
        return f"{Colors.FAIL}[■ OFFLINE]{Colors.ENDC}"
    else:
        return f"{Colors.BLUE}[? {status}]{Colors.ENDC}"

async def main():
    print_banner()
    
    use_ai = "--ai" in sys.argv
    if not use_ai:
        print(f"{Colors.CYAN}💡 Tip: Run 'python3 diagnose.py --ai' to trigger AI-assisted playbook generation!{Colors.ENDC}\n")
    else:
        print(f"{Colors.CYAN}🤖 AI Diagnostics enabled. Contacting '{settings.LLM_PROVIDER}' (model: '{settings.LLM_MODEL}')...{Colors.ENDC}\n")

    print(f"{Colors.BOLD}🔍 Initiating system-wide environment & signal diagnostics...{Colors.ENDC}\n")
    
    rca = RCAEngine()
    try:
        report = await rca.run_diagnostics(run_llm=use_ai)
    except Exception as e:
        print(f"{Colors.FAIL}❌ Failed to execute diagnostics: {e}{Colors.ENDC}")
        sys.exit(1)

    # Health Rating Header
    rating = report["health_rating"]
    color = Colors.GREEN
    if rating == "CRITICAL":
        color = Colors.FAIL
    elif rating == "DEGRADED":
        color = Colors.WARNING
    elif rating == "WARNING":
        color = Colors.WARNING

    print(f"{Colors.BOLD}System Observability Rating: {color}{rating}{Colors.ENDC}\n")
    
    # Print Service Statuses
    print(f"{Colors.BOLD}📡 --- SERVICE STATUS REGISTER ---{Colors.ENDC}")
    services = report["services"]
    for svc_name, svc_info in services.items():
        name_str = svc_name.replace("_", " ").title().ljust(20)
        status_badge = get_status_badge(svc_info["status"])
        url_or_endpoint = svc_info.get("url") or svc_info.get("endpoint") or svc_info.get("bootstrap_servers") or ""
        print(f"  • {name_str} : {status_badge}  {Colors.BLUE}{url_or_endpoint}{Colors.ENDC}")
        if svc_info.get("error"):
            print(f"    {Colors.FAIL}└ Error details: {svc_info['error']}{Colors.ENDC}")
        if svc_info.get("latency_ms"):
            print(f"    └ Response latency: {svc_info['latency_ms']:.2f} ms")
    print()

    # Signals summary
    summary = report["signals_summary"]
    print(f"{Colors.BOLD}📜 --- OBSERVABILITY SIGNAL SUMMARY ---{Colors.ENDC}")
    print(f"  • Total Anomalous Signals Logged: {Colors.BOLD}{summary['total_signals']}{Colors.ENDC}")
    if summary['total_signals'] > 0:
        print(f"  • By Signal Type:")
        for stype, count in summary["by_type"].items():
            print(f"    - {stype}: {Colors.WARNING}{count}{Colors.ENDC}")
        print(f"  • By Severity Level:")
        for sev, count in summary["by_severity"].items():
            color = Colors.FAIL if sev in ("critical", "high") else Colors.WARNING
            print(f"    - {sev}: {color}{count}{Colors.ENDC}")
    else:
        print(f"  • {Colors.GREEN}No anomalous signals currently stored in ops ledger.{Colors.ENDC}")
    print()

    # Anomalies
    anomalies = report["detected_anomalies"]
    print(f"{Colors.BOLD}⚠️  --- DETECTED ANOMALIES ({len(anomalies)}) ---{Colors.ENDC}")
    if not anomalies:
        print(f"  {Colors.GREEN}No active anomalies detected across connected channels.{Colors.ENDC}")
    else:
        for a in anomalies:
            sev_color = Colors.FAIL if a["severity"] == "CRITICAL" else Colors.WARNING
            print(f"  {sev_color}[{a['severity']}] {Colors.BOLD}{a['source']}{Colors.ENDC} ({a['type']}): {a['message']}")
    print()

    # Identified Root Cause & Action Items
    root_causes = report["identified_root_causes"]
    print(f"{Colors.BOLD}🔧 --- ROOT CAUSE ANALYSIS & RECOMMENDATIONS ({len(root_causes)}) ---{Colors.ENDC}")
    if not root_causes:
        print(f"  {Colors.GREEN}All checks passed. System is fully operational and healthy!{Colors.ENDC}")
    else:
        for idx, rc in enumerate(root_causes, 1):
            print(f"  {Colors.BOLD}{idx}. ISSUE: {rc['issue']}{Colors.ENDC}")
            print(f"     {Colors.WARNING}Root Cause:{Colors.ENDC} {rc['cause']}")
            print(f"     {Colors.GREEN}Recommended Action:{Colors.ENDC} {rc['remedy']}")
            print()

    # Render LLM RCA Explanation
    if use_ai and report.get("ai_explanation"):
        print(f"{Colors.BOLD}{Colors.CYAN}🤖 --- AI-GENERATED RCA PLAYBOOK ---{Colors.ENDC}")
        print(report["ai_explanation"])
        print()

    print(f"{Colors.BOLD}{Colors.CYAN}======================================================================{Colors.ENDC}")

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        # Windows terminal color setup
        os.system("color")
    
    asyncio.run(main())
