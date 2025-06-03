#!/usr/bin/env python3
"""
Common downloader module with consistent progress display for all scrapers.
"""
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def format_progress_bar(percent, width=30):
    """Create a progress bar string."""
    filled = int(width * percent / 100)
    bar = '█' * filled + '░' * (width - filled)
    return bar


def format_size(bytes):
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:3.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


def sanitize_filename(filename):
    """Clean filename for safe file system usage."""
    # Remove invalid characters
    safe_name = re.sub(r'[^\w\s-]', '', filename)
    # Replace spaces and multiple dashes with single dash
    safe_name = re.sub(r'[-\s]+', '-', safe_name)
    return safe_name


def download_file_with_progress(url, filename, track_info):
    """Download a file from URL to filename with progress info."""
    name = os.path.basename(filename)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, stream=True, headers=headers, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        
        with open(filename, 'wb') as fd:
            for chunk in response.iter_content(chunk_size=16384):
                fd.write(chunk)
                downloaded += len(chunk)
                
                # Update progress every 100KB or at completion
                if downloaded % (100 * 1024) < 16384 or downloaded == total_size:
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        
                        bar = format_progress_bar(percent)
                        line = f"\r[{track_info['num']:2d}/{track_info['total']:2d}] {name:<40} [{bar}] {percent:5.1f}% {format_size(downloaded)}/{format_size(total_size)} @ {format_size(speed)}/s"
                        print(line, end='', flush=True)
        
        print(f"\r[{track_info['num']:2d}/{track_info['total']:2d}] {name:<40} [{'█' * 30}] 100.0% ✓ Complete ({format_size(total_size)})              ")
        return True
    except Exception as e:
        print(f"\r[{track_info['num']:2d}/{track_info['total']:2d}] {name:<40} [{'✗' * 30}] ✗ Error: {str(e)[:30]}...")
        return False


def download_tracks(tracks, directory, prefix=None):
    """
    Download all tracks with consistent progress display.
    
    Args:
        tracks: List of track dictionaries with 'url' and 'name' keys
        directory: Directory to save files to
        prefix: Optional prefix for filenames
    
    Returns:
        Dictionary with download statistics
    """
    # Create downloads directory structure
    downloads_dir = os.path.join('downloads', directory)
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    
    print(f"\nDownloading to: downloads/{directory}/")
    print(f"Total tracks to download: {len(tracks)}")
    print("-" * 80)
    
    # Download files sequentially for cleaner output
    successful_downloads = 0
    failed_downloads = 0
    
    for i, track in enumerate(tracks, 1):
        # Generate filename
        if prefix and track.get('track_num'):
            # For simple scrapers that need numbering
            filename = f"{prefix}_{track['track_num']:03d}.mp3"
        else:
            # For scrapers that provide track names
            safe_name = sanitize_filename(track['name'])
            filename = f"{safe_name}.mp3"
        
        filepath = os.path.join(downloads_dir, filename)
        
        track_info = {
            'num': i,
            'total': len(tracks)
        }
        
        success = download_file_with_progress(track['url'], filepath, track_info)
        if success:
            successful_downloads += 1
        else:
            failed_downloads += 1
        
        # Small delay between downloads
        if i < len(tracks):
            time.sleep(0.5)
    
    print("-" * 80)
    print(f"\nDownload Summary:")
    print(f"  ✓ Successful: {successful_downloads}")
    print(f"  ✗ Failed: {failed_downloads}")
    print(f"  Total: {len(tracks)}")
    
    return {
        'successful': successful_downloads,
        'failed': failed_downloads,
        'total': len(tracks)
    }