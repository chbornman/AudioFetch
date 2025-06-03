import os
import time
import asyncio
import requests
from playwright.async_api import async_playwright

async def scrape_audiobook_playwright():
    """
    Scrape audiobook using Playwright (alternative to Selenium)
    """
    
    url = "https://zaudiobooks.com/the-well-of-ascension_t1/"
    
    # Create download directory
    save_folder = os.path.join("downloads", "the_well_of_ascension")
    os.makedirs(save_folder, exist_ok=True)
    
    async with async_playwright() as p:
        # Launch browser
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Enable request interception to capture MP3 URLs
        mp3_urls = []
        
        async def capture_requests(request):
            if request.url.endswith('.mp3'):
                mp3_urls.append(request.url)
                print(f"Captured MP3 URL: {request.url}")
        
        page.on('request', capture_requests)
        
        print(f"Loading page: {url}")
        await page.goto(url, wait_until='networkidle')
        
        # Wait for playlist to load
        await page.wait_for_selector('.plList')
        
        # Get all playlist items
        playlist_items = await page.query_selector_all('.plItem')
        print(f"Found {len(playlist_items)} tracks")
        
        # Extract track information
        tracks = []
        for item in playlist_items:
            track_num = await item.query_selector('.plNum')
            track_title = await item.query_selector('.plTitle')
            
            if track_num and track_title:
                num_text = await track_num.inner_text()
                title_text = await track_title.inner_text()
                tracks.append({
                    'number': num_text.strip().rstrip('.'),
                    'title': title_text.strip()
                })
        
        # Click on each track to trigger MP3 loading
        print("\nClicking tracks to capture MP3 URLs...")
        
        for i, item in enumerate(playlist_items):
            print(f"\nProcessing track {i+1}/{len(playlist_items)}")
            
            # Scroll to element
            await item.scroll_into_view_if_needed()
            
            # Click the track
            await item.click()
            
            # Wait for audio to load
            await page.wait_for_timeout(2000)
            
            # Get current audio source
            audio_src = await page.evaluate('''
                () => {
                    const audio = document.getElementById('audio1');
                    return audio ? audio.src : null;
                }
            ''')
            
            if audio_src and audio_src not in mp3_urls:
                mp3_urls.append(audio_src)
                print(f"Found MP3: {audio_src.split('/')[-1]}")
        
        await browser.close()
    
    # Download all MP3 files
    print(f"\n{'='*60}")
    print(f"Found {len(mp3_urls)} unique MP3 URLs")
    print(f"Starting downloads...")
    print(f"{'='*60}")
    
    for i, (track, mp3_url) in enumerate(zip(tracks, mp3_urls)):
        filename = f"{track['number'].zfill(2)} - {track['title']}.mp3"
        filepath = os.path.join(save_folder, filename)
        
        # Skip if already exists
        if os.path.exists(filepath):
            print(f"\nSkipping {filename} - already exists")
            continue
        
        print(f"\nDownloading ({i+1}/{len(mp3_urls)}): {filename}")
        
        try:
            response = requests.get(mp3_url, stream=True)
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
            
            print(f"\nSaved to: {filepath}")
            
        except Exception as e:
            print(f"Error downloading: {e}")
    
    print("\nAll downloads complete!")

def main():
    print("The Well of Ascension - Playwright Scraper")
    print("=" * 60)
    print("\nThis scraper uses Playwright instead of Selenium.")
    print("Install with: pip install playwright")
    print("Then run: playwright install chromium")
    print("=" * 60 + "\n")
    
    try:
        asyncio.run(scrape_audiobook_playwright())
    except ImportError:
        print("Playwright not installed. Install with:")
        print("  pip install playwright")
        print("  playwright install chromium")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()