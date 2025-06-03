import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def scrape(url, prefix=None, directory=None):
    """
    Extract direct audio file links from a webpage.
    Supports: MP3, M4A, AAC, OGG, OPUS, WebM, WAV, FLAC
    
    Returns:
        List of track dictionaries with 'url', 'name', and 'track_num' keys,
        or None if scraping fails.
    """
    print(f"[Simple Audio Scraper] Starting scrape of: {url}")
    print("Looking for direct audio links on the page...")
    print("Fetching page content...")
    
    try:
        # Fetch the page
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Define supported audio extensions
        audio_extensions = ('.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac')
        
        # Find all <a> tags with href ending in audio extensions
        href_elements = soup.find_all('a', href=lambda href: href and any(href.lower().endswith(ext) for ext in audio_extensions))
        
        # Also find elements with data-url attribute ending in audio extensions
        # Some sites use data-url instead of href for audio links
        data_url_elements = soup.find_all(attrs={'data-url': lambda url: url and any(url.lower().endswith(ext) for ext in audio_extensions)})
        
        # Combine both types of elements
        elements = href_elements + data_url_elements
        
        print(f"Found {len(elements)} audio elements to process on the page.")
        
        # Extract audio file URLs
        tracks = []
        audio_count = 0
        
        for element in elements:
            # Get the URL from either href or data-url
            url_value = element.get('href') or element.get('data-url')
            
            if url_value is not None and any(url_value.lower().endswith(ext) for ext in audio_extensions):
                audio_count += 1
                # Make sure the url_value is an absolute URL
                url_value = urljoin(url, url_value)
                
                # Extract original filename from URL
                original_filename = url_value.split('/')[-1]
                
                # Get file extension
                file_ext = next(ext for ext in audio_extensions if original_filename.lower().endswith(ext))
                
                # Try to get a display name from the element text
                display_name = element.get_text(strip=True)
                if not display_name:
                    # Use filename without extension as display name
                    display_name = original_filename
                    for ext in audio_extensions:
                        display_name = display_name.replace(ext, '')
                        display_name = display_name.replace(ext.upper(), '')
                
                tracks.append({
                    'url': url_value,
                    'name': display_name,
                    'original_filename': original_filename,
                    'track_num': audio_count
                })
                
                print(f"\nFound audio file #{audio_count} ({file_ext}): {url_value}")
        
        print(f"\n[Simple Audio Scraper] Found {audio_count} audio files")
        if audio_count == 0:
            print("No direct audio links found. This site might use a different audio plugin.")
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