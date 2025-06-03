# Audio Downloader

Command-line tool for downloading audio files from various web-based audio players. The tool automatically detects the type of audio player used on a webpage and extracts all available audio tracks for download.

## Supported Audio Players

### 1. **Plyr-based Players**

- Detects Plyr.js audio players commonly used on audiobook and podcast sites
- Extracts tracks from JavaScript arrays and playlists
- Supports sites that use APIs to fetch MP3 URLs dynamically
- Handles both direct MP3 links and API-based track loading

### 2. **Simple MP3 Links**

- Finds all direct MP3 links on a page
- Searches for `<a>` tags with `href` attributes ending in `.mp3`
- Detects elements with `data-url` attributes pointing to MP3 files
- Ideal for simple download pages or file listings

**Note:** Many sites using MediaElement.js (WordPress default player) expose direct MP3 links that can be downloaded using the simple MP3 scraper. If MediaElement.js is detected, try using `-p simple_mp3`.

## Features

- **Auto-detection**: Automatically identifies which type of audio player is used
- **Manual override**: Option to specify which scraper to use
- **Parallel downloads**: Downloads multiple files simultaneously (default: 5 workers)
- **Progress tracking**: Real-time progress bars for each download
- **Smart naming**: Preserves track names from the website or uses original filenames
- **Directory safety**: Prevents accidental overwrites by checking for existing directories
- **Comprehensive logging**: Clear status updates throughout the scraping and download process

## Prerequisites

- Python 3.7+
- pip (Python package manager)

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
python main.py URL [NAME] [-p PLUGIN] [-d DIRECTORY] [-w WORKERS]
```

### Command Line Arguments

- **URL**: The webpage address containing audio files (required)
- **NAME**: Name for the download folder (optional - auto-generated if not provided)
- **-p/--plugin**: Manually specify which plugin to use:
  - `plyr` - For Plyr.js audio players
  - `simple_mp3` - For direct MP3 links (also works for many MediaElement.js sites)
- **-d/--directory**: Custom directory name (defaults to NAME)
- **-w/--workers**: Number of parallel downloads (default: 5)

### Automatic Naming

If no name is provided, the script will automatically generate one based on:

1. The last segment of the URL path (e.g., `/example-audio/` → `example-audio`)
2. The domain name if no path exists (e.g., `example.com` → `example-com`)
3. A timestamp if neither provides a good name (e.g., `audio-download-20240115-143022`)

### Examples

**Simplest usage (auto-detect everything):**

```bash
python main.py https://example.com/audio-streamer-example
```

Auto-detects the player type and creates `downloads/audio-streamer-example/` based on the URL.

**Specify a custom name:**

```bash
python main.py https://example.com/audio-streamer-example my-audiobook
```

Downloads to `downloads/my-audiobook/` regardless of the URL structure.

**Force specific scraper:**

```bash
python main.py https://example.com/audio-streamer-example my-audiobook -p plyr
```

Forces the use of the Plyr scraper, useful if auto-detection fails.

**Control parallel downloads:**

```bash
python main.py https://example.com/audio-streamer-example my-audiobook -w 10
```

Downloads 10 files simultaneously for faster completion.

**Reduce parallel downloads (for rate-limited sites):**

```bash
python main.py https://example.com/audio-streamer-example -w 1
```

Downloads only one file at a time to avoid overwhelming the server.

### Output Example

```
Auto-detecting plugin...
Detected plugin: plyr
[Plyr Scraper] Starting scrape of: https://example.com/audiobook
Fetching page content...
Analyzing page for Plyr audio tracks...

Fetching MP3 URLs from API for 26 tracks...

Found 27 audio tracks:
   1. Introduction                          https://example.com/files/intro.mp3
   2. Chapter 01 - The Beginning           https://example.com/files/chapter01.mp3
   3. Chapter 02 - The Journey             https://example.com/files/chapter02.mp3
   ...

