import json
import re

raw_text = """
Aurukun - https://www.aurukun.qld.gov.au/blog/
Balonne - https://www.balonne.qld.gov.au/About-Council/Publications-Media/News
Banana - https://www.banana.qld.gov.au/news/category/latest-news
Barcaldine - https://www.barcaldinerc.qld.gov.au/Our-Council/Media-Releases-Public-Notices
Barcoo - https://www.barcoo.qld.gov.au/news-and-events/news
Blackall Tambo - https://www.btrc.qld.gov.au/Home/Tabs/News
Boulia - https://www.boulia.qld.gov.au/News-articles
Brisbane - https://www.brisbane.qld.gov.au/about-council/news-and-community-updates/community-service-announcements
Bulloo - https://www.bulloo.qld.gov.au/About-Council/Council-Publications/Council-News
Bundaberg - https://www.bundabergnow.com/
Burdekin - https://www.burdekin.qld.gov.au/latest-news
Burke - https://www.burke.qld.gov.au/news/category/all
Cairns - https://www.cairns.qld.gov.au/council/news-notices/media-releases
Carpentaria - https://www.carpentaria.qld.gov.au/news/category/all
Cassowary Coast - https://www.cassowarycoast.qld.gov.au/homepage/178/council-news
Central Highlands - https://www.chrc.qld.gov.au/about-council/news/
Charters Towers - https://www.charterstowers.qld.gov.au/news
Cherbourg Aboriginal Shire - https://cherbourg.qld.gov.au/news-events/
Cloncurry - https://www.cloncurry.qld.gov.au/News-articles
Cook - https://www.cook.qld.gov.au/council/news-public-notices-and-media-releases/news/
Croydon - https://www.croydon.qld.gov.au/News-articles
Diamantina - https://www.diamantina.qld.gov.au/News/Latest-News
Doomadgee Aboriginal Shire -
Douglas - https://douglas.qld.gov.au/category/general-news/
Etheridge https://www.etheridge.qld.gov.au/Home/Tabs/News
Flinders - https://www.flinders.qld.gov.au/Your-Council/Latest-News
Fraser Coast https://www.frasercoast.qld.gov.au/media-releases
Gladstone: https://www.gladstone.qld.gov.au/news/category/all
Gold Coast - https://www.goldcoast.qld.gov.au/Council/City-news
Goondiwindi -https://www.grc.qld.gov.au/News-and-Community/News/Council-News
Gympie - https://www.gympie.qld.gov.au/Council/News-and-Notices/Latest-News
Livingstone - https://www.livingstone.qld.gov.au/Your-Council/Publications-and-Media/Media-Releases
Lockhart River - https://lockhart.nsw.gov.au/council/latest-news/
Lockyer Valley - https://www.lockyervalley.qld.gov.au/our-council/news
Logan https://www.logan.qld.gov.au/news/category/all
Longreach - https://www.longreach.qld.gov.au/About-Council/Latest-News
Mackay - https://www.mackay.qld.gov.au/about_council/news_and_media/media_releases
Mapoon - https://www.mapoon.qld.gov.au/News
Maranoa - https://www.maranoa.qld.gov.au/About-Council/Publications-and-Media/Latest-Council-News
Mareeba - https://msc.qld.gov.au/council/news/
McKinlay - https://www.mckinlay.qld.gov.au/News/Media-releases
Moreton Bay - https://www.moretonbay.qld.gov.au/News/Media
Mornington - https://www.mornington.qld.gov.au/news/latest-news/
Mount Isa https://www.mountisa.qld.gov.au/Latest-News
Murweh - https://www.murweh.qld.gov.au/News
Napranum - https://www.napranum.qld.gov.au/news/
Noosa - https://www.noosa.qld.gov.au/About-Council/News-and-publications/Media-releases
North Burnett - https://northburnett.qld.gov.au/communications/media-releases-public-notices/
Northern Peninsula Area - https://www.nparc.qld.gov.au/Our-council/Public-notice
Palm Island - https://www.palmcouncil.qld.gov.au/News-articles
Paroo - https://www.paroo.qld.gov.au/News-and-Events/News
Pormpuraaw - https://www.pormpuraaw.qld.gov.au/public-news-notices
Quilpie - https://quilpie.qld.gov.au/news/
Redland https://www.redlandscoasttoday.com.au/
Richmond - https://www.richmond.qld.gov.au/monthly-newsletters
Rockhampton https://www.rockhamptonregion.qld.gov.au/AboutCouncil/News-and-announcements/Latest-News
Scenic Rim https://www.scenicrim.qld.gov.au/our-council/connect-with-council/news-and-announcements
Somerset - https://www.somerset.qld.gov.au/News
South Burnett https://www.southburnett.qld.gov.au/about-council/news/media-releases
Southern Downs https://www.sdrc.qld.gov.au/council/news-notices/latest-news
Sunshine Coast - https://www.sunshinecoast.qld.gov.au/news
Tablelands - https://www.trc.qld.gov.au/category/news/
Toowoomba - https://www.tr.qld.gov.au/about-council/news-publications/media-releases
Torres - https://www.torres.qld.gov.au/Council/Media-Release
Torres Strait Island - https://tsirc.qld.gov.au/news/
Townsville - https://www.townsville.qld.gov.au/about-council/news-and-publications/media-releases
Weipa Town Authority - https://www.weipatownauthority.com.au/Your-WTA/Publications-and-Media/News
Western Downs - https://www.wdrc.qld.gov.au/Council/News-Public-Updates/News
Whitsunday - https://www.whitsundayrc.qld.gov.au/Our-Council/Publications-and-Media/Latest-News
Winton - https://www.winton.qld.gov.au/News/Latest-News
Woorabinda - https://www.woorabinda.qld.gov.au/News-and-Updates/Council-News
Wujal Wujal - https://www.wujalwujalcouncil.qld.gov.au/council/newsandnotices/
Yarrabah - https://www.yarrabah.qld.gov.au/yarrabah-news/
"""

councils = []
for line in raw_text.strip().split('\n'):
    line = line.strip()
    if not line:
        continue
        
    # Split by hyphen or colon or just space if no separator
    # Some lines are "Name - URL", some "Name: URL", some "Name URL"
    
    # Try to find the URL
    url_match = re.search(r'(https?://\S+)', line)
    if not url_match:
        # print(f"Skipping line with no URL: {line}")
        continue
        
    url = url_match.group(1)
    
    # Name is everything before the URL, cleaned up
    name_part = line[:line.find(url)].strip()
    name_part = re.sub(r'[-:]$', '', name_part).strip()
    
    # Generate ID
    council_id = name_part.lower().replace(' ', '-').replace('.', '')
    
    # Append "Council" if not present (optional, but good for consistency)
    # Many in the list are just "Aurukun", "Balonne". 
    # I'll leave the name as is from the list, but maybe append "Council" to the ID or Name if it looks short?
    # Actually, let's just use the name provided but ensure it looks nice.
    # Most are just the LGA name.
    
    full_name = name_part
    if "Council" not in full_name and "Shire" not in full_name and "City" not in full_name and "Authority" not in full_name:
        full_name += " Council"
        
    councils.append({
        "id": council_id,
        "name": full_name,
        "news_url": url,
        "scraper": "curl_scraper", # Default to curl_scraper for QLD as many use WAFs
        "enabled": True
    })

output = {"councils": councils}
print(json.dumps(output, indent=4))
