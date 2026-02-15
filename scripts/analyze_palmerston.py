from bs4 import BeautifulSoup

def analyze_palmerston():
    with open('debug_palmerston.html', 'r') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try the observed selectors
    items = soup.select('article.teaser-card')
    print(f"Found {len(items)} items with 'article.teaser-card'")
    
    for i, item in enumerate(items[:3]):
        print(f"\n--- Item {i+1} ---")
        
        # Title
        title_tag = item.select_one('h3.teaser-card__title a')
        if title_tag:
            print(f"Title: {title_tag.get_text(strip=True)}")
            print(f"Link: {title_tag['href']}")
        else:
            print("Title: NOT FOUND")
            
        # Date
        date_tag = item.select_one('time.teaser-card__time')
        if date_tag:
            print(f"Date: {date_tag.get_text(strip=True)} (datetime={date_tag.get('datetime')})")
        else:
            print("Date: NOT FOUND")

if __name__ == "__main__":
    analyze_palmerston()
