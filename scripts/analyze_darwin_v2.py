import requests
from bs4 import BeautifulSoup

def analyze_darwin():
    url = "https://www.darwin.nt.gov.au/news"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove nav/header to avoid menu links
        for nav in soup.find_all(['nav', 'header']):
            nav.decompose()
        # Also remove the mega menu block specifically if it's a div
        for mm in soup.find_all('div', class_='we-mega-menu-submenu'):
            mm.decompose()
            
        # Find a news link now
        link = soup.find('a', href=lambda x: x and '/council/news-media/' in x)
        if link:
            print(f"Found link: {link}")
            # Walk up to find the article container
            container = link.find_parent('div', class_='views-row')
            if not container:
                container = link.find_parent('article')
                
            if container:
                print(f"Container Tag: {container.name}")
                print(f"Container Classes: {container.get('class')}")
                
                title = container.find(['span', 'h3', 'div'], class_=lambda x: x and 'title' in x)
                if title:
                    print(f"Title Element: {title}")
                
                # Check different date formats
                date = container.find('span', class_='date-display-single')
                if not date:
                    date = container.find('div', class_='field--name-post-date')
                if not date:
                    date = container.find('time')

                if date:
                    print(f"Date found: {date} (Class: {date.get('class')})")
                else:
                    print("No date found. Container text:")
                    print(container.get_text(separator=' | ', strip=True))

            else:
                 print("Could not find container (views-row or article). dumping parents:")
                 for p in link.parents:
                     print(f"  {p.name} {p.get('class')}")
                     if p.name == 'body': break
        else:
            print("No news link found in body.")

    except Exception as e:
        print(e)
            
if __name__ == "__main__":
    analyze_darwin()
