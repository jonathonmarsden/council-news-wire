import requests
from bs4 import BeautifulSoup

def analyze_darwin():
    url = "https://www.darwin.nt.gov.au/news"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find a known news link
        link = soup.find('a', href=lambda x: x and '/council/news-media/' in x)
        if link:
            print(f"Found link: {link}")
            # Go up to find the container
            parent = link.find_parent('div')
            print(f"Parent classes: {parent.get('class')}")
            grandparent = parent.find_parent('div')
            print(f"Grandparent classes: {grandparent.get('class')}")
            
            # Try to find date nearby
            article_container = link.find_parent('div', class_=lambda x: x and ('view-mode-teaser' in x or 'views-row' in x or 'teaser' in x))
            if not article_container:
                # heuristic: go up 3 levels
                article_container = link.find_parent().find_parent().find_parent()
                
            print(f"Article Container: {article_container.name} class={article_container.get('class')}")
            
            # Check for date in container
            date = article_container.find('time')
            if date:
                print(f"Date found: {date}")
            else:
                print("No <time> tag found, checking text...")
                print(article_container.get_text()[:100])
        else:
            print("No news link found.")

    except Exception as e:
        print(e)

if __name__ == "__main__":
    analyze_darwin()
