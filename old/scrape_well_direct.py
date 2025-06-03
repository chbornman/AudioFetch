import os
import requests
from bs4 import BeautifulSoup
import time

def download_audiobook():
    """
    Direct download approach for The Well of Ascension audiobook
    """
    
    # First, get the track list
    url = "https://zaudiobooks.com/the-well-of-ascension_t1/"
    print(f"Fetching track list from: {url}")
    
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
    
    # Create download directory
    save_folder = os.path.join("downloads", "the_well_of_ascension")
    os.makedirs(save_folder, exist_ok=True)
    
    # Based on the analysis, the MP3 files follow this pattern:
    # Base URL: https://files02.tokybook.com/audio/the-well-of-ascension/1195800334/
    # File pattern: "01 - The Well Of Ascension-966596803.mp3"
    
    base_url = "https://files02.tokybook.com/audio/the-well-of-ascension/1195800334/"
    
    # Common suffixes for this audiobook (these would need to be discovered)
    # For now, we'll try to construct URLs and test them
    
    print("\nAttempting to download tracks...")
    print("Note: This requires knowing the exact filenames with their suffixes.")
    
    # Save track list
    tracklist_path = os.path.join(save_folder, "tracklist.txt")
    with open(tracklist_path, 'w', encoding='utf-8') as f:
        f.write("The Well of Ascension - Track List\n")
        f.write("=" * 40 + "\n\n")
        for track in tracks:
            f.write(f"{track['number'].zfill(2)}. {track['title']}\n")
    
    print(f"\nTrack list saved to: {tracklist_path}")
    
    # Try to download with constructed URLs
    # The actual suffixes would need to be obtained from inspecting the page
    # or using browser developer tools
    
    # For demonstration, let's try a few common patterns
    for i, track in enumerate(tracks[:3]):  # Test first 3 tracks
        track_num = track['number'].zfill(2)
        
        # Try different filename patterns
        test_filenames = [
            f"{track_num} - The Well Of Ascension.mp3",
            f"{track_num} - {track['title']}.mp3",
            f"{track_num} - The Well Of Ascension-{i}.mp3",
        ]
        
        for filename in test_filenames:
            test_url = base_url + filename.replace(" ", "%20")
            
            print(f"\nTesting: {filename}")
            
            try:
                response = requests.head(test_url, timeout=5)
                if response.status_code == 200:
                    print(f"Found valid URL!")
                    # Download the file
                    download_file(test_url, os.path.join(save_folder, filename))
                    break
                else:
                    print(f"Status {response.status_code} - not found")
            except Exception as e:
                print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("To download all files, you would need:")
    print("1. The exact filename suffixes for each track")
    print("2. These can be found by:")
    print("   - Using browser developer tools (Network tab)")
    print("   - Clicking each track and capturing the URL")
    print("   - Using the Selenium version of the scraper")

def download_file(url, filepath):
    """Download a single file with progress indicator"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filepath, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        
        print(f"\nSaved: {os.path.basename(filepath)}")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def manual_download_helper():
    """
    Helper function to download if you have the exact URLs
    """
    print("\n" + "=" * 60)
    print("MANUAL DOWNLOAD HELPER")
    print("=" * 60)
    print("\nIf you have the exact MP3 URLs, you can add them here:")
    print("\nExample format:")
    print('urls = [')
    print('    "https://files02.tokybook.com/audio/the-well-of-ascension/1195800334/01 - The Well Of Ascension-966596803.mp3",')
    print('    "https://files02.tokybook.com/audio/the-well-of-ascension/1195800334/02 - The Well Of Ascension-123456789.mp3",')
    print('    # ... add all URLs here')
    print(']')
    print("\nThen uncomment the download loop below in the code.")
    
    # Uncomment and populate this list with actual URLs if you have them
    # urls = [
    #     # Add your URLs here
    # ]
    
    # save_folder = os.path.join("downloads", "the_well_of_ascension")
    # os.makedirs(save_folder, exist_ok=True)
    
    # for i, url in enumerate(urls):
    #     filename = url.split('/')[-1].replace("%20", " ")
    #     filepath = os.path.join(save_folder, filename)
    #     print(f"\nDownloading {i+1}/{len(urls)}: {filename}")
    #     download_file(url, filepath)

if __name__ == "__main__":
    print("The Well of Ascension - Direct Downloader")
    print("=" * 60)
    
    download_audiobook()
    manual_download_helper()
    
    print("\n" + "=" * 60)
    print("Alternative approaches:")
    print("1. Use browser developer tools to capture MP3 URLs manually")
    print("2. Use a browser extension to download all audio files")
    print("3. Fix the Selenium ChromeDriver issue and use the automated scraper")