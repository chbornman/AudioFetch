import argparse
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

def find_audio_tags(url, prefix, directory):
    print(f"Fetching content from: {url}")
    response = requests.get(url)
    print("Content fetched successfully.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    print("Soup is ready.")

    # Find all 'a' tags and elements with 'data-url'
    href_elements = soup.find_all('a')
    data_url_elements = soup.select('[data-url]')
    elements = href_elements + data_url_elements

    print(f"Found {len(elements)} elements to process on the page.")

    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Use ThreadPoolExecutor to download files concurrently
    with ThreadPoolExecutor() as executor:
        for i, element in enumerate(elements, start=1):
            # Determine the attribute to use based on the type of element
            attribute = 'href' if element.name == 'a' else 'data-url'
            url_value = element.get(attribute)

            # Print the value of the attribute
            print(f"{attribute} value for element {i}: {url_value}")

            if url_value is not None and url_value.endswith('.mp3'):
                # Make sure the url_value is an absolute URL
                url_value = urljoin(url, url_value)

                # Create filename using the index, the prefix, and the directory
                filename = os.path.join(directory, f"{prefix}_{i}.mp3")

                print(f"\nStarting download of element {i} from URL: {url_value}")
                executor.submit(download_file, url_value, filename)

# Set up command line arguments
parser = argparse.ArgumentParser(description='Download all audio from a webpage.')
parser.add_argument('url', help='URL of the webpage to scrape')
parser.add_argument('prefix', help='Prefix for all file names')
parser.add_argument('-d', '--directory', help='Directory to put the downloaded files', default=None)
args = parser.parse_args()

# If directory is not given, use prefix as the directory name
if args.directory is None:
    args.directory = args.prefix

# Find and download audio from the webpage
find_audio_tags(args.url, args.prefix, args.directory)
