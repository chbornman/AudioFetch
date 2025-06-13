#!/bin/bash
# Secure VPS Setup Script for AudioFetch
# This script should be run on the VPS to set up the environment securely
# before using GitHub Actions for deployment

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to generate secure random strings
generate_secret() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   print_error "Please do not run this script as root for security reasons"
   exit 1
fi

print_status "Starting secure VPS setup for AudioFetch"

# Get application directory
read -p "Enter the application directory path (e.g., /home/user/audiofetch): " APP_DIR

# Create directory if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    print_status "Creating application directory: $APP_DIR"
    mkdir -p "$APP_DIR"
fi

cd "$APP_DIR"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

print_status "Docker and Docker Compose are installed"

# Create .env file securely
if [ -f .env ]; then
    print_warning ".env file already exists. Backing up to .env.backup"
    cp .env .env.backup
fi

print_status "Creating secure .env file"

# Gather configuration
echo
print_status "Please provide the following configuration values:"
echo

read -p "Admin password for server mode (leave empty to generate): " ADMIN_PASSWORD
if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD=$(generate_secret)
    print_status "Generated admin password: $ADMIN_PASSWORD"
    print_warning "SAVE THIS PASSWORD! It won't be shown again."
fi

read -p "Application port (default: 8000): " PORT
PORT=${PORT:-8000}

read -p "Log level (debug/info/warning/error, default: info): " LOG_LEVEL
LOG_LEVEL=${LOG_LEVEL:-info}

read -p "Downloads directory path (default: ./downloads): " DOWNLOADS_PATH
DOWNLOADS_PATH=${DOWNLOADS_PATH:-./downloads}

# Generate SECRET_KEY
SECRET_KEY=$(generate_secret)
print_status "Generated SECRET_KEY for JWT tokens"

# Create .env file with restrictive permissions
cat > .env << EOF
# AudioFetch Environment Configuration
# Generated on $(date)
# DO NOT COMMIT THIS FILE TO VERSION CONTROL

# Security
ADMIN_PASSWORD=${ADMIN_PASSWORD}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Application
PORT=${PORT}
HOST=0.0.0.0
LOG_LEVEL=${LOG_LEVEL}

# Paths
DOWNLOADS_HOST_PATH=${DOWNLOADS_PATH}
DOWNLOADS_CONTAINER_PATH=/app/downloads

# Docker
PYTHONUNBUFFERED=1
DOCKER_CONTAINER=1
EOF

# Set restrictive permissions on .env
chmod 600 .env
print_status "Created .env file with restrictive permissions (600)"

# Create docker-compose.yml
print_status "Creating docker-compose.yml"

cat > docker-compose.yml << 'EOF'
services:
  web:
    image: ghcr.io/GITHUB_USERNAME/GITHUB_REPO:latest
    restart: unless-stopped
    ports:
      - "${PORT}:${PORT}"
    volumes:
      - "${DOWNLOADS_HOST_PATH}:${DOWNLOADS_CONTAINER_PATH}"
    env_file:
      - .env
    environment:
      - DOCKER_CONTAINER=1
    command: >
      uvicorn app:app
        --host ${HOST}
        --port ${PORT}
        --log-level ${LOG_LEVEL}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT}/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

print_warning "IMPORTANT: Update docker-compose.yml with your GitHub username and repository name"
print_warning "Replace GITHUB_USERNAME/GITHUB_REPO with your actual values"

# Create downloads directory
if [ ! -d "$DOWNLOADS_PATH" ]; then
    mkdir -p "$DOWNLOADS_PATH"
    print_status "Created downloads directory: $DOWNLOADS_PATH"
fi

# Create deployment log file
touch deployment.log
chmod 644 deployment.log
print_status "Created deployment.log file"

# Create backup directory
mkdir -p backups
print_status "Created backups directory"

# Create a backup script
cat > backup-config.sh << 'EOF'
#!/bin/bash
# Backup configuration files
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/"
cp docker-compose.yml "$BACKUP_DIR/"
echo "Backup created in $BACKUP_DIR"
EOF

chmod +x backup-config.sh
print_status "Created backup script: backup-config.sh"

# Create a restore script
cat > restore-config.sh << 'EOF'
#!/bin/bash
# Restore configuration from backup
if [ -z "$1" ]; then
    echo "Usage: ./restore-config.sh <backup_directory>"
    echo "Available backups:"
    ls -la backups/
    exit 1
fi

if [ ! -d "$1" ]; then
    echo "Backup directory not found: $1"
    exit 1
fi

cp "$1/.env" .
cp "$1/docker-compose.yml" .
echo "Configuration restored from $1"
EOF

chmod +x restore-config.sh
print_status "Created restore script: restore-config.sh"

# Create update script
cat > update-app.sh << 'EOF'
#!/bin/bash
# Update AudioFetch application
set -e

echo "[$(date)] Starting application update"

# Pull latest image
docker compose pull

# Backup current config
./backup-config.sh

# Restart application
docker compose down
docker compose up -d

# Clean up old images
docker image prune -f

echo "[$(date)] Update completed"
EOF

chmod +x update-app.sh
print_status "Created update script: update-app.sh"

# Summary
echo
print_status "=== Setup Complete ==="
echo
print_status "Configuration summary:"
echo "  - Application directory: $APP_DIR"
echo "  - Port: $PORT"
echo "  - Downloads directory: $DOWNLOADS_PATH"
echo "  - Log level: $LOG_LEVEL"
echo
print_warning "Next steps:"
echo "1. Update docker-compose.yml with your GitHub repository details"
echo "2. Test the configuration locally:"
echo "   docker compose up -d"
echo "3. Configure GitHub Secrets in your repository:"
echo "   - VPS_HOST: Your server IP/hostname"
echo "   - VPS_USERNAME: Your SSH username"
echo "   - VPS_SSH_KEY: Your SSH private key"
echo "   - VPS_PORT: Your SSH port"
echo "   - VPS_APP_DIR: $APP_DIR"
echo "4. Use the secure workflow (deploy-secure.yml) for deployments"
echo
print_status "Security notes:"
echo "  - .env file has restrictive permissions (600)"
echo "  - Admin password is stored securely"
echo "  - SECRET_KEY is randomly generated"
echo "  - Configuration is not stored in version control"
echo "  - Use backup-config.sh to backup configuration"
echo "  - Use update-app.sh to manually update the application"
echo
print_warning "IMPORTANT: Keep your .env file secure and never commit it to version control!"