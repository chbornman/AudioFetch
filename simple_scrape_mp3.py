import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from concurrent.futures import ThreadPoolExecutor

def download_file(url, filename):
    print(f"Starting download from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=60)  # 1 minute timeout
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("Download timed out.")
        return
    except requests.exceptions.RequestException as err:
        print(f"Download failed. Error: {err}")
        return

    print("Download in progress...")
    with open(filename, 'wb') as fd:
        for chunk in response.iter_content(chunk_size=8192):
            fd.write(chunk)
    print(f"Download of {filename} completed.")

def scrape(url, prefix, directory):
    """
    Main entry point for simple MP3 scraping.
    Looks for direct MP3 links in HTML (href and data-url attributes).
    """
    print(f"[Simple MP3 Scraper] Starting scrape of: {url}")
    print(f"Fetching content from: {url}")
    response = requests.get(url)
    print("Content fetched successfully.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    print("Parsing HTML...")

    # Find all 'a' tags and elements with 'data-url'
    href_elements = soup.find_all('a')
    data_url_elements = soup.select('[data-url]')
    elements = href_elements + data_url_elements

    print(f"Found {len(elements)} elements to process on the page.")

    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Count MP3 files found
    mp3_count = 0
    download_tasks = []

    # Use ThreadPoolExecutor to download files concurrently
    with ThreadPoolExecutor() as executor:
        for i, element in enumerate(elements, start=1):
            # Determine the attribute to use based on the type of element
            attribute = 'href' if element.name == 'a' else 'data-url'
            url_value = element.get(attribute)

            if url_value is not None and url_value.endswith('.mp3'):
                mp3_count += 1
                # Make sure the url_value is an absolute URL
                url_value = urljoin(url, url_value)

                # Create filename using the index, the prefix, and the directory
                filename = os.path.join(directory, f"{prefix}_{mp3_count:03d}.mp3")

                print(f"\nFound MP3 #{mp3_count}: {url_value}")
                download_tasks.append(executor.submit(download_file, url_value, filename))
    
    print(f"\n[Simple MP3 Scraper] Found {mp3_count} MP3 files")
    if mp3_count == 0:
        print("No direct MP3 links found. This site might use a different audio plugin.")
    else:
        print(f"All downloads queued. Files will be saved to: {directory}/")

# Allow script to be run standalone for testing
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Simple MP3 link scraper')
    parser.add_argument('url', help='URL of the webpage to scrape')
    parser.add_argument('prefix', help='Prefix for all file names')
    parser.add_argument('-d', '--directory', help='Directory to put the downloaded files', default=None)
    args = parser.parse_args()
    
    if args.directory is None:
        args.directory = args.prefix
    
    scrape(args.url, args.prefix, args.directory)
