
import sqlite3
import re
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_tangled_titles():
    conn = sqlite3.connect('bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all articles for NSW councils
    # We don't have a 'state' column in articles, but we can filter by council_id if we knew them,
    # or just check all and filter by known NSW council names if needed.
    # For now, let's check all and see what the patterns look like.
    
    cursor.execute("SELECT id, council_id, title, url, posted_date FROM articles WHERE posted = 1")
    articles = cursor.fetchall()
    
    # Pattern for "TitleDD Mon" or "TitleD Mon" (e.g. "Meeting Minutes12 Nov")
    # Looking for: non-space, digit(s), space, Month
    # The issue described was "Title12 Nov" -> no space before digit?
    
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
              "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    month_pattern = "|".join(months)
    # Regex: Any char, then 1-2 digits, then space, then Month, at the end of string
    # And importantly, NO space before the digits? Or maybe there is?
    # The user said "tangled up", implying concatenation.
    
    # Example: "Council Meeting12 Nov"
    regex = re.compile(r'.*[a-z](?:\d{1,2})\s(?:' + month_pattern + r').*$', re.IGNORECASE)
    
    tangled_count = 0
    tangled_ids = []
    
    print(f"Checking {len(articles)} posted articles for tangled dates...")
    
    for article in articles:
        title = article['title']
        if regex.match(title):
            # Double check it's not just a date in the title like "Minutes 12 Nov" (valid)
            # We want "Minutes12 Nov" (invalid)
            # So check if the char before the digit is NOT a space.
            
            # Find the digit start
            match = re.search(r'([^\s])(\d{1,2})\s(?:' + month_pattern + r')', title, re.IGNORECASE)
            if match:
                print(f"Found tangled: [{article['council_id']}] {title}")
                tangled_count += 1
                tangled_ids.append(article['id'])
                
    print(f"\nFound {tangled_count} potentially tangled titles.")
    return tangled_ids

if __name__ == "__main__":
    check_tangled_titles()
