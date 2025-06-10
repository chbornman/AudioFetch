#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
import asyncio
import os
import shutil
import uuid
from datetime import datetime
import importlib
import re
from urllib.parse import urlparse
import logging
import zipfile
from io import BytesIO
from fastapi.responses import StreamingResponse
import requests
from typing import AsyncGenerator
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Import the existing modules
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from player_info import get_player_info
from downloader import download_tracks

app = FastAPI(title="Audio Downloader", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store download jobs and cancellation flags
download_jobs = {}
cancel_flags = {}
# Store ZIP creation progress
zip_progress = {}

def update_job_progress(job_id: str, completed: int, failed: int):
    """Update job progress during download."""
    if job_id in download_jobs:
        job = download_jobs[job_id]
        if job.get('progress'):
            job['progress']['completed'] = completed
            job['progress']['failed'] = failed

class DownloadRequest(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    plugin: Optional[str] = None
    workers: int = 5
    download_mode: str = "server"  # "server" or "browser"

class DownloadStatus(BaseModel):
    job_id: str
    status: str  # pending, detecting, downloading, zipping, completed, error
    message: Optional[str] = None
    progress: Optional[Dict] = None
    result: Optional[Dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_name: Optional[str] = None
    download_mode: Optional[str] = None
    zip_ready: Optional[bool] = None

def detect_plugin(url):
    """Detect which audio streaming plugin a website is using."""
    import requests
    from bs4 import BeautifulSoup
    
    try:
        response = requests.get(str(url), timeout=30)
        response.raise_for_status()
        html = response.text.lower()
        html_original = response.text
        
        detections = []
        
        if 'plyr' in html or 'new plyr' in html:
            detections.append(('plyr', True))
        
        if 'howler' in html or 'howl(' in html or 'howler.js' in html:
            detections.append(('howler', False))
        
        mediaelement_patterns = [
            'mediaelement', 'mejsplayer', 'mejs', 'mejs-',
            'wp-mediaelement', 'mediaelement-and-player',
            'mediaelementplayer', 'mejs__'
        ]
        if any(pattern in html for pattern in mediaelement_patterns):
            detections.append(('mediaelement', False))
        
        if 'video-js' in html or 'videojs' in html:
            detections.append(('videojs', False))
        
        if 'jwplayer' in html or 'jwplatform' in html:
            detections.append(('jwplayer', False))
        
        if '<audio' in html:
            detections.append(('html5audio', False))
        
        if 'soundcloud.com' in html or 'soundcloud-widget' in html:
            detections.append(('soundcloud', False))
        
        if 'spotify.com/embed' in html:
            detections.append(('spotify', False))
        
        soup = BeautifulSoup(html_original, 'html.parser')
        mp3_links = soup.find_all(lambda tag: 
            (tag.name == 'a' and tag.get('href', '').endswith('.mp3')) or
            (tag.get('data-url', '').endswith('.mp3'))
        )
        if mp3_links:
            detections.append(('simple_mp3', True))
        
        return detections
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error detecting plugin: {str(e)}")

def generate_name_from_url(url: str) -> str:
    """Generate a name from URL if none provided."""
    parsed_url = urlparse(url)
    path_parts = [p for p in parsed_url.path.strip('/').split('/') if p]
    
    if path_parts:
        name = re.sub(r'[^\w\s-]', '', path_parts[-1])
        name = re.sub(r'[-\s]+', '-', name)
    else:
        name = parsed_url.netloc.replace('.', '-')
    
    if not name or len(name) < 3:
        from datetime import datetime
        name = f"audio-download-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    return name

def process_download(job_id: str, request: DownloadRequest):
    """Background task to process download."""
    job = download_jobs[job_id]
    
    try:
        # Generate name if not provided
        if not request.name:
            request.name = generate_name_from_url(str(request.url))
            job['status'] = 'detecting'
            job['message'] = f"Generated name: {request.name}"
            print(f"[Job {job_id[:8]}] Generated name: {request.name}")
        
        # Detect plugin if not specified
        if not request.plugin:
            job['status'] = 'detecting'
            job['message'] = "Detecting audio player..."
            print(f"[Job {job_id[:8]}] Detecting audio player...")
            detections = detect_plugin(request.url)
            
            if not detections:
                raise Exception("Could not detect any audio player on this page")
            
            # Find first supported plugin
            supported = [d for d in detections if d[1]]
            if not supported:
                unsupported_names = [get_player_info(d[0])['name'] for d in detections]
                raise Exception(f"Detected unsupported players: {', '.join(unsupported_names)}")
            
            request.plugin = supported[0][0]
            job['message'] = f"Detected player: {get_player_info(request.plugin)['name']}"
            print(f"[Job {job_id[:8]}] Detected player: {get_player_info(request.plugin)['name']}")
        
        # Import and run the scraper
        job['status'] = 'downloading'
        job['message'] = f"Scraping with {request.plugin} plugin..."
        print(f"[Job {job_id[:8]}] Scraping with {request.plugin} plugin...")
        
        if request.plugin == 'simple' or request.plugin == 'simple_mp3':
            module_name = 'simple_scrape_mp3'
        elif request.plugin == 'plyr':
            module_name = 'scrape_plyr'
        else:
            raise Exception(f"Unknown plugin: {request.plugin}")
        
        try:
            scraper = importlib.import_module(module_name)
        except ImportError as e:
            raise Exception(f"Failed to import scraper module '{module_name}': {str(e)}")
        
        try:
            tracks = scraper.scrape(str(request.url), request.name, request.name)
        except Exception as e:
            raise Exception(f"Scraper error: {str(e)}")
        
        if not tracks:
            raise Exception("No tracks found to download")
        
        job['message'] = f"Found {len(tracks)} tracks. Downloading..."
        job['progress'] = {'total': len(tracks), 'completed': 0, 'failed': 0}
        job['download_mode'] = request.download_mode
        job['download_name'] = request.name
        job['tracks'] = tracks  # Store tracks for browser mode
        print(f"[Job {job_id[:8]}] Found {len(tracks)} tracks. Starting download in {request.download_mode} mode...")
        
        if request.download_mode == "browser":
            # For browser mode, start creating the ZIP immediately
            job['status'] = 'zipping'
            job['message'] = f"Creating ZIP file for {len(tracks)} tracks..."
            job['zip_ready'] = False
            print(f"[Job {job_id[:8]}] Browser mode: Starting ZIP creation...")
            
            # Create ZIP synchronously in the background task
            try:
                # Use asyncio.run to execute the async function
                import asyncio
                zip_buffer = asyncio.run(create_streaming_zip(tracks, request.name, request.workers, job_id))
                job['zip_buffer'] = zip_buffer
                job['zip_ready'] = True
                job['status'] = 'completed'
                job['message'] = f"ZIP ready for download ({len(tracks)} tracks)"
                job['result'] = {
                    'successful': len(tracks),
                    'failed': 0,
                    'mode': 'browser',
                    'zip_size': zip_buffer.getbuffer().nbytes
                }
                job['completed_at'] = datetime.now()
                print(f"[Job {job_id[:8]}] Browser mode: ZIP ready for download")
            except Exception as e:
                job['status'] = 'error'
                job['message'] = f"Failed to create ZIP: {str(e)}"
                job['completed_at'] = datetime.now()
                logger.error(f"[Job {job_id[:8]}] ZIP creation failed: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            # Download tracks with progress callback and cancellation check
            def update_progress(completed, failed):
                # Check if cancelled
                if cancel_flags.get(job_id, False):
                    logger.info(f"[Job {job_id[:8]}] Download cancelled")
                    return False  # Signal to stop downloading
                
                job['progress']['completed'] = completed
                job['progress']['failed'] = failed
                logger.info(f"[Job {job_id[:8]}] Progress: {completed}/{len(tracks)} completed, {failed} failed")
                return True  # Continue downloading
            
            result = download_tracks(
                tracks, 
                request.name,
                prefix=request.name if request.plugin in ['simple', 'simple_mp3'] else None,
                max_workers=request.workers,
                progress_callback=update_progress,
                job_id=job_id
            )
            
            job['status'] = 'completed'
            job['message'] = f"Downloaded {result['successful']} tracks successfully"
            job['result'] = result
            job['completed_at'] = datetime.now()
            print(f"[Job {job_id[:8]}] Completed: {result['successful']} successful, {result['failed']} failed")
        
    except Exception as e:
        import traceback
        job['status'] = 'error'
        job['message'] = str(e)
        job['completed_at'] = datetime.now()
        print(f"[Job {job_id[:8]}] Error: {str(e)}")
        print(traceback.format_exc())

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open('static/index.html', 'r') as f:
        return f.read()

@app.post("/api/download", response_model=DownloadStatus)
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start a new download job."""
    job_id = str(uuid.uuid4())
    
    # Check if directory already exists
    if request.name:
        downloads_dir = os.path.join('downloads', request.name)
        if os.path.exists(downloads_dir):
            raise HTTPException(
                status_code=400,
                detail=f"Directory 'downloads/{request.name}' already exists. Please choose a different name."
            )
    
    # Create job entry
    download_jobs[job_id] = {
        'job_id': job_id,
        'status': 'pending',
        'message': 'Job created',
        'progress': None,
        'result': None,
        'created_at': datetime.now(),
        'completed_at': None,
        'request': request
    }
    
    # Start background task
    background_tasks.add_task(process_download, job_id, request)
    
    return DownloadStatus(**download_jobs[job_id])

@app.get("/api/status/{job_id}", response_model=DownloadStatus)
async def get_status(job_id: str):
    """Get the status of a download job."""
    if job_id not in download_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return DownloadStatus(**download_jobs[job_id])

@app.get("/api/jobs", response_model=List[DownloadStatus])
async def list_jobs():
    """List all download jobs."""
    return [DownloadStatus(**job) for job in download_jobs.values()]

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a completed job."""
    if job_id not in download_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = download_jobs[job_id]
    if job['status'] in ['pending', 'detecting', 'downloading']:
        raise HTTPException(status_code=400, detail="Cannot delete active job")
    
    del download_jobs[job_id]
    if job_id in cancel_flags:
        del cancel_flags[job_id]
    return {"message": "Job cleared"}

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel an active job."""
    if job_id not in download_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = download_jobs[job_id]
    if job['status'] not in ['pending', 'detecting', 'downloading']:
        raise HTTPException(status_code=400, detail="Job is not active")
    
    # Set cancel flag
    cancel_flags[job_id] = True
    job['status'] = 'cancelled'
    job['message'] = 'Download cancelled by user'
    job['completed_at'] = datetime.now()
    
    logger.info(f"[Job {job_id[:8]}] Cancelled by user")
    
    return {"message": "Job cancelled"}

@app.get("/api/downloads")
async def list_downloads():
    """List available downloads."""
    downloads_dir = 'downloads'
    if not os.path.exists(downloads_dir):
        return []
    
    downloads = []
    for dir_name in os.listdir(downloads_dir):
        dir_path = os.path.join(downloads_dir, dir_name)
        if os.path.isdir(dir_path):
            # Support multiple audio formats
            audio_extensions = ('.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac')
            files = [f for f in os.listdir(dir_path) if f.lower().endswith(audio_extensions)]
            downloads.append({
                'name': dir_name,
                'files': len(files),
                'size': sum(os.path.getsize(os.path.join(dir_path, f)) for f in files),
                'created': datetime.fromtimestamp(os.path.getctime(dir_path))
            })
    
    # Sort by creation date, most recent first
    downloads.sort(key=lambda x: x['created'], reverse=True)
    
    return downloads

@app.delete("/api/downloads/{name}")
async def delete_download(name: str):
    """Delete a download directory."""
    dir_path = os.path.join('downloads', name)
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail="Download not found")
    
    shutil.rmtree(dir_path)
    return {"message": "Download deleted"}

@app.get("/api/downloads/{name}/zip")
async def download_as_zip(name: str):
    """Download all files in a directory as a ZIP file."""
    logger.info(f"Attempting to download zip for: {name}")
    dir_path = os.path.join('downloads', name)
    logger.info(f"Looking for directory: {dir_path}")
    if not os.path.exists(dir_path):
        logger.error(f"Directory not found: {dir_path}")
        # List what directories do exist
        if os.path.exists('downloads'):
            existing = os.listdir('downloads')
            logger.info(f"Existing downloads: {existing}")
        raise HTTPException(status_code=404, detail="Download not found")
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    audio_extensions = ('.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac')
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file in os.listdir(dir_path):
            if file.lower().endswith(audio_extensions):
                file_path = os.path.join(dir_path, file)
                zip_file.write(file_path, file)
    
    zip_buffer.seek(0)
    
    # Get the size of the buffer for Content-Length
    zip_size = zip_buffer.getbuffer().nbytes
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={name}.zip",
            "Content-Length": str(zip_size)
        }
    )

async def download_file_to_memory(session: aiohttp.ClientSession, url: str, filename: str):
    """Download a single file to memory."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            content = await response.read()
            return (filename, content, None)
    except Exception as e:
        logger.error(f"Failed to download {filename}: {str(e)}")
        return (filename, None, str(e))

async def create_streaming_zip(tracks: List[Dict], name: str, max_workers: int = 5, job_id: str = None):
    """Create a ZIP file in memory from track URLs with progress tracking."""
    zip_buffer = BytesIO()
    total_tracks = len(tracks)
    completed = 0
    failed = 0
    
    # Initialize progress tracking
    if job_id:
        zip_progress[job_id] = {
            'total': total_tracks,
            'completed': 0,
            'failed': 0,
            'status': 'downloading'
        }
    
    logger.info(f"Starting ZIP creation for {total_tracks} tracks")
    
    async with aiohttp.ClientSession() as session:
        # Download files in batches
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i in range(0, len(tracks), max_workers):
                batch = tracks[i:i + max_workers]
                batch_start = i
                tasks = []
                
                logger.info(f"Processing batch {i//max_workers + 1}/{(total_tracks + max_workers - 1)//max_workers} (tracks {i+1}-{min(i+len(batch), total_tracks)})")
                
                for track in batch:
                    filename = track.get('filename', track['url'].split('/')[-1])
                    if not any(filename.endswith(ext) for ext in ['.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac']):
                        filename += '.mp3'
                    tasks.append(download_file_to_memory(session, track['url'], filename))
                
                results = await asyncio.gather(*tasks)
                
                for idx, (filename, content, error) in enumerate(results):
                    if content:
                        zip_file.writestr(filename, content)
                        completed += 1
                        logger.info(f"Added to ZIP: {filename} ({completed}/{total_tracks})")
                    else:
                        failed += 1
                        logger.warning(f"Failed to download {filename}: {error} ({completed}/{total_tracks} completed, {failed} failed)")
                    
                    # Update progress
                    if job_id:
                        zip_progress[job_id]['completed'] = completed
                        zip_progress[job_id]['failed'] = failed
    
    # Mark as complete
    if job_id:
        zip_progress[job_id]['status'] = 'complete'
    
    logger.info(f"ZIP creation complete: {completed} successful, {failed} failed out of {total_tracks} total")
    
    zip_buffer.seek(0)
    return zip_buffer

@app.get("/api/jobs/{job_id}/zip-progress")
async def get_zip_progress(job_id: str):
    """Get ZIP creation progress for a job."""
    if job_id not in zip_progress:
        return {"status": "not_started"}
    return zip_progress[job_id]

@app.get("/api/jobs/{job_id}/download-zip")
async def download_job_as_zip(job_id: str):
    """Download a browser mode job as ZIP."""
    if job_id not in download_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = download_jobs[job_id]
    
    # Check if job is in browser mode
    if job.get('download_mode') != 'browser':
        raise HTTPException(status_code=400, detail="This job is not in browser download mode")
    
    # Check if ZIP is ready
    if not job.get('zip_ready', False):
        raise HTTPException(status_code=425, detail="ZIP file is still being created. Please wait.")
    
    if not job.get('zip_buffer'):
        raise HTTPException(status_code=500, detail="ZIP buffer not found")
    
    # Get the pre-created ZIP buffer
    zip_buffer = job['zip_buffer']
    zip_buffer.seek(0)  # Reset to beginning
    
    # Get the size for Content-Length
    zip_size = zip_buffer.getbuffer().nbytes
    logger.info(f"Serving pre-created ZIP, size: {zip_size} bytes")
    
    # Clean up progress tracking
    if job_id in zip_progress:
        del zip_progress[job_id]
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={job['download_name']}.zip",
            "Content-Length": str(zip_size)
        }
    )

@app.post("/api/stream-download")
async def stream_download(request: DownloadRequest):
    """Stream download directly to browser as ZIP without saving to server."""
    try:
        # Generate name if not provided
        if not request.name:
            request.name = generate_name_from_url(str(request.url))
            logger.info(f"Generated name: {request.name}")
        
        # Detect plugin if not specified
        if not request.plugin:
            logger.info("Detecting audio player...")
            detections = detect_plugin(request.url)
            
            if not detections:
                raise HTTPException(status_code=400, detail="Could not detect any audio player on this page")
            
            # Find first supported plugin
            supported = [d for d in detections if d[1]]
            if not supported:
                unsupported_names = [get_player_info(d[0])['name'] for d in detections]
                raise HTTPException(status_code=400, detail=f"Detected unsupported players: {', '.join(unsupported_names)}")
            
            request.plugin = supported[0][0]
            logger.info(f"Detected player: {get_player_info(request.plugin)['name']}")
        
        # Import and run the scraper
        logger.info(f"Scraping with {request.plugin} plugin...")
        
        if request.plugin == 'simple' or request.plugin == 'simple_mp3':
            module_name = 'simple_scrape_mp3'
        elif request.plugin == 'plyr':
            module_name = 'scrape_plyr'
        else:
            raise HTTPException(status_code=400, detail=f"Unknown plugin: {request.plugin}")
        
        try:
            scraper = importlib.import_module(module_name)
        except ImportError as e:
            raise HTTPException(status_code=400, detail=f"Failed to import scraper module '{module_name}': {str(e)}")
        
        try:
            tracks = scraper.scrape(str(request.url), request.name, request.name)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Scraper error: {str(e)}")
        
        if not tracks:
            raise HTTPException(status_code=400, detail="No tracks found to download")
        
        logger.info(f"Found {len(tracks)} tracks. Creating streaming ZIP...")
        
        # Create ZIP in memory and stream it
        zip_buffer = await create_streaming_zip(tracks, request.name, request.workers)
        
        # Get the size of the buffer for Content-Length
        zip_size = zip_buffer.getbuffer().nbytes
        logger.info(f"ZIP created, size: {zip_size} bytes")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={request.name}.zip",
                "Content-Length": str(zip_size)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream download error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Run on startup."""
    print("=" * 60)
    print("Audio Downloader Web App Started")
    print("Access the app at: http://localhost:8000")
    print("=" * 60)

@app.on_event("startup")
async def startup_event():
    """Log startup message."""
    logger.info("Audio Downloader API started successfully!")
    logger.info("Access the web interface at http://localhost:8000")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")