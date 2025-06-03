#!/usr/bin/env python3
import argparse
import importlib
import requests
from bs4 import BeautifulSoup
import sys
import os

def detect_plugin(url):
    """
    Detect which audio streaming plugin a website is using.
    Returns the plugin name or None if no known plugin is detected.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        html = response.text.lower()
        
        # Check for Plyr
        if 'plyr' in html or 'new plyr' in html:
            return 'plyr'
        
        # Check for simple MP3 links
        soup = BeautifulSoup(response.text, 'html.parser')
        # Check for direct MP3 links in href or data-url attributes
        mp3_links = soup.find_all(lambda tag: 
            (tag.name == 'a' and tag.get('href', '').endswith('.mp3')) or
            (tag.get('data-url', '').endswith('.mp3'))
        )
        if mp3_links:
            return 'simple_mp3'
        
        # Add more plugin detections here as needed
        # Examples: 'mediaelement', 'videojs', 'howler', etc.
        
        return None
        
    except Exception as e:
        print(f"Error detecting plugin: {e}")
        return None

def get_available_plugins():
    """Get list of available scraper plugins."""
    plugins = []
    
    # Check for scraper modules
    if os.path.exists('simple_scrape_mp3.py'):
        plugins.append('simple_mp3')
    if os.path.exists('scrape_plyr.py'):
        plugins.append('plyr')
    
    # Add more plugins here as they're created
    
    return plugins

def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive audio scraper supporting multiple streaming plugins.'
    )
    parser.add_argument('url', help='URL of the webpage to scrape')
    parser.add_argument('name', help='Name prefix for downloaded files')
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
    
    args = parser.parse_args()
    
    # Use name as directory if not specified
    if args.directory is None:
        args.directory = args.name
    
    # Determine which plugin to use
    if args.plugin:
        plugin_name = args.plugin
        print(f"Using manually specified plugin: {plugin_name}")
    else:
        print("Auto-detecting plugin...")
        plugin_name = detect_plugin(args.url)
        
        if plugin_name is None:
            print("Error: Could not detect audio plugin type.")
            print("Available plugins:", ', '.join(get_available_plugins()))
            print("Please specify a plugin manually with --plugin")
            sys.exit(1)
        
        print(f"Detected plugin: {plugin_name}")
    
    # Import and run the appropriate scraper
    try:
        if plugin_name == 'simple_mp3':
            module_name = 'simple_scrape_mp3'
        elif plugin_name == 'plyr':
            module_name = 'scrape_plyr'
        else:
            raise ValueError(f"Unknown plugin: {plugin_name}")
        
        # Dynamically import the scraper module
        scraper = importlib.import_module(module_name)
        
        # Call the scraper's main function
        # Each scraper should have a scrape() function
        if hasattr(scraper, 'scrape'):
            scraper.scrape(args.url, args.name, args.directory)
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