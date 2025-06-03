import os
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def scrape_audiobook(url):
    """
    Scrapes audiobook MP3 files from zaudiobooks.com
    Uses Selenium to handle JavaScript-rendered content
    """
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print(f"Loading page: {url}")
        driver.get(url)
        
        # Wait for the playlist to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "plList")))
        
        # Get page source after JavaScript execution
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Extract playlist items
        playlist_items = soup.select('.plItem')
        track_info = []
        
        for item in playlist_items:
            track_num = item.select_one('.plNum').text.strip()
            track_title = item.select_one('.plTitle').text.strip()
            track_info.append({
                'number': track_num.rstrip('.'),
                'title': track_title
            })
        
        print(f"Found {len(track_info)} tracks")
        
        # Create download directory
        book_title = "the_well_of_ascension"
        save_folder = os.path.join("downloads", book_title)
        os.makedirs(save_folder, exist_ok=True)
        
        # For each track, we need to click on it to load the MP3 URL
        mp3_urls = []
        
        for i, track in enumerate(track_info):
            print(f"\nProcessing track {i+1}/{len(track_info)}: {track['title']}")
            
            # Click on the track
            track_elements = driver.find_elements(By.CLASS_NAME, "plItem")
            if i < len(track_elements):
                driver.execute_script("arguments[0].scrollIntoView();", track_elements[i])
                driver.execute_script("arguments[0].click();", track_elements[i])
                
                # Wait a bit for the audio to load
                time.sleep(2)
                
                # Get the current audio source
                audio_element = driver.find_element(By.ID, "audio1")
                mp3_url = audio_element.get_attribute("src")
                
                if mp3_url:
                    mp3_urls.append({
                        'url': mp3_url,
                        'filename': f"{track['number'].zfill(2)} - {track['title']}.mp3"
                    })
                    print(f"Found MP3 URL: {mp3_url}")
                else:
                    print(f"Warning: Could not find MP3 URL for track {i+1}")
        
        # Download all MP3 files
        print(f"\nStarting download of {len(mp3_urls)} files...")
        
        for i, mp3 in enumerate(mp3_urls):
            file_path = os.path.join(save_folder, mp3['filename'])
            
            # Skip if already downloaded
            if os.path.exists(file_path):
                print(f"Skipping {mp3['filename']} - already exists")
                continue
            
            print(f"\nDownloading ({i+1}/{len(mp3_urls)}): {mp3['filename']}")
            
            try:
                response = requests.get(mp3['url'], stream=True)
                response.raise_for_status()
                
                # Get file size if available
                total_size = int(response.headers.get('content-length', 0))
                
                with open(file_path, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(f"\rProgress: {progress:.1f}%", end='', flush=True)
                
                print(f"\nSaved to: {file_path}")
                
            except Exception as e:
                print(f"Error downloading {mp3['filename']}: {e}")
        
        print("\nAll downloads complete!")
        
    finally:
        driver.quit()

def main():
    # The URL for "The Well of Ascension" audiobook
    url = "https://zaudiobooks.com/the-well-of-ascension_t1/"
    
    print("Starting audiobook scraper...")
    print("Note: This script requires Chrome and ChromeDriver to be installed.")
    print("Install with: pip install selenium requests beautifulsoup4")
    
    try:
        scrape_audiobook(url)
    except Exception as e:
        print(f"An error occurred: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Chrome browser is installed")
        print("2. Install ChromeDriver: https://chromedriver.chromium.org/")
        print("3. Make sure ChromeDriver is in your PATH")

if __name__ == "__main__":
    main()