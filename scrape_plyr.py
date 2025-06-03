import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed


def extract_tracks_from_javascript(html_content):
    """
    Extract track information from JavaScript in the HTML.
    Looks for various patterns used by Plyr-based audiobook sites.
    """
    tracks = []
    
    # Pattern 1: Look for tracks array in JavaScript
    # More precise pattern to match just the array
    tracks_pattern = r'(?:var\s+)?tracks\s*=\s*(\[[^\]]*(?:\[[^\]]*\][^\]]*)*\])\s*[,;]'
    match = re.search(tracks_pattern, html_content, re.IGNORECASE | re.DOTALL)
    
    if match:
        try:
            # Extract the JavaScript array
            tracks_str = match.group(1)
            
            # Clean up JavaScript syntax to make it valid JSON
            # First, handle the trailing commas after the last property in objects
            tracks_str = re.sub(r',\s*}', '}', tracks_str)  # Remove trailing commas before }
            tracks_str = re.sub(r',\s*]', ']', tracks_str)  # Remove trailing commas before ]
            
            # Check if keys are already quoted (look for pattern like "key":)
            if '"track":' in tracks_str:
                # Keys are already quoted, just rename 'track' to 'track_num'
                tracks_str = tracks_str.replace('"track":', '"track_num":')
            
            # Try to parse the cleaned JSON
            try:
                tracks_data = json.loads(tracks_str)
            except json.JSONDecodeError as je:
                print(f"JSON parsing error: {je}")
                print(f"Error at position {je.pos} in cleaned tracks string")
                # Print a snippet around the error position for debugging
                start = max(0, je.pos - 50)
                end = min(len(tracks_str), je.pos + 50)
                print(f"Context: ...{tracks_str[start:end]}...")
                raise
            
            for track in tracks_data:
                # Get track info
                name = track.get('name', track.get('title', track.get('chapter', 'Unknown')))
                chapter_id = track.get('chapter_id', track.get('chapterid', track.get('id', '0')))
                track_num = track.get('track_num', track.get('track', len(tracks) + 1))
                
                # Handle direct URL (like welcome track) vs API-based tracks
                if 'chapter_link_dropbox' in track and track['chapter_link_dropbox'].startswith('http'):
                    # Direct URL
                    tracks.append({
                        'url': track['chapter_link_dropbox'],
                        'name': name,
                        'chapter_id': chapter_id,
                        'track_num': track_num,
                        'needs_api': False
                    })
                else:
                    # Needs API call
                    tracks.append({
                        'url': None,
                        'name': name,
                        'chapter_id': chapter_id,
                        'track_num': track_num,
                        'needs_api': True
                    })
        except Exception as e:
            print(f"Error parsing tracks array: {e}")
    
    # Pattern 2: Look for myPost() function URLs (common in some audiobook sites)
    post_pattern = r'myPost\([\'"]([^\'"]+)[\'"]\)'
    post_matches = re.findall(post_pattern, html_content)
    for i, url in enumerate(post_matches):
        if url and ('.mp3' in url or 'dropbox' in url):
            tracks.append({
                'url': url,
                'name': f'Chapter {i + 1}',
                'chapter_id': i + 1
            })
    
    # Pattern 3: Look for Plyr source configurations
    plyr_pattern = r'source\s*:\s*[\'"]([^\'"]+\.mp3)[\'"]'
    plyr_matches = re.findall(plyr_pattern, html_content)
    for i, url in enumerate(plyr_matches):
        tracks.append({
            'url': url,
            'name': f'Track {i + 1}',
            'chapter_id': i + 1
        })
    
    return tracks


def fetch_mp3_url_from_api(chapter_id, server_type=1):
    """
    Fetch the actual MP3 URL from the API using chapter ID.
    """
    api_url = "https://api.galaxyaudiobook.com/api/getMp3Link"
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    payload = {
        "chapterId": int(chapter_id),
        "serverType": server_type
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('link_mp3')
    except Exception as e:
        print(f"Error fetching MP3 URL for chapter {chapter_id}: {e}")
        return None


def extract_dropbox_links(html_content, base_url):
    """
    Extract and construct Dropbox links from the HTML.
    Many audiobook sites use Dropbox for hosting.
    """
    links = []
    
    # Look for Dropbox patterns
    dropbox_patterns = [
        r'https?://[^"\s]*dropbox[^"\s]*\.mp3[^"\s]*',
        r'[\'"]([^\'"\s]*dropbox[^\'"\s]*\.mp3[^\'"\s]*)[\'"]',
        r'chapter_link_dropbox[\'"]?\s*:\s*[\'"]([^\'"\s]+)[\'"]'
    ]
    
    for pattern in dropbox_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for match in matches:
            if match and '.mp3' in match:
                # Handle relative Dropbox paths
                if not match.startswith('http'):
                    # Could be a path like "audiobook_name/file.mp3"
                    match = f"https://dl.dropboxusercontent.com/s/{match}"
                links.append(match)
    
    return list(set(links))  # Remove duplicates


def scrape(url, prefix=None, directory=None):
    """
    Extract audio track metadata from Plyr-based audio players.
    
    Returns:
        List of track dictionaries with 'url' and 'name' keys,
        or None if scraping fails.
    """
    print(f"[Plyr Scraper] Starting scrape of: {url}")
    print("Fetching page content...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        html_content = response.text
        
        # Extract tracks from JavaScript
        print("Analyzing page for Plyr audio tracks...")
        tracks = extract_tracks_from_javascript(html_content)
        
        # Fetch MP3 URLs for tracks that need API calls using parallel requests
        api_tracks = [t for t in tracks if t.get('needs_api') and t.get('chapter_id') != '0']
        
        if api_tracks:
            print(f"\nFetching MP3 URLs from API for {len(api_tracks)} tracks...")
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_track = {
                    executor.submit(fetch_mp3_url_from_api, track['chapter_id']): track 
                    for track in api_tracks
                }
                
                for future in as_completed(future_to_track):
                    track = future_to_track[future]
                    try:
                        mp3_url = future.result()
                        if mp3_url:
                            track['url'] = mp3_url
                    except Exception as e:
                        print(f"  ✗ Failed to get URL for: {track['name']} - {e}")
        
        # Filter out tracks without URLs
        tracks_with_urls = [t for t in tracks if t.get('url')]
        
        if not tracks_with_urls:
            print("No audio tracks found. This might require a more advanced scraping method.")
            print("Consider using the scrape_with_playwright.py for JavaScript-heavy sites.")
            return None
        
        print(f"\nFound {len(tracks_with_urls)} audio tracks:")
        for i, track in enumerate(tracks_with_urls, 1):
            print(f"  {i:2d}. {track['name']:<40} {track['url']}")
        
        # Return track metadata for main.py to download
        return tracks_with_urls
        
    except Exception as e:
        print(f"Error during Plyr scraping: {e}")
        print("\nTip: If this is a complex JavaScript site, try using Playwright:")
        print("  python scrape_with_playwright.py")
        return None


# Allow script to be run standalone for testing
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Plyr audio player scraper')
    parser.add_argument('url', help='URL of the webpage to scrape')
    parser.add_argument('prefix', help='Prefix for all file names', nargs='?')
    parser.add_argument('-d', '--directory', help='Directory to save files', default=None)
    args = parser.parse_args()
    
    tracks = scrape(args.url)
    if tracks:
        print(f"\nExtracted {len(tracks)} tracks successfully.")
    else:
        print("\nFailed to extract tracks.")