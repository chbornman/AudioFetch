import os
import re
import time
import requests
from bs4 import BeautifulSoup

def scrape_audiobook_simple(url):
    """
    Simplified scraper that constructs MP3 URLs based on observed patterns
    """
    
    print(f"Fetching page: {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract playlist items
    playlist_items = soup.select('.plItem')
    tracks = []
    
    for item in playlist_items:
        track_num = item.select_one('.plNum').text.strip().rstrip('.')
        track_title = item.select_one('.plTitle').text.strip()
        tracks.append({
            'number': track_num,
            'title': track_title
        })
    
    print(f"Found {len(tracks)} tracks")
    
    # Based on the pattern observed: "the-well-of-ascension/1195800334/"
    # We need to find the base path for this audiobook
    # This might be embedded in the JavaScript or initial MP3 load
    
    # Try to extract the base path from the page
    script_tags = soup.find_all('script')
    base_path = None
    
    for script in script_tags:
        if script.string:
            # Look for patterns like "the-well-of-ascension/[numbers]/"
            match = re.search(r'the-well-of-ascension/\d+/', script.string)
            if match:
                base_path = match.group(0)
                break
    
    if not base_path:
        print("Could not find base path automatically.")
        print("Manual inspection shows the pattern: the-well-of-ascension/1195800334/")
        base_path = "the-well-of-ascension/1195800334/"
    
    # Base URL for the files
    base_url = "https://files02.tokybook.com/audio/"
    
    # Create download directory
    save_folder = os.path.join("downloads", "the_well_of_ascension")
    os.makedirs(save_folder, exist_ok=True)
    
    # Construct MP3 URLs based on the pattern
    # Pattern appears to be: "[track_number] - [track_title]-[random_numbers].mp3"
    mp3_files = []
    
    for track in tracks:
        # Construct filename
        # Note: The random numbers at the end might be consistent for each track
        # but we'd need to capture them from the actual page loads
        filename = f"{track['number'].zfill(2)} - {track['title']}.mp3"
        mp3_files.append({
            'track': track,
            'filename': filename
        })
    
    print(f"\nPrepared {len(mp3_files)} files for download")
    print("\nNote: This simplified version may not work without the exact MP3 filenames.")
    print("The full version with Selenium is recommended for accurate downloads.")
    
    # Save track list for reference
    tracklist_path = os.path.join(save_folder, "tracklist.txt")
    with open(tracklist_path, 'w') as f:
        f.write("The Well of Ascension - Track List\n")
        f.write("=" * 40 + "\n\n")
        for track in tracks:
            f.write(f"{track['number'].zfill(2)}. {track['title']}\n")
    
    print(f"\nTrack list saved to: {tracklist_path}")
    
    # Alternative approach: Try common patterns
    print("\nAttempting to download with common URL patterns...")
    
    # Try a few different URL patterns
    test_patterns = [
        f"{base_url}{base_path}{{filename}}",
        f"{base_url}{base_path}{{filename_encoded}}",
        f"https://zaudiobooks.com/wp-content/uploads/{{year}}/{{month}}/{{filename}}"
    ]
    
    # Test with first track
    first_track = mp3_files[0]
    test_filename = f"{first_track['track']['number'].zfill(2)} - {first_track['track']['title']}"
    
    for pattern in test_patterns:
        test_url = pattern.format(
            filename=test_filename + ".mp3",
            filename_encoded=test_filename.replace(" ", "%20") + ".mp3",
            year="2024",
            month="01"
        )
        
        print(f"\nTesting URL pattern: {test_url[:50]}...")
        
        try:
            response = requests.head(test_url, timeout=5)
            if response.status_code == 200:
                print("Success! Found working URL pattern")
                break
        except:
            continue
    
    return tracks

def download_with_known_pattern():
    """
    Download using the known pattern from the page analysis
    """
    # Based on the pattern from the WebFetch analysis
    base_url = "https://files02.tokybook.com/audio/the-well-of-ascension/1195800334/"
    
    # Sample URL pattern: "01 - The Well Of Ascension-966596803.mp3"
    # The number suffix appears to be random/unique per file
    
    print("To download the files, you would need:")
    print("1. The exact MP3 filenames including the number suffix")
    print("2. Or use the Selenium version to capture them dynamically")
    print(f"\nBase URL: {base_url}")
    print("Pattern: [number] - [title]-[suffix].mp3")

def main():
    url = "https://zaudiobooks.com/the-well-of-ascension_t1/"
    
    print("Simple Audiobook Scraper")
    print("=" * 40)
    
    tracks = scrape_audiobook_simple(url)
    
    print("\n" + "=" * 40)
    print("Download Instructions:")
    print("1. Use scrape_well_of_ascension.py for automatic download (requires Selenium)")
    print("2. Or manually inspect the page to get exact MP3 filenames")
    
    download_with_known_pattern()

if __name__ == "__main__":
    main()