Downloading to: downloads/my-audiobook/
Total tracks to download: 27
Parallel downloads: 5
--------------------------------------------------------------------------------
[ 1/27] Introduction.mp3                         [██████████████████████████████] 100.0% ✓ Complete (1.2 MB)
[ 2/27] Chapter-01-The-Beginning.mp3             [████████████████░░░░░░░░░░░░░░]  55.3% 35.6 MB/64.4 MB
[ 3/27] Chapter-02-The-Journey.mp3               [██████░░░░░░░░░░░░░░░░░░░░░░░░]  21.7% 14.2 MB/65.3 MB
...
```

## How It Works

1. **Plugin Detection**: The main script analyzes the webpage to determine which audio player is being used
2. **Track Extraction**: The appropriate scraper extracts track metadata (names, URLs, etc.)
3. **URL Resolution**: For Plyr players, the scraper may need to make API calls to get actual MP3 URLs
4. **Download Management**: The common downloader handles all files with consistent progress tracking
5. **File Organization**: Files are saved to `downloads/[name]/` with sanitized filenames

## Architecture

The project uses a modular plugin architecture:

- **`main.py`**: Entry point that detects plugins and coordinates the process
- **`scrape_plyr.py`**: Handles Plyr.js-based audio players
- **`simple_scrape_mp3.py`**: Handles direct MP3 links
- **`downloader.py`**: Common download manager with progress tracking

## Adding New Scrapers

To support a new audio player type:

1. Create a new scraper file (e.g., `scrape_newplayer.py`)
2. Implement a `scrape(url, prefix, directory)` function that returns a list of track dictionaries
3. Each track dictionary should have at minimum: `{'url': 'http://...', 'name': 'Track Name'}`
4. Update the detection logic in `main.py`

## Troubleshooting

**Auto-detection fails:**

- Use the `-p` flag to manually specify the plugin
- Check if the site uses a player type not yet supported

**Downloads fail:**

- Some sites may require authentication or have rate limiting
- Try reducing parallel downloads with `-w 1` or `-w 2`
- Check if the MP3 URLs are region-restricted

**Directory already exists:**

- The script prevents accidental overwrites
- Remove the existing directory or choose a different name

## Future Improvements

Here are planned enhancements for the audio downloader:

### Additional Player Support

- **MediaElement.js**: Another popular HTML5 audio/video player
- **Video.js**: Widely used open-source player
- **Howler.js**: Web audio library used by many sites
- **JW Player**: Commercial player with various protection mechanisms
- **Spotify/Apple Music embeds**: For publicly available podcasts

### Future Features

- **Playlist support**: Save M3U/PLS playlists along with downloads
- **Metadata extraction**: Save track information, album art, and descriptions
- **Rate limiting**: Automatic adjustment based on server responses
- **Proxy support**: Route downloads through proxy servers

### Technical Enhancements

- **Async downloads**: Use asyncio for better performance
- **API mode**: Run as a service with REST API
- **GUI version**: Simple graphical interface for non-technical users

## Contributing

Contributions are welcome! If you'd like to add support for a new player or feature:

1. Fork the repository
2. Create a feature branch
3. Add your scraper or enhancement
4. Submit a pull request

## Web Application with Docker

The project now includes a web interface that can be run as a containerized application using Docker.

### Docker Setup

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access the web interface:**
   Open your browser and navigate to `http://localhost:8000`

3. **View logs:**
   ```bash
   docker-compose logs -f
   ```

4. **Stop the application:**
   ```bash
   docker-compose down
   ```

### Web Interface Features

- **Simple HTML/CSS frontend** - No JavaScript frameworks required
- **Real-time progress tracking** - Monitor download progress for all tracks
- **Job management** - View active and completed download jobs
- **Download management** - Browse and delete completed downloads
- **Auto-detection** - Same plugin detection as the CLI version
- **Background processing** - Downloads continue even if you close the browser

### Docker Configuration

The `docker-compose.yml` file:
- Maps port 8000 for web access
- Mounts the `downloads` directory as a volume for persistent storage
- Auto-restarts the container unless explicitly stopped

### API Endpoints

The FastAPI backend provides these endpoints:
- `GET /` - Main web interface
- `POST /api/download` - Start a new download job
- `GET /api/status/{job_id}` - Check job status
- `GET /api/jobs` - List all jobs
- `DELETE /api/jobs/{job_id}` - Delete a completed job
- `GET /api/downloads` - List completed downloads
- `DELETE /api/downloads/{name}` - Delete a download

## License

This script is provided as-is under the MIT License. Feel free to modify and distribute.
