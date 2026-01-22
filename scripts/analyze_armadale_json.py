import json
import re

def analyze_json_stream(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The file contains lines like "1a:[...]" or just JSON chunks stuck together
    # It's not a valid JSON file. It's a concatenation of JS calls.
    # However, our previous script `debug_armadale_extractor_v2.py` ALREADY purely extracted the JSON strings.
    # Let's verify what `debug_armadale_extracted_v2.txt` looks like.
    # If it is just a massive string of JSON objects, we might be able to regex find "contentTypeId":"..."
    
    # Let's find all occurences of "contentTypeId":"VALUE"
    content_type_pattern = r'"contentTypeId":"([^"]+)"'
    matches = re.findall(content_type_pattern, content)
    
    print(f"Found {len(matches)} contentTypeId matches.")
    from collections import Counter
    print(Counter(matches).most_common())

    # Let's also find all "type":"Entry" and see their contentTypes (which are nested)
    # The structure is usually "contentType":{"sys":{"id":"VALUE"}}
    entry_content_type_pattern = r'"contentType":\{"sys":\{"type":"Link","linkType":"ContentType","id":"([^"]+)"\}\}'
    entry_matches = re.findall(entry_content_type_pattern, content)
    
    print(f"Found {len(entry_matches)} Entry contentType matches.")
    print(Counter(entry_matches).most_common())

    # Let's look for titles of things that map to news items
    # Maybe keys like "newsTitle", "headline"?
    
if __name__ == "__main__":
    analyze_json_stream("debug_armadale_extracted_v2.txt")
