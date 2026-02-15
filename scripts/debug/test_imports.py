print("1. Importing sys")
import sys
print("2. Importing Path")
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

print("3. Importing BeautifulSoup")
from bs4 import BeautifulSoup
print("4. Importing RSSScraper")
from core.scrapers.rss import RSSScraper
print("5. Importing CardScraper")
from core.scrapers.card import CardScraper
print("6. Importing OpenCitiesScraper")
from core.scrapers.custom import OpenCitiesScraper

print("Done imports")
