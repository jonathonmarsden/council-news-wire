#!/usr/bin/env python3
"""
WAF Bypass Research Tool.

This script tests various `curl_cffi` impersonations and proxy settings against a target URL
to find a working combination that bypasses Cloudflare/WAF.

Usage:
    python3 scripts/debug/research_waf_bypass.py --url https://www.cityofadelaide.com.au/news
"""

import argparse
import os
import sys
import time
from typing import Optional

try:
    from curl_cffi import requests
except ImportError:
    print("Error: curl_cffi not installed. Run 'pip install curl_cffi'")
    sys.exit(1)

# Load environment for PROXY_URL
from dotenv import load_dotenv
load_dotenv()

PROXY_URL = os.getenv("COUNCIL_BOT_PROXY") or os.getenv("PROXY_URL_ROTATING") or os.getenv("PROXY_URL")

IMPERSONATIONS = [
    "chrome110",
    "chrome120",
    "chrome124",
    "safari15_3",
    "safari15_5",
    "safari17_0",
    "edge101",
    "edge120"
]

def check_bypass(url: str, impersonate: str, use_proxy: bool) -> bool:
    proxies = {"http": PROXY_URL, "https": PROXY_URL} if use_proxy and PROXY_URL else None
    proxy_status = "PROXY" if use_proxy else "DIRECT"
    
    print(f"Testing {impersonate:<12} | {proxy_status:<6} ... ", end="", flush=True)
    
    try:
        response = requests.get(
            url,
            impersonate=impersonate,
            proxies=proxies,
            timeout=15,
            allow_redirects=True
        )
        
        # Cloudflare often returns 200 even when blocked
        content = response.text.lower()
        is_blocked = False
        
        if response.status_code == 403:
            is_blocked = True
        elif "error code:" in content and ("cloudflare" in content or "access denied" in content):
            is_blocked = True
        elif "just a moment..." in content:
            is_blocked = True
        elif "verifying you are human" in content:
            is_blocked = True
            
        if is_blocked:
            print(f"❌ Blocked (Status: {response.status_code}, Length: {len(content)})")
            return False
            
        print(f"✅ SUCCESS! (Status: {response.status_code}, Length: {len(content)})")
        return True

    except Exception as e:
        print(f"⚠️  Error: {str(e).split('(')[0]}")
        return False

def main():
    parser = argparse.ArgumentParser(description="WAF Bypass Research Tool")
    parser.add_argument("--url", default="https://www.cityofadelaide.com.au/news", help="Target URL")
    args = parser.parse_args()

    print(f"🔍 Researching WAF Bypass for: {args.url}")
    print(f"🌍 Proxy Configured: {'Yes' if PROXY_URL else 'No'}")
    print("-" * 60)

    success_found = False

    # 1. Test Direct Connection (No Proxy)
    print("\n--- Phase 1: Direct Connection (Local IP) ---")
    for imp in IMPERSONATIONS:
        if check_bypass(args.url, imp, use_proxy=False):
            success_found = True
        time.sleep(1)

    # 2. Test Proxy Connection
    if PROXY_URL:
        print("\n--- Phase 2: Rotating Proxy ---")
        for imp in IMPERSONATIONS:
            if check_bypass(args.url, imp, use_proxy=True):
                success_found = True
            time.sleep(1)
    else:
        print("\nSkipping Phase 2 (No PROXY_URL found in .env)")

    print("-" * 60)
    if success_found:
        print("🎉 Working configuration found! Update councils.json with the successful settings.")
    else:
        print("❌ No working configuration found. Try adding headers or waiting.")

if __name__ == "__main__":
    main()
