"""Security utilities for input validation and sanitization."""
import os
import re
from urllib.parse import urlparse
from typing import Optional
import ipaddress

# Allowed protocols for downloads
ALLOWED_PROTOCOLS = ['http', 'https']

# Blocked internal network ranges
INTERNAL_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]

def validate_url(url: str) -> bool:
    """Validate URL for security issues."""
    try:
        parsed = urlparse(url)
        
        # Check protocol
        if parsed.scheme not in ALLOWED_PROTOCOLS:
            return False
        
        # Check for empty host
        if not parsed.hostname:
            return False
        
        # Check for internal IPs
        try:
            # Try to parse as IP address
            ip = ipaddress.ip_address(parsed.hostname)
            for network in INTERNAL_NETWORKS:
                if ip in network:
                    return False
        except ValueError:
            # Not an IP address, check for localhost variants
            hostname_lower = parsed.hostname.lower()
            if hostname_lower in ['localhost', '127.0.0.1', '::1']:
                return False
        
        # Block file:// and other dangerous schemes
        if parsed.scheme in ['file', 'ftp', 'sftp', 'ssh']:
            return False
            
        return True
    except Exception:
        return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal."""
    # Remove any directory components
    filename = os.path.basename(filename)
    
    # Remove any potentially dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Remove multiple dots to prevent extension confusion
    filename = re.sub(r'\.+', '.', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed'
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename

def validate_safe_path(base_dir: str, user_path: str) -> str:
    """Validate that a path stays within the base directory."""
    # Get absolute paths
    base_dir = os.path.abspath(base_dir)
    full_path = os.path.abspath(os.path.join(base_dir, user_path))
    
    # Ensure the full path starts with the base directory
    if not full_path.startswith(base_dir + os.sep) and full_path != base_dir:
        raise ValueError("Invalid path: attempted directory traversal")
    
    return full_path

def is_valid_job_id(job_id: str) -> bool:
    """Validate job ID format (UUID)."""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(job_id))