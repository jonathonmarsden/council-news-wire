import json
import os
import re

def clean_text(text):
    """Clean and normalize text content."""
    if not isinstance(text, str):
        return text
        
    # Fix common mojibake (UTF-8 bytes interpreted as Windows-1252/Latin-1)
    replacements = {
        'â': "'",
        'â\x80\x99': "'",
        'â': "-",
        'â\x80\x93': "-",
        'â': "-",
        'â\x80\x94': "-",
        'â': '"',
        'â\x80\x9c': '"',
        'â': '"',
        'â\x80\x9d': '"',
        'â¦': '...',
        'â\x80\xa6': '...',
        'Â': '',  # Non-breaking space artifact
        '\xa0': ' ', # Non-breaking space
        '\u00a0': ' ', # Non-breaking space unicode
    }
    
    for bad, good in replacements.items():
        text = text.replace(bad, good)
        
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_json_file(filepath):
    print(f"Cleaning {filepath}...")
    
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cleaned_count = 0
    
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, str):
                        cleaned = clean_text(value)
                        if cleaned != value:
                            item[key] = cleaned
                            cleaned_count += 1
    
    if cleaned_count > 0:
        print(f"Fixed {cleaned_count} fields.")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Saved changes.")
    else:
        print("No changes needed.")

if __name__ == "__main__":
    # Use relative path from the script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    filepath = os.path.join(project_root, 'scraped_articles.json')
    clean_json_file(filepath)
