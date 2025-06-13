#!/usr/bin/env python3
"""
Common downloader module with consistent progress display for all scrapers.
"""
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
from collections import OrderedDict
import asyncio
import aiohttp
from typing import List, Dict, Optional, Callable


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


class MultiLineProgress:
    """Manages multiple progress lines for parallel downloads."""
    def __init__(self, total_tracks):
        self.lock = threading.Lock()
        self.total_tracks = total_tracks
        self.lines = OrderedDict()
        self.completed_count = 0
        self.failed_count = 0
        
        # Reserve space for all tracks
        for i in range(1, total_tracks + 1):
            print()  # Create empty lines
    
    def update_line(self, track_num, filename, status, percent=0, downloaded=0, total=0):
        """Update a specific line with progress information."""
        with self.lock:
            # Calculate how many lines up to go
            lines_up = self.total_tracks - track_num + 1
            
            # Build the status line
            if status == 'downloading':
                if total > 0:
                    bar = format_progress_bar(percent)
                    line = f"[{track_num:2d}/{self.total_tracks:2d}] {filename:<40} [{bar}] {percent:5.1f}% {format_size(downloaded)}/{format_size(total)}"
                else:
                    line = f"[{track_num:2d}/{self.total_tracks:2d}] {filename:<40} [{'?' * 30}] Downloading..."
            elif status == 'complete':
                self.completed_count += 1
                line = f"[{track_num:2d}/{self.total_tracks:2d}] {filename:<40} [{'█' * 30}] 100.0% ✓ Complete ({format_size(total)})"
            elif status == 'error':
                self.failed_count += 1
                line = f"[{track_num:2d}/{self.total_tracks:2d}] {filename:<40} [{'✗' * 30}] ✗ Error"
            else:
                line = f"[{track_num:2d}/{self.total_tracks:2d}] {filename:<40} Waiting..."
            
            # Clear the line and print the new content
            sys.stdout.write(f"\033[{lines_up}A")  # Move up
            sys.stdout.write(f"\r{line:<120}")     # Write line (padded to clear old content)
            sys.stdout.write(f"\033[{lines_up}B")  # Move back down
            sys.stdout.flush()


def download_file_with_progress(url, filename, track_info, progress_mgr=None):
    """Download a file with progress tracking."""
    name = os.path.basename(filename)
    track_num = track_info['num']
    total_tracks = track_info['total']
    
    # For single file download or when no progress manager
    if progress_mgr is None:
        return download_file_simple(url, filename, track_info)
    
    # Multi-line progress mode
    progress_mgr.update_line(track_num, name, 'downloading')
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, stream=True, headers=headers, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        last_update = time.time()
        
        with open(filename, 'wb') as fd:
            for chunk in response.iter_content(chunk_size=32768):
                fd.write(chunk)
                downloaded += len(chunk)
                
                # Update progress every 0.1 seconds
                current_time = time.time()
                if current_time - last_update > 0.1 or downloaded == total_size:
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        progress_mgr.update_line(track_num, name, 'downloading', percent, downloaded, total_size)
                        last_update = current_time
        
        progress_mgr.update_line(track_num, name, 'complete', 100, total_size, total_size)
        return True, total_size
    except Exception as e:
        progress_mgr.update_line(track_num, name, 'error')
        return False, 0


