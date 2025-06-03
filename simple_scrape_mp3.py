import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def scrape(url, prefix=None, directory=None):
    """
    Extract direct MP3 links from a webpage.
    
    Returns:
        List of track dictionaries with 'url', 'name', and 'track_num' keys,
        or None if scraping fails.
    """
    print(f"[Simple MP3 Scraper] Starting scrape of: {url}")
    print("Fetching page content...")
    
    try:
        # Fetch the page
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all <a> tags with href ending in .mp3
        href_elements = soup.find_all('a', href=lambda href: href and href.endswith('.mp3'))
        
        # Also find elements with data-url attribute ending in .mp3
        # Some sites use data-url instead of href for audio links
        data_url_elements = soup.find_all(attrs={'data-url': lambda url: url and url.endswith('.mp3')})
        
        # Combine both types of elements
        elements = href_elements + data_url_elements
        
        print(f"Found {len(elements)} elements to process on the page.")
        
        # Extract MP3 URLs
        tracks = []
        mp3_count = 0
        
        for element in elements:
            # Get the URL from either href or data-url
            url_value = element.get('href') or element.get('data-url')
            
            if url_value is not None and url_value.endswith('.mp3'):
                mp3_count += 1
                # Make sure the url_value is an absolute URL
                url_value = urljoin(url, url_value)
                
                # Try to extract a meaningful name from the element or URL
                name = element.get_text(strip=True) or f"Track {mp3_count}"
                if not name or name == "":
                    # Extract name from URL
                    name = url_value.split('/')[-1].replace('.mp3', '')
                
                tracks.append({
                    'url': url_value,
                    'name': name,
                    'track_num': mp3_count
                })
                
                print(f"\nFound MP3 #{mp3_count}: {url_value}")
        
        print(f"\n[Simple MP3 Scraper] Found {mp3_count} MP3 files")
        if mp3_count == 0:
            print("No direct MP3 links found. This site might use a different audio plugin.")
            return None
        
        return tracks
        
    except Exception as e:
        print(f"Error during simple MP3 scraping: {e}")
        return None


# Allow script to be run standalone for testing
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Simple MP3 link scraper')
    parser.add_argument('url', help='URL of the webpage to scrape')
    parser.add_argument('prefix', help='Prefix for all file names', nargs='?')
    parser.add_argument('-d', '--directory', help='Directory to put the downloaded files', default=None)
    args = parser.parse_args()
    
    tracks = scrape(args.url)
    if tracks:
        print(f"\nExtracted {len(tracks)} tracks successfully.")
    else:
        print("\nFailed to extract tracks.")