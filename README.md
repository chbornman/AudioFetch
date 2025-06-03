# Audio Downloader Script

A simple command-line tool to scrape a webpage for .mp3 links and download them.
It finds all `<a>` tags that link to .mp3 files or elements that use `data-url` for audio sources, and then downloads each file.

## Features
- Preserves original filenames from the server.
- Optional prefix for downloaded files.
- Concurrent downloads to save time.
- Customizable download directory.

## Prerequisites
- Python 3.7+
Make sure you have Python 3.7 or later installed.

## Setup

### Using a Virtual Environment (Recommended)

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment:**
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Without Virtual Environment

Install the required packages directly:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Script

With virtual environment activated:
```bash
python download_audiobook.py [URL] [PREFIX] [-d DIRECTORY]
```

### Command Line Arguments

```bash
python download_audiobook.py [URL] [PREFIX] [-d DIRECTORY]
```

- **URL**: The webpage address you want to scrape for .mp3 files.
- **PREFIX** (optional): A prefix for downloaded files (e.g., `podcast_`).
- **-d/--directory** (optional): The folder to store the files. Defaults to:
  - The prefix name, if specified
  - "downloads", if prefix is empty

### Examples

**Basic:**
```bash
python download_audiobook.py https://example.com
```
This downloads all .mp3 files found on https://example.com into a folder named downloads, using their original filenames without any added prefix.

**With Prefix:**
```bash
python download_audiobook.py https://example.com myprefix
```
This downloads all .mp3 files found on https://example.com into a folder named myprefix, each with myprefix_ prepended to the original filename.

**Custom Directory:**
```bash
python download_audiobook.py https://example.com myprefix -d "audio_files"
```
This downloads all .mp3 files into a folder named audio_files, each with myprefix_ prepended to the original filename.

## How It Works
Scrape the URL

Uses requests to fetch HTML from the given URL.
Parses the HTML with BeautifulSoup.
Locate Audio Links

Searches for:
<a> tags with href attributes ending in .mp3.
Any element with a data-url attribute ending in .mp3.
Build Final Paths

Extracts the original filename from the URL using Python’s os.path.basename.
Optionally adds a prefix to the file (e.g., myprefix_).
Joins it with the specified or default directory.
Download Files (Concurrent)

Uses a ThreadPoolExecutor to download files in parallel, speeding up retrieval.
Troubleshooting
Timeout or Connection Errors:
If a download takes too long or fails, you’ll see a timeout or request exception message. Increase or decrease the timeout in the download_file function if needed.

Missing Files:
If some .mp3 files aren't downloaded, make sure they're actually direct .mp3 links (some sites hide or dynamically generate URLs).

License
This script is provided as-is under the MIT License (or any license of your choosing). Feel free to modify and distribute.