def download_file_docker(url, filename, track_num):
    """Download file in Docker environment without fancy progress."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, stream=True, headers=headers, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filename, 'wb') as fd:
            for chunk in response.iter_content(chunk_size=32768):
                fd.write(chunk)
        
        return True, total_size, track_num
    except Exception as e:
        print(f"[ERROR] Track {track_num}: {str(e)}")
        return False, 0, track_num


def download_file_docker(url, filename, track_info):
    """Docker-friendly download without ANSI escape sequences."""
    name = os.path.basename(filename)
    track_num = track_info['num']
    total_tracks = track_info['total']
    
    print(f"[{track_num}/{total_tracks}] Downloading {name}...")
    sys.stdout.flush()
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, stream=True, headers=headers, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filename, 'wb') as fd:
            for chunk in response.iter_content(chunk_size=32768):
                fd.write(chunk)
        
        print(f"[{track_num}/{total_tracks}] ✓ {name} ({format_size(total_size)})")
        sys.stdout.flush()
        return True, total_size
    except Exception as e:
        print(f"[{track_num}/{total_tracks}] ✗ {name} - Error: {str(e)}")
        sys.stdout.flush()
        return False, 0


def download_file_simple(url, filename, track_info):
    """Simple download with inline progress (sequential mode)."""
    name = os.path.basename(filename)
    track_num = track_info['num']
    total_tracks = track_info['total']
    
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
                        line = f"\r[{track_num:2d}/{total_tracks:2d}] {name:<40} [{bar}] {percent:5.1f}% {format_size(downloaded)}/{format_size(total_size)} @ {format_size(speed)}/s"
                        print(line, end='', flush=True)
        
        print(f"\r[{track_num:2d}/{total_tracks:2d}] {name:<40} [{'█' * 30}] 100.0% ✓ Complete ({format_size(total_size)})              ")
        return True, total_size
    except Exception as e:
        print(f"\r[{track_num:2d}/{total_tracks:2d}] {name:<40} [{'✗' * 30}] ✗ Error: {str(e)[:30]}...")
        return False, 0


def download_tracks(tracks, directory, prefix=None, max_workers=5, progress_callback=None, job_id=None):
    """
    Download all tracks with consistent progress display.
    
    Args:
        tracks: List of track dictionaries with 'url' and 'name' keys
        directory: Directory to save files to
        prefix: Optional prefix for filenames
        max_workers: Maximum number of parallel downloads (default 5)
        progress_callback: Optional callback function for progress updates
        job_id: Optional job ID for tracking and logging
    
    Returns:
        Dictionary with download statistics
    """
    # Create downloads directory structure
    downloads_dir = os.path.join('downloads', directory)
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    
    # Detect if running in Docker (no TTY)
    is_docker = not sys.stdout.isatty()
    
    if not is_docker:
        job_prefix = f"[Job {job_id[:8]}] " if job_id else ""
        print(f"\n{job_prefix}Downloading to: downloads/{directory}/")
        print(f"{job_prefix}Total tracks to download: {len(tracks)}")
        
        if max_workers > 1:
            print(f"{job_prefix}Parallel downloads: {max_workers}")
        print("-" * 80)
    
    successful = 0
    failed = 0
    
    # Prepare download tasks
    download_tasks = []
    for i, track in enumerate(tracks, 1):
        # Generate filename
        if track.get('original_filename'):
            # Use original filename if provided by scraper
            filename = track['original_filename']
        elif prefix and track.get('track_num'):
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
        
        download_tasks.append((track['url'], filepath, track_info))
    
    # Execute downloads
    if is_docker:
        # Docker mode - simple progress without ANSI escape sequences
        job_prefix = f"[Job {job_id[:8]}] " if job_id else ""
        print(f"{job_prefix}Starting download of {len(tracks)} tracks...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(download_file_docker, url, filepath, track_info): (url, filepath, track_info)
                for url, filepath, track_info in download_tasks
            }
            
            for future in as_completed(future_to_task):
                try:
                    success, size = future.result()
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    if progress_callback:
                        progress_callback(successful, failed)
                        
                except Exception as e:
                    failed += 1
                    print(f"[ERROR] Unexpected error: {e}")
                    if progress_callback:
                        progress_callback(successful, failed)
                        
    elif max_workers == 1:
        # Sequential downloads with inline progress
        for url, filepath, track_info in download_tasks:
            success, size = download_file_simple(url, filepath, track_info)
            if success:
                successful += 1
            else:
                failed += 1
            if progress_callback:
                progress_callback(successful, failed)
    else:
        # Parallel downloads with multi-line progress
        progress_mgr = MultiLineProgress(len(tracks))
        
        # Show initial state for all tracks
        for i, (url, filepath, track_info) in enumerate(download_tasks, 1):
            progress_mgr.update_line(i, os.path.basename(filepath), 'waiting')
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all downloads
            future_to_task = {
                executor.submit(download_file_with_progress, url, filepath, track_info, progress_mgr): (url, filepath, track_info)
                for url, filepath, track_info in download_tasks
            }
            
            # Wait for all downloads to complete
            for future in as_completed(future_to_task):
                try:
                    success, size = future.result()
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    if progress_callback:
                        progress_callback(successful, failed)
                except Exception as e:
                    failed += 1
                    print(f"\nUnexpected error in download: {e}")
                    if progress_callback:
                        progress_callback(successful, failed)
        
        # Move cursor to bottom after all lines
        print()
    
    if not is_docker:
        print("-" * 80)
        job_prefix = f"[Job {job_id[:8]}] " if job_id else ""
        print(f"\n{job_prefix}Download Summary:")
        print(f"  ✓ Successful: {successful}")
        print(f"  ✗ Failed: {failed}")
        print(f"  Total: {len(tracks)}")
    
    return {
        'successful': successful,
        'failed': failed,
        'total': len(tracks)
    }


async def download_file_async(session: aiohttp.ClientSession, url: str, filepath: str, track_info: dict, job_id: str = None) -> tuple:
    """Download a single file asynchronously."""
    try:
        job_prefix = f"[Job {job_id[:8]}] " if job_id else ""
        track_num = track_info['num']
        total_tracks = track_info['total']
        name = os.path.basename(filepath)[:40]
        
        print(f"{job_prefix}[{track_num}/{total_tracks}] Downloading {name}...")
        
        async with session.get(url) as response:
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as fd:
                async for chunk in response.content.iter_chunked(16384):
                    fd.write(chunk)
                    downloaded += len(chunk)
            
            size_mb = total_size / (1024 * 1024)
            print(f"{job_prefix}[{track_num}/{total_tracks}] ✓ {name} ({size_mb:.1f} MB)")
            return True, total_size
            
    except Exception as e:
        print(f"{job_prefix}[{track_num}/{total_tracks}] ✗ {name} - Error: {str(e)}")
        return False, 0


async def download_tracks_async(
    tracks: List[Dict], 
    directory: str, 
    prefix: Optional[str] = None, 
    max_workers: int = 5, 
    progress_callback: Optional[Callable] = None,
    job_id: Optional[str] = None
) -> Dict:
    """
    Download all tracks asynchronously with progress updates.
    
    Args:
        tracks: List of track dictionaries with 'url' and 'name' keys
        directory: Directory to save files to
        prefix: Optional prefix for filenames
        max_workers: Maximum number of parallel downloads
        progress_callback: Optional async callback function for progress updates
        job_id: Optional job ID for tracking and logging
    
    Returns:
        Dictionary with download statistics
    """
    # Create downloads directory structure
    downloads_dir = os.path.join('downloads', directory)
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    
    # Detect if running in Docker (no TTY)
    is_docker = not sys.stdout.isatty()
    
    if not is_docker:
        job_prefix = f"[Job {job_id[:8]}] " if job_id else ""
        print(f"\n{job_prefix}Downloading to: downloads/{directory}/")
        print(f"{job_prefix}Total tracks to download: {len(tracks)}")
        
        if max_workers > 1:
            print(f"{job_prefix}Parallel downloads: {max_workers}")
        print("-" * 80)
    
    successful = 0
    failed = 0
    
    # Prepare download tasks
    download_tasks = []
    for i, track in enumerate(tracks, 1):
        # Generate filename
        if track.get('original_filename'):
            filename = track['original_filename']
        elif prefix and track.get('track_num'):
            filename = f"{prefix}_{track['track_num']:03d}.mp3"
        else:
            safe_name = sanitize_filename(track['name'])
            filename = f"{safe_name}.mp3"
        
        filepath = os.path.join(downloads_dir, filename)
        
        track_info = {
            'num': i,
            'total': len(tracks)
        }
        
        download_tasks.append((track['url'], filepath, track_info))
    
    # Create aiohttp session with connection limit
    connector = aiohttp.TCPConnector(limit=max_workers)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Process downloads with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_workers)
        
        async def download_with_semaphore(url, filepath, track_info):
            async with semaphore:
                return await download_file_async(session, url, filepath, track_info, job_id)
        
        # Start all downloads
        tasks = []
        for url, filepath, track_info in download_tasks:
            task = asyncio.create_task(download_with_semaphore(url, filepath, track_info))
            tasks.append(task)
        
        # Process completions as they happen
        for completed_task in asyncio.as_completed(tasks):
            success, size = await completed_task
            if success:
                successful += 1
            else:
                failed += 1
            
            # Call progress callback if provided
            if progress_callback:
                should_continue = await progress_callback(successful, failed)
                if not should_continue:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    break
    
    if not is_docker:
        print("-" * 80)
        job_prefix = f"[Job {job_id[:8]}] " if job_id else ""
        print(f"\n{job_prefix}Download Summary:")
        print(f"  ✓ Successful: {successful}")
        print(f"  ✗ Failed: {failed}")
        print(f"  Total: {len(tracks)}")
    
    return {
        'successful': successful,
        'failed': failed,
        'total': len(tracks)
    }