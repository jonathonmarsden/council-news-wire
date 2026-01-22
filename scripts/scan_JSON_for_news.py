import json
import re
from datetime import datetime

INPUT_FILE = "debug_armadale_extracted_v2.txt"

def scan_for_news_candidates():
    print(" scanning for news candidates...")
    
    with open(INPUT_FILE, "r") as f:
        content = f.read()

    # The file contains multiple JSON objects/arrays, one per line or separated by newlines
    # We'll try to parse valid JSON substrings or just regex search
    
    # Since the extraction was crude, let's try to find JSON objects that look like Contentful Entries
    # Pattern: "sys": { ... "type": "Entry", "contentType": { ... "id": "mediaRelease" ... } }
    
    # Let's count potential content types first
    matches = re.findall(r'"contentType":\s*\{\s*"sys":\s*\{\s*"type":\s*"Link",\s*"linkType":\s*"ContentType",\s*"id":\s*"([^"]+)"', content)
    
    from collections import Counter
    print("Content Types found in raw dump:")
    print(Counter(matches))

    # Now let's try to extract specific fields that look like news
    # Look for "title" and "date" in close proximity
    
    # We will try to parse the whole file as a list of JSONs if possible, or line by line
    # Based on previous output, it seems to be a list of JS commands: self.__next_f.push(...)
    # We want the arguments to push.
    
    # Regex to grab the array passed to push: self.__next_f.push([1, "JSON_HERE"])
    # We need to be careful with nested brackets.
    
    # Alternative: Just look for JSON-like blocks that have "contentTypeId": "mediaRelease"
    # or ANY entry that has a 'date' field.
    
    # Let's look for "mediaRelease" items specifically again
    print("\nScanning for 'mediaRelease' items details...")
    # Find the start of an entry
    entries = re.finditer(r'"sys":\s*\{[^}]*"id":\s*"[^"]+",\s*"type":\s*"Entry".*?"contentType":\s*\{[^}]*"id":\s*"mediaRelease"', content, re.DOTALL)
    
    found_any = False
    for match in entries:
        found_any = True
        start = match.start()
        # Grab a chunk around it
        chunk = content[start-100:start+1000] 
        print(f"--- Found mediaRelease Entry Candidate ---\n{chunk}\n------------------------------------------")
        
    if not found_any:
        print("No 'mediaRelease' entries found (other than maybe the widget definition).")

    # Let's look for ANY entry with a field named "date" or "publishedDate"
    print("\nScanning for generic dates matching recent year (2025)...")
    date_matches = re.findall(r'"([^"]+)":\s*"2025-[^"]+"', content)
    print(f"Found {len(date_matches)} date fields.")
    # Show strict sample
    print(set(date_matches))

    print("\nCheck 'datePublished' contexts:")
    dp_matches = re.finditer(r'"datePublished":\s*"([^"]+)"', content)
    for i, m in enumerate(dp_matches):
        if i > 5: break
        start = m.start()
        print(f"--- datePublished Context {i} ---")
        print(content[start-500:start+500])


if __name__ == "__main__":
    scan_for_news_candidates()
