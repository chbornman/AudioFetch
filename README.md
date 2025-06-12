# AudioFetch

A FastAPI-based web application for downloading audio from websites with real-time progress tracking via WebSockets.

## Features

### Core Features

- **Browser Mode**: Stream downloads directly to browser without server storage
- **Server Mode**: Password-protected downloads saved to server (for admin use)
- **Real-time Progress**: WebSocket-based live updates
- **Auto-detection**: Automatically detects audio players on websites
- **Parallel Downloads**: Configurable workers for faster downloads
- **Multiple Formats**: Supports MP3, M4A, AAC, OGG, OPUS, WebM, WAV, FLAC

### Supported Audio Players

- ✅ Plyr.js audio players
- ✅ Direct MP3 links
- ❌ Howler.js (planned)
- ❌ MediaElement.js (planned)
- ❌ Video.js (planned)

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd download_audio
git checkout containerized
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables (optional):

```bash
export ADMIN_PASSWORD="your-secure-password"  # Default: admin123
export SECRET_KEY="your-secret-key"           # For JWT tokens
```

## Running the Application

### Local Development

```bash
python app.py
```

The app will be available at `http://localhost:8000`

### Using Docker

```bash
docker-compose up --build
```

## Usage Guide

### Browser Mode (No Authentication Required)

1. Open `http://localhost:8000` in your browser
2. Enter the URL of the page containing audio
3. Leave "Download Mode" as "Browser"
4. Click "Start Download"
5. Files will stream directly to your browser as a ZIP

### Server Mode (Authentication Required)

1. Click on "Admin Login" and enter the admin password
2. Select "Server" as the download mode
3. Start the download - files will be saved on the server
4. Access saved downloads from the "Server Downloads" section

### CLI Usage (Original Functionality)

The original command-line interface is still available:

```bash
python main.py <url> [name] [--plugin <plugin_name>] [--workers <num>]
```

Example:

```bash
python main.py https://example.com/audiobook my-audiobook --plugin plyr --workers 10
```

## API Endpoints

### Public Endpoints

- `GET /` - Web interface
- `POST /api/download` - Start a new download
- `GET /api/status/{job_id}` - Get job status
- `GET /api/jobs` - List all jobs
- `DELETE /api/jobs/{job_id}` - Delete completed job
- `POST /api/jobs/{job_id}/cancel` - Cancel active job
- `GET /api/stream/{job_id}` - Stream browser mode download
- `WebSocket /ws` - Real-time updates

### Protected Endpoints (Require Authentication)

- `POST /api/auth/login` - Login with admin password
- `GET /api/downloads` - List server downloads
- `DELETE /api/downloads/{name}` - Delete server download
- `GET /api/downloads/{name}/zip` - Download as ZIP

## Architecture

### Backend (FastAPI)

- WebSocket support for real-time updates
- JWT-based authentication for server mode
- Async/await for efficient I/O operations
- Background tasks for download processing
- Streaming responses for large files

### Frontend

- Vanilla JavaScript with WebSocket client
- Real-time progress bars
- Responsive design
- No framework dependencies

### Download Flow

#### Browser Mode

1. User submits URL
2. Backend scrapes audio links
3. Creates streaming response
4. Chunks audio files directly to browser
5. No server storage required

#### Server Mode

1. User authenticates with admin password
2. Backend downloads files to server
3. Files stored in `downloads/` directory
4. User can download as ZIP later

## Configuration

### Environment Variables

- `ADMIN_PASSWORD`: Password for server mode (default: "admin123")
- `SECRET_KEY`: JWT secret key (default: auto-generated)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiry (default: 1440)

### Download Settings

- Workers: 1-20 parallel downloads (default: 5)
- Timeout: 30 seconds per request
- Chunk size: 8KB for streaming

## Testing

Run the test script:

```bash
python test_improved.py
```

This will test:

- Authentication
- Browser mode downloads
- Server mode downloads
- Download listing

## Logging

Logs are written to:

- Console output (INFO level)
- `audiofetch.log` file (DEBUG level)

Log format includes:

- Timestamp
- Log level
- Job ID (when applicable)
- Progress updates
- Error details

## Security Considerations

1. **Authentication**: Server mode requires password
2. **CORS**: Configure for production deployment
3. **File paths**: Sanitized to prevent directory traversal
4. **Rate limiting**: Consider adding for production
5. **HTTPS**: Use reverse proxy with SSL in production

## Deployment

For VPS deployment:

1. Use a reverse proxy (Nginx/Caddy)
2. Enable SSL/TLS
3. Set strong admin password
4. Configure firewall rules
5. Use process manager (systemd/supervisor)

Example Nginx config:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### WebSocket Connection Issues

- Check firewall allows WebSocket connections
- Ensure reverse proxy forwards WebSocket headers
- Check browser console for errors

### Download Failures

- Check `audiofetch.log` for details
- Verify URL is accessible
- Check audio player is supported
- Ensure sufficient disk space (server mode)

### Authentication Issues

- Verify ADMIN_PASSWORD environment variable
- Check token hasn't expired
- Clear browser localStorage if needed

## Future Enhancements

- [ ] Support more audio players
- [ ] Batch URL processing
- [ ] Download history
- [ ] User management system
- [ ] Progress persistence across restarts
- [ ] Mobile app
- [ ] Browser extension
