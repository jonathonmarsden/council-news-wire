import sys
import os
import logging
from datetime import datetime
from core.scrapers import ScraperFactory
from core.poster import BlueSkyPoster
from core.database import Database
from core.utils import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def repost_wa_councils():
    councils_to_run = ['cranbrook', 'fremantle', 'irwin', 'trayning', 'albany']
    
    # Initialize database
    db = Database()
    
    # Initialize poster
    from dotenv import load_dotenv
    load_dotenv()
    
    handle = os.getenv('BLUESKY_HANDLE_WA')
    password = os.getenv('BLUESKY_PASSWORD_WA')
    
    if not handle or not password:
        print("Error: WA BlueSky credentials not found.")
        return
        
    poster = BlueSkyPoster(handle, password)
    
    # Load WA config
    import json
    with open('states/wa/councils.json', 'r') as f:
        wa_data = json.load(f)
        
    wa_councils = {c['id']: c for c in wa_data['councils']}
    
    for council_id in councils_to_run:
        if council_id not in wa_councils:
            print(f"Council {council_id} not found in config.")
            continue
            
        config = wa_councils[council_id]
        print(f"\n--- Running Scraper for {config['name']} ---")
        
        try:
            scraper = ScraperFactory.create_scraper(config)
            articles = scraper.scrape()
            print(f"Found {len(articles)} articles.")
            
            new_count = 0
            for article in articles:
                # Save to DB
                article_id = db.add_article(article.to_dict(), 'wa')
                
                # Post to BlueSky
                if article.date:
                    # Check if date is naive
                    if article.date.tzinfo is None:
                        age = (datetime.now() - article.date).days
                    else:
                        # Make datetime.now() aware if article.date is aware
                        # Or just ignore timezone for age check roughly
                        age = (datetime.now().date() - article.date.date()).days
                        
                    if age > 7:
                        print(f"Skipping old article: {article.title} ({age} days old)")
                        continue
                
                # Check if already posted (in local DB)
                if db.is_posted(article.url):
                    print(f"Already posted: {article.title}")
                    continue
                    
                print(f"Posting: {article.title}")
                
                # Prepare hashtags
                hashtags = ['#LGNewsRoundup', '#WALGA', '#WACouncils']
                
                success = poster.post_article(
                    council_name=article.council_name,
                    title=article.title,
                    url=article.url,
                    date=article.date,
                    excerpt=article.excerpt,
                    hashtags=hashtags
                )
                
                if success:
                    db.mark_as_posted(article.url, handle)
                    new_count += 1
                    # Be polite
                    import time
                    time.sleep(2)
                
            print(f"Posted {new_count} articles for {config['name']}.")
            
        except Exception as e:
            print(f"Error running {council_id}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    repost_wa_councils()
