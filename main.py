#!/usr/bin/env python3
import argparse
import importlib
import requests
from bs4 import BeautifulSoup
import sys
import os
import re
from downloader import download_tracks
from player_info import get_player_info

def detect_plugin(url):
    """
    Detect which audio streaming plugin a website is using.
    Returns a tuple of (plugin_name, is_supported).
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        html = response.text.lower()
        html_original = response.text  # Keep original case for some checks
        
        # List of all known audio players
        detections = []
        
        # Check for Plyr (supported)
        if 'plyr' in html or 'new plyr' in html:
            detections.append(('plyr', True))
        
        # Check for Howler.js (not yet supported)
        if 'howler' in html or 'howl(' in html or 'howler.js' in html:
            detections.append(('howler', False))
        
        # Check for MediaElement.js (not yet supported)
        # More comprehensive detection patterns
        mediaelement_patterns = [
            'mediaelement',
            'mejsplayer',
            'mejs',
            'mejs-',
            'wp-mediaelement',  # WordPress integration
            'mediaelement-and-player',
            'mediaelementplayer',
            'mejs__',  # BEM naming convention
        ]
        if any(pattern in html for pattern in mediaelement_patterns):
            detections.append(('mediaelement', False))
        
        # Check for Video.js (not yet supported)
        if 'video-js' in html or 'videojs' in html:
            detections.append(('videojs', False))
        
        # Check for JW Player (not yet supported)
        if 'jwplayer' in html or 'jwplatform' in html:
            detections.append(('jwplayer', False))
        
        # Check for HTML5 audio elements (not yet supported as a dedicated scraper)
        if '<audio' in html:
            detections.append(('html5audio', False))
        
        # Check for SoundCloud embeds (not yet supported)
        if 'soundcloud.com' in html or 'soundcloud-widget' in html:
            detections.append(('soundcloud', False))
        
        # Check for Spotify embeds (not yet supported)
        if 'spotify.com/embed' in html:
            detections.append(('spotify', False))
        
        # Check for simple audio file links (supported) - check this last
        soup = BeautifulSoup(html_original, 'html.parser')
        audio_extensions = ('.mp3', '.m4a', '.aac', '.ogg', '.opus', '.webm', '.wav', '.flac')
        audio_links = soup.find_all(lambda tag: 
            (tag.name == 'a' and tag.get('href', '') and any(tag.get('href', '').lower().endswith(ext) for ext in audio_extensions)) or
            (tag.get('data-url', '') and any(tag.get('data-url', '').lower().endswith(ext) for ext in audio_extensions))
        )
        if audio_links:
            detections.append(('simple', True))
        
        return detections
        
    except Exception as e:
        print(f"Error detecting plugin: {e}")
        return []

def get_available_plugins():
    """Get list of available scraper plugins."""
    plugins = []
    
    # Check for scraper modules
    if os.path.exists('scrapers/simple_audio_scraper.py'):
        plugins.append('simple')
    if os.path.exists('scrapers/scrape_plyr.py'):
        plugins.append('plyr')
    
    # Add more plugins here as they're created
    
    return plugins

def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive audio scraper supporting multiple streaming plugins.'
    )
    parser.add_argument('url', help='URL of the webpage to scrape')
    parser.add_argument('name', nargs='?', help='Name prefix for downloaded files (optional)')
    parser.add_argument(
        '-p', '--plugin', 
        help='Manually specify which plugin to use (e.g., simple_mp3, plyr)',
        choices=get_available_plugins()
    )
    parser.add_argument(
        '-d', '--directory', 
        help='Directory to save files (defaults to name)',
        default=None
    )
    parser.add_argument(
        '-w', '--workers',
        help='Number of parallel downloads (default 5)',
        type=int,
        default=5
    )
    
    args = parser.parse_args()
    
    # Generate a fallback name if none provided
    if args.name is None:
        # Try to extract a meaningful name from the URL
        from urllib.parse import urlparse
        parsed_url = urlparse(args.url)
        
        # Try to get the last meaningful part of the path
        path_parts = [p for p in parsed_url.path.strip('/').split('/') if p]
        if path_parts:
            # Use the last path segment, cleaned up
            args.name = re.sub(r'[^\w\s-]', '', path_parts[-1])
            args.name = re.sub(r'[-\s]+', '-', args.name)
        else:
            # Use the domain name as fallback
            args.name = parsed_url.netloc.replace('.', '-')
        
        # If still empty or too short, use a timestamp
        if not args.name or len(args.name) < 3:
            from datetime import datetime
            args.name = f"audio-download-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        print(f"No name provided, using: {args.name}")
    
    # Use name as directory if not specified
    if args.directory is None:
        args.directory = args.name
    
    # Check if download directory already exists before doing anything else
    downloads_dir = os.path.join('downloads', args.directory)
    if os.path.exists(downloads_dir):
        print(f"\nError: Directory 'downloads/{args.directory}' already exists!")
        print("Please choose a different name or remove the existing directory.")
        print(f"To remove: rm -rf downloads/{args.directory}")
        sys.exit(1)
    
    # Determine which plugin to use
    if args.plugin:
        plugin_name = args.plugin
        print(f"Using manually specified plugin: {plugin_name}")
    else:
        print("Auto-detecting audio player...")
        detections = detect_plugin(args.url)
        
        if not detections:
            print("\nError: Could not detect any audio player on this page.")
            print("Available plugins:", ', '.join(get_available_plugins()))
            print("Please specify a plugin manually with --plugin")
            sys.exit(1)
        
        # Show all detected players
        print("\nDetected audio players:")
        supported = []
        unsupported = []
        
        for player, is_supported in detections:
            info = get_player_info(player)
            if is_supported:
                supported.append(player)
                print(f"  ✓ {info['name']} - {info['description']}")
            else:
                unsupported.append(player)
                print(f"  ✗ {info['name']} - {info['description']} (not yet implemented)")
        
        # Choose the first supported plugin
        if supported:
            plugin_name = supported[0]
            
            # If we have both supported and unsupported, mention both
            if unsupported:
                print(f"\nNote: The site uses {get_player_info(unsupported[0])['name']}, but we'll use {get_player_info(plugin_name)['name']} instead.")
            else:
                print(f"\nUsing: {get_player_info(plugin_name)['name']}")
                
            # Special note for simple when other players are present
            if plugin_name == 'simple' and unsupported:
                print("The simple audio scraper will download any direct audio file links found on the page.")
        else:
            # No supported plugins found, but we detected something
            main_player = unsupported[0]
            info = get_player_info(main_player)
            print(f"\nUnfortunately, we haven't implemented support for {info['name']} yet.")
            print(f"\nAbout {info['name']}:")
            print(f"  {info['description']}")
            for characteristic in info['characteristics']:
                print(f"  • {characteristic}")
            
            print("\nYou can try the 'simple' scraper which works for direct audio file links:")
            print(f"  python main.py {args.url} {args.name or ''} -p simple")
            print("\nThis will download any audio files (MP3, M4A, AAC, OGG, etc.) that are directly linked on the page.")
            sys.exit(1)
    
    # Import and run the appropriate scraper
    try:
        if plugin_name == 'simple':
            module_name = 'scrapers.simple_audio_scraper'
        elif plugin_name == 'plyr':
            module_name = 'scrapers.scrape_plyr'
        else:
            raise ValueError(f"Unknown plugin: {plugin_name}")
        
        # Dynamically import the scraper module
        scraper = importlib.import_module(module_name)
        
        # Call the scraper's main function
        # Each scraper should have a scrape() function that returns track metadata
        if hasattr(scraper, 'scrape'):
            tracks = scraper.scrape(args.url, args.name, args.directory)
            if tracks:
                # Download the tracks using the common downloader
                result = download_tracks(
                    tracks, 
                    args.directory, 
                    prefix=args.name if plugin_name == 'simple' else None,
                    max_workers=args.workers
                )
                if result.get('error'):
                    sys.exit(1)
                elif result['failed'] > 0:
                    print(f"\nWarning: {result['failed']} downloads failed.")
                    sys.exit(2)
                else:
                    print(f"\nAll downloads completed successfully!")
            else:
                print("Error: No tracks found to download")
                sys.exit(1)
        else:
            print(f"Error: {module_name} does not have a scrape() function")
            sys.exit(1)
            
    except ImportError as e:
        print(f"Error: Could not import {module_name}: {e}")
        print(f"Make sure {module_name}.py exists")
        sys.exit(1)
    except Exception as e:
        print(f"Error running scraper: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()