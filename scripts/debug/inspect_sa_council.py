
import asyncio
import sys
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

async def main():
    if len(sys.argv) < 2:
        print("Usage: python3 inspect_sa_council.py <url>")
        sys.exit(1)
        
    url = sys.argv[1]
    print(f"Fetching {url}...")
    
    async with AsyncSession(impersonate="chrome110") as session:
        response = await session.get(url)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            print("\n--- Searching for potential article containers ---")
            
            # Look for elements containing "Read more" or similar
            keywords = ["Read more", "Read More", "Full Story", "View Article"]
            links = []
            for kw in keywords:
                links.extend(soup.find_all('a', string=lambda t: t and kw in t))
                
            print(f"Found {len(links)} 'Read more' style links")
            
            if links:
                first_link = links[0]
                print("\n--- Structure of first link parent ---")
                parent = first_link.parent
                for i in range(4):
                    if parent:
                        print(f"Parent {i}: {parent.name} class={parent.get('class')}")
                        parent = parent.parent
            
            print("\n--- Searching for common news classes ---")
            common_classes = ['news', 'article', 'item', 'list', 'card', 'post']
            for cls in common_classes:
                elements = soup.find_all(class_=lambda c: c and cls in c)
                if elements:
                    print(f"Found {len(elements)} elements with class containing '{cls}'")
                    # Print the first one's class
                    print(f"  Example classes: {elements[0].get('class')}")

if __name__ == "__main__":
    asyncio.run(main())
