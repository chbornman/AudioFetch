#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, AsyncGenerator
import asyncio
import os
import shutil
import uuid
from datetime import datetime, timedelta
import importlib
import re
from urllib.parse import urlparse
import logging
import zipfile
from io import BytesIO
import aiohttp
import json
import secrets
from passlib.context import CryptContext
import jwt
from jwt import PyJWTError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('audiofetch.log')
    ]
)
logger = logging.getLogger(__name__)

# Import the existing modules
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from player_info import get_player_info
from downloader import download_tracks

app = FastAPI(title="AudioFetch", version="2.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Security setup
security = HTTPBasic()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Change this!

# Store active websocket connections
active_connections: Dict[str, WebSocket] = {}

# Store download jobs and cancellation flags
download_jobs = {}
cancel_flags = {}

class DownloadRequest(BaseModel):
    url: HttpUrl
    name: Optional[str] = None
    plugin: Optional[str] = None
    workers: int = 5
    download_mode: str = "browser"  # "server" or "browser"
    auth_token: Optional[str] = None  # For server mode

class DownloadStatus(BaseModel):
    job_id: str
    status: str  # pending, detecting, downloading, streaming, completed, error, cancelled
    message: Optional[str] = None
    progress: Optional[Dict] = None
    result: Optional[Dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_name: Optional[str] = None
    download_mode: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    password: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return False
        return True
    except PyJWTError:
        return False

async def broadcast_job_update(job_id: str, job_data: dict):
    """Broadcast job updates to all connected websockets."""
    # Create a serializable copy of the job data
    serializable_data = job_data.copy()
    
    # Convert datetime objects to ISO format strings
    if 'created_at' in serializable_data and isinstance(serializable_data['created_at'], datetime):
        serializable_data['created_at'] = serializable_data['created_at'].isoformat()
    if 'completed_at' in serializable_data and isinstance(serializable_data['completed_at'], datetime):
        serializable_data['completed_at'] = serializable_data['completed_at'].isoformat()
    
    # Remove non-serializable objects
    serializable_data.pop('request', None)
    serializable_data.pop('tracks', None)
    
    message = {
        "type": "job_update",
        "job_id": job_id,
        "data": serializable_data
    }
    
    disconnected = []
    for conn_id, websocket in active_connections.items():
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send to websocket {conn_id}: {e}")
            disconnected.append(conn_id)
    
    # Clean up disconnected websockets
    for conn_id in disconnected:
        active_connections.pop(conn_id, None)

async def stream_zip_truly(tracks: List[Dict], job_id: str) -> AsyncGenerator[bytes, None]:
    """
    True streaming ZIP generation - sends data as soon as it's downloaded.
    """
    import struct
    import zlib
    import time
    
    def create_local_header(filename: str, size: int, crc: int) -> bytes:
        """Create ZIP local file header"""
        dt = time.localtime()
        dosdate = (dt.tm_year - 1980) << 9 | dt.tm_mon << 5 | dt.tm_mday
        dostime = dt.tm_hour << 11 | dt.tm_min << 5 | (dt.tm_sec // 2)
        
        header = struct.pack(
            '<4sHHHHHIIIHH',  # Local file header format
            b'PK\x03\x04',  # Local file header signature
            0x14,  # Version needed to extract (2.0)
            0,   # General purpose bit flag
            0,   # Compression method (0 = stored)
            dostime,  # Last mod file time
            dosdate,  # Last mod file date
            crc,  # CRC-32
            size,  # Compressed size
            size,  # Uncompressed size
            len(filename.encode('utf-8')),  # File name length
            0    # Extra field length
        )
        return header + filename.encode('utf-8')
    
    def create_central_header(filename: str, size: int, crc: int, offset: int) -> bytes:
        """Create ZIP central directory header"""
        dt = time.localtime()
        dosdate = (dt.tm_year - 1980) << 9 | dt.tm_mon << 5 | dt.tm_mday
        dostime = dt.tm_hour << 11 | dt.tm_min << 5 | (dt.tm_sec // 2)
        
        header = struct.pack(
            '<4sHHHHHHIIIHHHHHII',  # Central directory header format
            b'PK\x01\x02',  # Central file header signature
            0x314,  # Version made by (3.1 Unix)
            0x14,   # Version needed to extract (2.0)
            0,      # General purpose bit flag
            0,      # Compression method
            dostime,  # Last mod file time
            dosdate,  # Last mod file date
            crc,      # CRC-32
            size,     # Compressed size
            size,     # Uncompressed size
            len(filename.encode('utf-8')),  # File name length
            0,   # Extra field length
            0,   # File comment length
            0,   # Disk number start
            0,   # Internal file attributes
            0x81A4 << 16,  # External file attributes (regular file, rw-r--r--)
            offset  # Relative offset of local header
        )
        return header + filename.encode('utf-8')
    
    # Track metadata for central directory
    file_records = []
    current_offset = 0
    completed = 0
    failed = 0
    
    async with aiohttp.ClientSession() as session:
        # Stream each file as it downloads
        for idx, track in enumerate(tracks):
            if cancel_flags.get(job_id, False):
                logger.info(f"[Job {job_id[:8]}] Cancelled")
                break
                
            try:
                filename = track.get('filename', track['url'].split('/')[-1])
                if not any(filename.endswith(ext) for ext in ['.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac']):
                    filename += '.mp3'
                
                logger.info(f"[Job {job_id[:8]}] Streaming track {idx+1}/{len(tracks)}: {filename}")
                
                # Download file
                async with session.get(track['url']) as response:
                    response.raise_for_status()
                    
                    # Collect chunks to calculate CRC
                    chunks = []
                    async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                        chunks.append(chunk)
                    
                    file_data = b''.join(chunks)
                    crc = zlib.crc32(file_data) & 0xffffffff
                    size = len(file_data)
                    
                    # Write local header
                    header = create_local_header(filename, size, crc)
                    yield header
                    
                    # Stream file data
                    yield file_data
                    
                    # Save record for central directory
                    file_records.append({
                        'filename': filename,
                        'size': size,
                        'crc': crc,
                        'offset': current_offset
                    })
                    
                    current_offset += len(header) + size
                    completed += 1
                    
                    # Update progress
                    if job_id in download_jobs:
                        download_jobs[job_id]['progress'] = {
                            'total': len(tracks),
                            'completed': completed,
                            'failed': failed
                        }
                        await broadcast_job_update(job_id, download_jobs[job_id])
                        
            except Exception as e:
                logger.error(f"[Job {job_id[:8]}] Failed: {str(e)}")
                failed += 1
                if job_id in download_jobs:
                    download_jobs[job_id]['progress'] = {
                        'total': len(tracks),
                        'completed': completed,
                        'failed': failed
                    }
                    await broadcast_job_update(job_id, download_jobs[job_id])
        
        # Write central directory
        central_offset = current_offset
        for record in file_records:
            header = create_central_header(
                record['filename'],
                record['size'],
                record['crc'],
                record['offset']
            )
            yield header
            current_offset += len(header)
        
        # Write end of central directory
        end_record = struct.pack(
            '<4s4H2IH',
            b'PK\x05\x06',  # End of central dir signature
            0,   # This disk number
            0,   # Central dir start disk
            len(file_records),  # Entries on this disk
            len(file_records),  # Total entries
            current_offset - central_offset,  # Central dir size
            central_offset,  # Central dir offset
            0    # Comment length
        )
        yield end_record
        
    logger.info(f"[Job {job_id[:8]}] Streaming complete: {completed}/{len(tracks)} successful")

def detect_plugin(url):
    """Detect which audio streaming plugin a website is using."""
    import requests
    from bs4 import BeautifulSoup
    
    try:
        logger.info(f"Detecting plugin for URL: {url}")
        response = requests.get(str(url), timeout=30)
        response.raise_for_status()
        html = response.text.lower()
        html_original = response.text
        
        detections = []
        
        if 'plyr' in html or 'new plyr' in html:
            detections.append(('plyr', True))
            logger.debug("Detected Plyr player")
        
        if 'howler' in html or 'howl(' in html or 'howler.js' in html:
            detections.append(('howler', False))
            logger.debug("Detected Howler (unsupported)")
        
        mediaelement_patterns = [
            'mediaelement', 'mejsplayer', 'mejs', 'mejs-',
            'wp-mediaelement', 'mediaelement-and-player',
            'mediaelementplayer', 'mejs__'
        ]
        if any(pattern in html for pattern in mediaelement_patterns):
            detections.append(('mediaelement', False))
            logger.debug("Detected MediaElement (unsupported)")
        
        if 'video-js' in html or 'videojs' in html:
            detections.append(('videojs', False))
            logger.debug("Detected VideoJS (unsupported)")
        
        if 'jwplayer' in html or 'jwplatform' in html:
            detections.append(('jwplayer', False))
            logger.debug("Detected JWPlayer (unsupported)")
        
        if '<audio' in html:
            detections.append(('html5audio', False))
            logger.debug("Detected HTML5 Audio (unsupported)")
        
        if 'soundcloud.com' in html or 'soundcloud-widget' in html:
            detections.append(('soundcloud', False))
            logger.debug("Detected SoundCloud (unsupported)")
        
        if 'spotify.com/embed' in html:
            detections.append(('spotify', False))
            logger.debug("Detected Spotify (unsupported)")
        
        soup = BeautifulSoup(html_original, 'html.parser')
        mp3_links = soup.find_all(lambda tag: 
            (tag.name == 'a' and tag.get('href', '').endswith('.mp3')) or
            (tag.get('data-url', '').endswith('.mp3'))
        )
        if mp3_links:
            detections.append(('simple_mp3', True))
            logger.debug(f"Detected {len(mp3_links)} direct MP3 links")
        
        logger.info(f"Detection complete. Found {len(detections)} players")
        return detections
        
    except Exception as e:
        logger.error(f"Error detecting plugin: {str(e)}")
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
    
    logger.debug(f"Generated name from URL: {name}")
    return name

async def process_download(job_id: str, request: DownloadRequest):
    """Background task to process download."""
    job = download_jobs[job_id]
    logger.info(f"[Job {job_id[:8]}] Starting download process in {request.download_mode} mode")
    
    try:
        # Generate name if not provided
        if not request.name:
            request.name = generate_name_from_url(str(request.url))
            job['status'] = 'detecting'
            job['message'] = f"Generated name: {request.name}"
            logger.info(f"[Job {job_id[:8]}] Generated name: {request.name}")
            await broadcast_job_update(job_id, job)
        
        # Detect plugin if not specified
        if not request.plugin:
            job['status'] = 'detecting'
            job['message'] = "Detecting audio player..."
            logger.info(f"[Job {job_id[:8]}] Detecting audio player...")
            await broadcast_job_update(job_id, job)
            
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
            logger.info(f"[Job {job_id[:8]}] Detected player: {get_player_info(request.plugin)['name']}")
            await broadcast_job_update(job_id, job)
        
        # Import and run the scraper
        job['status'] = 'downloading'
        job['message'] = f"Scraping with {request.plugin} plugin..."
        logger.info(f"[Job {job_id[:8]}] Scraping with {request.plugin} plugin...")
        await broadcast_job_update(job_id, job)
        
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
        job['tracks'] = tracks  # Store tracks for streaming
        logger.info(f"[Job {job_id[:8]}] Found {len(tracks)} tracks. Starting download in {request.download_mode} mode...")
        await broadcast_job_update(job_id, job)
        
        if request.download_mode == "browser":
            # For browser mode, we'll use WebSocket streaming
            job['status'] = 'streaming'
            job['message'] = f"Ready to stream {len(tracks)} tracks"
            job['stream_ready'] = True
            await broadcast_job_update(job_id, job)
            logger.info(f"[Job {job_id[:8]}] Browser mode: Ready for streaming")
        else:
            # Server mode - check authentication
            if not request.auth_token or not verify_token(request.auth_token):
                raise Exception("Authentication required for server downloads")
            
            # Download tracks with progress callback
            def update_progress(completed, failed):
                # Check if cancelled
                if cancel_flags.get(job_id, False):
                    logger.info(f"[Job {job_id[:8]}] Download cancelled")
                    return False  # Signal to stop downloading
                
                job['progress']['completed'] = completed
                job['progress']['failed'] = failed
                logger.info(f"[Job {job_id[:8]}] Progress: {completed}/{len(tracks)} completed, {failed} failed")
                
                # Use asyncio to run the coroutine
                asyncio.create_task(broadcast_job_update(job_id, job))
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
            await broadcast_job_update(job_id, job)
            logger.info(f"[Job {job_id[:8]}] Completed: {result['successful']} successful, {result['failed']} failed")
        
    except Exception as e:
        import traceback
        job['status'] = 'error'
        job['message'] = str(e)
        job['completed_at'] = datetime.now()
        await broadcast_job_update(job_id, job)
        logger.error(f"[Job {job_id[:8]}] Error: {str(e)}")
        logger.error(traceback.format_exc())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    active_connections[connection_id] = websocket
    logger.info(f"WebSocket connected: {connection_id}")
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.pop(connection_id, None)
        logger.info(f"WebSocket disconnected: {connection_id}")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    with open('static/index.html', 'r') as f:
        return f.read()

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login endpoint for server download authentication."""
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": "admin"}, expires_delta=access_token_expires
    )
    logger.info("Admin login successful")
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/download", response_model=DownloadStatus)
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start a new download job."""
    job_id = str(uuid.uuid4())
    
    # For server mode, verify authentication
    if request.download_mode == "server":
        if not request.auth_token or not verify_token(request.auth_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for server downloads"
            )
        
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
        'request': request,
        'download_mode': request.download_mode
    }
    
    logger.info(f"[Job {job_id[:8]}] Created new download job in {request.download_mode} mode")
    
    # Start background task
    background_tasks.add_task(process_download, job_id, request)
    
    return DownloadStatus(**download_jobs[job_id])

@app.get("/api/stream/{job_id}")
async def stream_download(job_id: str):
    """Stream download directly to browser."""
    if job_id not in download_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = download_jobs[job_id]
    
    if job.get('download_mode') != 'browser':
        raise HTTPException(status_code=400, detail="This job is not in browser mode")
    
    if not job.get('stream_ready', False):
        raise HTTPException(status_code=425, detail="Stream not ready yet")
    
    tracks = job.get('tracks', [])
    if not tracks:
        raise HTTPException(status_code=404, detail="No tracks found")
    
    logger.info(f"[Job {job_id[:8]}] Starting streaming download for {len(tracks)} tracks")
    
    # Update job status
    job['status'] = 'downloading'
    job['message'] = f"Streaming {len(tracks)} tracks directly to browser..."
    
    async def stream_with_status():
        """Stream ZIP and update status"""
        try:
            await broadcast_job_update(job_id, job)
            
            # Stream the ZIP file directly as files download
            async for chunk in stream_zip_truly(tracks, job_id):
                yield chunk
            
            # Update completion status
            job['status'] = 'completed'
            job['message'] = "Download complete!"
            job['completed_at'] = datetime.now()
            await broadcast_job_update(job_id, job)
            
        except Exception as e:
            job['status'] = 'error'
            job['message'] = f"Download failed: {str(e)}"
            job['completed_at'] = datetime.now()
            await broadcast_job_update(job_id, job)
            logger.error(f"[Job {job_id[:8]}] Streaming error: {str(e)}")
            raise
    
    # Return true streaming response
    return StreamingResponse(
        stream_with_status(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={job.get('download_name', 'download')}.zip",
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache"
        }
    )

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
    if job['status'] in ['pending', 'detecting', 'downloading', 'streaming']:
        raise HTTPException(status_code=400, detail="Cannot delete active job")
    
    del download_jobs[job_id]
    if job_id in cancel_flags:
        del cancel_flags[job_id]
    
    logger.info(f"[Job {job_id[:8]}] Job deleted")
    return {"message": "Job cleared"}

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel an active job."""
    if job_id not in download_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = download_jobs[job_id]
    if job['status'] not in ['pending', 'detecting', 'downloading', 'streaming']:
        raise HTTPException(status_code=400, detail="Job is not active")
    
    # Set cancel flag
    cancel_flags[job_id] = True
    job['status'] = 'cancelled'
    job['message'] = 'Download cancelled by user'
    job['completed_at'] = datetime.now()
    
    await broadcast_job_update(job_id, job)
    logger.info(f"[Job {job_id[:8]}] Cancelled by user")
    
    return {"message": "Job cancelled"}

@app.get("/api/downloads")
async def list_downloads(auth_token: Optional[str] = None):
    """List available downloads (requires auth)."""
    if not auth_token or not verify_token(auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    downloads_dir = 'downloads'
    if not os.path.exists(downloads_dir):
        return []
    
    downloads = []
    for dir_name in os.listdir(downloads_dir):
        dir_path = os.path.join(downloads_dir, dir_name)
        if os.path.isdir(dir_path):
            audio_extensions = ('.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac')
            files = [f for f in os.listdir(dir_path) if f.lower().endswith(audio_extensions)]
            downloads.append({
                'name': dir_name,
                'files': len(files),
                'size': sum(os.path.getsize(os.path.join(dir_path, f)) for f in files),
                'created': datetime.fromtimestamp(os.path.getctime(dir_path))
            })
    
    downloads.sort(key=lambda x: x['created'], reverse=True)
    return downloads

@app.delete("/api/downloads/{name}")
async def delete_download(name: str, auth_token: Optional[str] = None):
    """Delete a download directory (requires auth)."""
    if not auth_token or not verify_token(auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    dir_path = os.path.join('downloads', name)
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail="Download not found")
    
    shutil.rmtree(dir_path)
    logger.info(f"Deleted download directory: {name}")
    return {"message": "Download deleted"}

@app.get("/api/downloads/{name}/zip")
async def download_as_zip(name: str, auth_token: Optional[str] = None):
    """Download all files in a directory as a ZIP file (requires auth)."""
    if not auth_token or not verify_token(auth_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    logger.info(f"Creating ZIP for download: {name}")
    dir_path = os.path.join('downloads', name)
    if not os.path.exists(dir_path):
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
    zip_size = zip_buffer.getbuffer().nbytes
    
    logger.info(f"ZIP created for {name}, size: {zip_size} bytes")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={name}.zip",
            "Content-Length": str(zip_size)
        }
    )

@app.on_event("startup")
async def startup_event():
    """Log startup message."""
    logger.info("=" * 60)
    logger.info("AudioFetch API v2.0 started successfully!")
    logger.info("Access the web interface at http://localhost:8000")
    logger.info(f"Admin password is: {ADMIN_PASSWORD}")
    logger.info("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=True)