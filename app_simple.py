#!/usr/bin/env python3
"""Simple test version of the app to debug Docker issues."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="Audio Downloader Test")

@app.get("/")
async def root():
    """Test endpoint."""
    return {
        "message": "Audio Downloader Test API",
        "working_dir": os.getcwd(),
        "files": os.listdir('.'),
        "downloads_exists": os.path.exists('downloads'),
        "static_exists": os.path.exists('static')
    }

@app.get("/test/modules")
async def test_modules():
    """Test if modules can be imported."""
    results = {}
    modules = ['player_info', 'downloader', 'simple_scrape_mp3', 'scrape_plyr']
    
    for module in modules:
        try:
            __import__(module)
            results[module] = "OK"
        except Exception as e:
            results[module] = str(e)
    
    return results

@app.get("/test/scrape")
async def test_scrape():
    """Test basic scraping."""
    try:
        from player_info import get_player_info
        import simple_scrape_mp3
        
        # Test a simple function
        info = get_player_info('simple_mp3')
        
        return {
            "player_info_test": info,
            "module_loaded": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("Starting test server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)