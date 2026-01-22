from bs4 import BeautifulSoup

html = """
<div class="module-list">
    <div class="row">
        <div class="col-sm-5 pv-16">
            <div class="news-image-wrapper">
                <img src="..." alt="Image" />
            </div>
        </div>
        <div class="col-sm-7 pv-16">
            <span class="h5">Posted 18 December 2025</span>
            <span class="h4 text-primary">Public Notice: Annual General Meeting of Electors</span>
            <p>Excerpt...</p>
            <div class="pv-8">
                <a class="btn btn-primary" href="/news/test/123">Read More</a>
            </div>
        </div>
    </div>
</div>
"""

def test_scrape():
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('.module-list')
    rows = container.select('.row')
    
    for row in rows:
        print("--- Row ---")
        date_el = row.select_one('.h5')
        if date_el:
            print(f"Date Match: {date_el}")
            print(f"Date Text: '{date_el.get_text(strip=True)}'")
        
        title_tag = row.select_one('.h4')
        if title_tag:
            print(f"Title Match: {title_tag}")
            print(f"Title Text: '{title_tag.get_text(strip=True)}'")

if __name__ == "__main__":
    test_scrape()
