#!/usr/bin/env python3
"""
All-councils proxy-free scrape test — the home-server / proxy-weaning rehearsal.

Scrapes every enabled council with NO proxy (bypass_proxy forced, rotating
proxy stripped), using the current working-tree scraper code. Run it from a
residential IP to rehearse the post-proxy world (home IP ≈ home-server).

Failures get a rescue pass:
  - councils not using curl_cffi  -> retry with use_curl + chrome124
  - councils already on curl_cffi -> retry with impersonate=safari15_5

Output: JSON results + a per-state summary + concrete config recommendations
("add use_curl", "change impersonate", "needs proxy or deeper fix").

Usage:
    python3 scripts/analysis/test_all_councils_noproxy.py
    python3 scripts/analysis/test_all_councils_noproxy.py --state wa --concurrency 6
    python3 scripts/analysis/test_all_councils_noproxy.py --out results.json
"""
import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.scrapers.factory import ScraperFactory  # noqa: E402
from core.exceptions import ScrapeError  # noqa: E402
from core.validator import is_valid_article  # noqa: E402

STATES = ['nsw', 'vic', 'qld', 'wa', 'sa', 'tas', 'nt', 'act']


def load_councils(only_state=None):
    councils = []
    for st in STATES:
        if only_state and st != only_state:
            continue
        data = json.loads((ROOT / f'states/{st}/councils.json').read_text())
        for c in data['councils']:
            if c.get('enabled'):
                c = dict(c)
                c['_state'] = st
                councils.append(c)
    return councils


def scrape_once(council, override=None):
    """Scrape one council with no proxy. Returns a result dict."""
    cfg = dict(council)
    cfg.pop('use_rotating_proxy', None)  # this test is proxy-free by design
    cfg['bypass_proxy'] = True
    if override:
        cfg.update(override)

    t0 = time.monotonic()
    result = {
        'id': cfg['id'], 'state': cfg['_state'], 'scraper': cfg.get('scraper', 'card_scraper'),
        'use_curl': bool(cfg.get('use_curl') or cfg.get('scraper') == 'curl_scraper'),
        'override': override or None,
    }
    try:
        scraper = ScraperFactory.create_scraper(cfg, proxy=None)
        articles = scraper.scrape()
        valid = [a for a in articles if is_valid_article(a)]
        result.update({
            'status': 'ok' if valid else ('junk' if articles else 'empty'),
            'found': len(articles),
            'valid': len(valid),
            'dateless': sum(1 for a in valid if a.date is None),
        })
    except ScrapeError as e:
        result.update({'status': 'fetch_failed', 'error': str(e)[:200]})
    except Exception as e:  # noqa: BLE001 — harness must survive anything
        result.update({'status': 'exception', 'error': f'{type(e).__name__}: {e}'[:200]})
    result['seconds'] = round(time.monotonic() - t0, 1)
    return result


def rescue_override(result):
    """Pick the rescue variant for a failed council, or None."""
    if result['status'] not in ('fetch_failed', 'empty', 'exception'):
        return None
    if result['scraper'] == 'browser_scraper':
        return None  # already the heavy option; nothing cheap to try
    if not result['use_curl']:
        return {'use_curl': True, 'impersonate': 'chrome124'}
    return {'impersonate': 'safari15_5'}


def run_pool(councils, concurrency, override_map=None):
    results = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(scrape_once, c, (override_map or {}).get(c['id'])): c
            for c in councils
        }
        for fut in concurrent.futures.as_completed(futures):
            r = fut.result()
            results.append(r)
            done += 1
            flag = '' if r['status'] == 'ok' else f"  <-- {r['status']}: {r.get('error', '')[:80]}"
            print(f"[{done}/{len(futures)}] {r['state']}/{r['id']}: {r['status']}"
                  f" ({r.get('valid', 0)} valid, {r['seconds']}s){flag}", flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', help='limit to one state')
    ap.add_argument('--concurrency', type=int, default=10)
    ap.add_argument('--out', default=None, help='JSON output path')
    ap.add_argument('--no-rescue', action='store_true', help='skip the rescue pass')
    args = ap.parse_args()

    councils = load_councils(args.state)
    by_id = {c['id']: c for c in councils}
    print(f"Testing {len(councils)} enabled councils, NO PROXY, concurrency {args.concurrency}", flush=True)

    t0 = time.monotonic()
    results = run_pool(councils, args.concurrency)

    # Rescue pass for failures
    rescues = {}
    if not args.no_rescue:
        to_rescue = {}
        for r in results:
            ov = rescue_override(r)
            if ov:
                to_rescue[r['id']] = ov
        if to_rescue:
            print(f"\n=== RESCUE PASS: {len(to_rescue)} councils ===", flush=True)
            rescue_results = run_pool([by_id[i] for i in to_rescue], args.concurrency, to_rescue)
            rescues = {r['id']: r for r in rescue_results}

    # Merge: attach rescue outcome to the primary result
    for r in results:
        rr = rescues.get(r['id'])
        if rr:
            r['rescue'] = {'override': rr['override'], 'status': rr['status'], 'valid': rr.get('valid', 0)}

    total_s = time.monotonic() - t0

    # Summary
    print(f"\n{'=' * 70}\nSUMMARY ({len(results)} councils, {total_s / 60:.1f} min)\n{'=' * 70}", flush=True)
    statuses = {}
    for r in results:
        statuses.setdefault(r['status'], []).append(r)
    for status in ('ok', 'empty', 'junk', 'fetch_failed', 'exception'):
        rs = statuses.get(status, [])
        print(f"  {status:13s}: {len(rs)}")

    print("\nPer-state:")
    for st in STATES:
        rs = [r for r in results if r['state'] == st]
        if not rs:
            continue
        ok = sum(1 for r in rs if r['status'] == 'ok')
        print(f"  {st.upper():4s}: {ok}/{len(rs)} ok")

    rescued = [r for r in results if r.get('rescue', {}).get('status') == 'ok']
    dead = [r for r in results if r['status'] != 'ok' and r.get('rescue', {}).get('status') != 'ok']
    print(f"\nRECOMMENDATIONS")
    if rescued:
        print(f"  {len(rescued)} councils fixed by a config change (apply to councils.json):")
        for r in sorted(rescued, key=lambda x: (x['state'], x['id'])):
            print(f"    {r['state']}/{r['id']}: add {json.dumps(r['rescue']['override'])}"
                  f" ({r['rescue']['valid']} valid articles)")
    if dead:
        print(f"  {len(dead)} councils still failing without proxy (investigate individually):")
        for r in sorted(dead, key=lambda x: (x['state'], x['id'])):
            print(f"    {r['state']}/{r['id']} [{r['scraper']}] {r['status']}: {r.get('error', '')[:100]}")

    out = args.out or str(ROOT / 'noproxy_test_results.json')
    Path(out).write_text(json.dumps(sorted(results, key=lambda r: (r['state'], r['id'])), indent=1))
    print(f"\nFull results: {out}", flush=True)


if __name__ == '__main__':
    main()
