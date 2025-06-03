#!/usr/bin/env python3
"""Test script to diagnose Docker issues."""

import sys
import os
import requests

print("=" * 60)
print("Docker Environment Test")
print("=" * 60)

# Test 1: Check if running in Docker
print("\n1. TTY Detection:")
print(f"   - sys.stdout.isatty(): {sys.stdout.isatty()}")
print(f"   - Is Docker: {not sys.stdout.isatty()}")

# Test 2: Check working directory
print("\n2. Working Directory:")
print(f"   - Current dir: {os.getcwd()}")
print(f"   - Files in current dir: {os.listdir('.')}")

# Test 3: Check if downloads directory exists
print("\n3. Downloads Directory:")
downloads_exists = os.path.exists('downloads')
print(f"   - Exists: {downloads_exists}")
if downloads_exists:
    print(f"   - Contents: {os.listdir('downloads')}")

# Test 4: Check if static directory exists
print("\n4. Static Directory:")
static_exists = os.path.exists('static')
print(f"   - Exists: {static_exists}")
if static_exists:
    print(f"   - Contents: {os.listdir('static')}")

# Test 5: Test module imports
print("\n5. Module Imports:")
modules_to_test = ['player_info', 'downloader', 'simple_scrape_mp3', 'scrape_plyr']
for module in modules_to_test:
    try:
        __import__(module)
        print(f"   ✓ {module}")
    except Exception as e:
        print(f"   ✗ {module}: {str(e)}")

# Test 6: Test web request
print("\n6. Web Request Test:")
try:
    response = requests.get('https://httpbin.org/get', timeout=5)
    print(f"   - Status: {response.status_code}")
    print(f"   - Success: {response.status_code == 200}")
except Exception as e:
    print(f"   - Error: {str(e)}")

print("\n" + "=" * 60)