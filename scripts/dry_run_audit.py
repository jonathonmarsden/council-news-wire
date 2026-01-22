import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from core.poster import BlueSkyPoster

load_dotenv()

# Admin credentials to fetch bookmarks
ADMIN_HANDLE = os.getenv("BLUESKY_HANDLE_ADMIN")
ADMIN_PASS = os.getenv("BLUESKY_PASSWORD_ADMIN")

def get_admin_jwt():
    from atproto import Client
    client = Client()
    client.login(ADMIN_HANDLE, ADMIN_PASS)
    return client._session.access_jwt

def fetch_bookmarks(jwt):
    import requests
    endpoint = "https://bsky.social/xrpc/app.bsky.bookmark.getBookmarks"
    headers = {"Authorization": f"Bearer {jwt}"}
    resp = requests.get(endpoint, headers=headers)
    resp.raise_for_status()
    return resp.json().get('bookmarks', [])

def load_domain_map():
    with open('scripts/council_domain_map.json', 'r') as f:
        return json.load(f)

def get_council_name_from_url(url, domain_map):
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Exact match
        if domain in domain_map:
            return domain_map[domain]
            
        # Suffix match (safety for subdomains)
        for dom, name in domain_map.items():
            if domain.endswith("." + dom) or domain == dom:
                return name
                
        return "Unknown Council"
    except:
        return "Unknown Council"

def main():
    print("Generating Dry Run Audit Report (SAFE MODE)...")
    jwt = get_admin_jwt()
    bookmarks = fetch_bookmarks(jwt)
    domain_map = load_domain_map()
    
    report_lines = []
    report_lines.append(f"AUDIT DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"TOTAL BOOKMARKS: {len(bookmarks)}")
    report_lines.append("="*60 + "\n")
    
    # We need a dummy poster to use its formatting logic
    # We can init it with dummy credentials as we won't actually post
    poster = BlueSkyPoster("dummy.bsky.social", "password")
    
    count_matched = 0
    
    for i, b in enumerate(bookmarks):
        item = b.get('item', {})
        record = item.get('record', {})
        text = record.get('text', '')
        author = item.get('author', {}).get('handle', 'unknown')
        
        # Extract Link Facet
        link = None
        facets = record.get('facets', [])
        for f in facets:
            for feat in f.get('features', []):
                if feat.get('$type') == 'app.bsky.richtext.facet#link':
                    link = feat.get('uri')
                    break
            if link: break
            
        if not link:
            # Skip items without links for the audit (can't map them)
            continue
            
        # Determine state from author
        state_code = poster._detect_state(author)
        poster.state = state_code 
        
        # SAFE LOOKUP
        # Use simple heuristic if URL parsing fails or mock data
        if "mock-link" in link:
             council_name = "Unknown Council"
        else:
             council_name = get_council_name_from_url(link, domain_map)
             
        if council_name != "Unknown Council":
            count_matched += 1

        # Clean Title 
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        
        # HEURISTIC FOR TITLE RECOVERY FOR AUDIT
        # If it's the "3673" style garbage, we mark it.
        # Otherwise take the first line.
        raw_title = lines[0] if lines else "NO TITLE"
        
        if re.match(r'^\d+$', raw_title) or "Posted" in raw_title:
             clean_title = "[REQUIRES SCRAPING] " + raw_title
        else:
             clean_title = poster._sanitize_title(raw_title)
        
        # Generate Preview
        preview_text, _, _ = poster._format_post_with_facets(
            council_name=council_name,
            title=clean_title,
            url=link,
            date=None, 
            excerpt="[Excerpt Content Placeholder]",
            extra_hashtags=[]
        )
        
        report_lines.append(f"ITEM #{i+1} | OWNER: {author} | URL: {link[:40]}...")
        report_lines.append(f"DETECTED COUNCIL: {council_name}")
        report_lines.append("-" * 20 + " PREVIEW " + "-" * 20)
        report_lines.append(preview_text)
        report_lines.append("="*60 + "\n")

    report_lines.append(f"SUMMARY: Matched {count_matched}/{len(bookmarks)} Councils via Domain Map.")

    with open("dry_run_audit_safe.txt", "w") as f:
        f.write("\n".join(report_lines))
        
    print(f"Audit complete. Report saved to 'dry_run_audit_safe.txt'.")

if __name__ == "__main__":
    main()
