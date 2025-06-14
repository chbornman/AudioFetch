-- Create download logs table
CREATE TABLE IF NOT EXISTS download_logs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    url_domain VARCHAR(255),
    custom_name VARCHAR(255),
    plugin VARCHAR(50),
    workers INTEGER,
    download_mode VARCHAR(20),
    is_authenticated BOOLEAN DEFAULT FALSE,
    connection_id VARCHAR(36),
    status VARCHAR(20),
    error_message TEXT,
    tracks_count INTEGER,
    total_size_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds DECIMAL(10,2),
    user_agent TEXT,
    ip_address INET
);

-- Create indexes for common queries
CREATE INDEX idx_download_logs_created_at ON download_logs(created_at DESC);
CREATE INDEX idx_download_logs_status ON download_logs(status);
CREATE INDEX idx_download_logs_url_domain ON download_logs(url_domain);
CREATE INDEX idx_download_logs_download_mode ON download_logs(download_mode);

-- Create a view for daily statistics
CREATE VIEW daily_download_stats AS
SELECT 
    DATE(created_at) as download_date,
    COUNT(*) as total_downloads,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_downloads,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_downloads,
    COUNT(CASE WHEN download_mode = 'server' THEN 1 END) as server_downloads,
    COUNT(CASE WHEN download_mode = 'browser' THEN 1 END) as browser_downloads,
    COUNT(DISTINCT url_domain) as unique_domains,
    AVG(tracks_count) as avg_tracks_per_download,
    SUM(total_size_bytes) as total_bytes_downloaded
FROM download_logs
GROUP BY DATE(created_at);

-- Create a view for domain statistics
CREATE VIEW domain_stats AS
SELECT 
    url_domain,
    COUNT(*) as download_count,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_downloads,
    AVG(tracks_count) as avg_tracks,
    MAX(created_at) as last_download
FROM download_logs
GROUP BY url_domain
ORDER BY download_count DESC;