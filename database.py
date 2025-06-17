"""Database connection and logging functions."""
import os
import asyncpg
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Database connection pool
_db_pool: Optional[asyncpg.Pool] = None

async def init_db_pool():
    """Initialize the database connection pool."""
    global _db_pool
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.warning("DATABASE_URL not set, database logging disabled")
        return
    
    try:
        _db_pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        _db_pool = None

async def close_db_pool():
    """Close the database connection pool."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database connection pool closed")

@asynccontextmanager
async def get_db_connection():
    """Get a database connection from the pool."""
    if not _db_pool:
        yield None
        return
    
    try:
        async with _db_pool.acquire() as connection:
            yield connection
    except Exception as e:
        logger.error(f"Failed to acquire database connection: {e}")
        yield None

async def log_download_request(
    job_id: str,
    url: str,
    url_domain: str,
    custom_name: Optional[str],
    plugin: Optional[str],
    workers: int,
    download_mode: str,
    is_authenticated: bool,
    connection_id: Optional[str],
    user_agent: Optional[str],
    ip_address: Optional[str]
) -> bool:
    """Log a new download request to the database."""
    async with get_db_connection() as conn:
        if not conn:
            return False
        
        try:
            await conn.execute("""
                INSERT INTO download_logs (
                    job_id, url, url_domain, custom_name, plugin, workers,
                    download_mode, is_authenticated, connection_id,
                    status, user_agent, ip_address, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, job_id, url, url_domain, custom_name, plugin, workers,
                download_mode, is_authenticated, connection_id,
                'pending', user_agent, ip_address, datetime.now(timezone.utc))
            return True
        except Exception as e:
            logger.error(f"Failed to log download request: {e}")
            return False

async def update_download_status(
    job_id: str,
    status: str,
    error_message: Optional[str] = None,
    tracks_count: Optional[int] = None,
    total_size_bytes: Optional[int] = None
) -> bool:
    """Update the status of a download job."""
    async with get_db_connection() as conn:
        if not conn:
            return False
        
        try:
            completed_at = datetime.now(timezone.utc) if status in ['completed', 'error', 'cancelled'] else None
            
            # Calculate duration if completed
            duration_seconds = None
            if completed_at:
                result = await conn.fetchrow(
                    "SELECT created_at FROM download_logs WHERE job_id = $1",
                    job_id
                )
                if result and result['created_at']:
                    duration = completed_at - result['created_at']
                    duration_seconds = duration.total_seconds()
            
            await conn.execute("""
                UPDATE download_logs
                SET status = $2,
                    error_message = $3,
                    tracks_count = $4,
                    total_size_bytes = $5,
                    completed_at = $6,
                    duration_seconds = $7
                WHERE job_id = $1
            """, job_id, status, error_message, tracks_count,
                total_size_bytes, completed_at, duration_seconds)
            return True
        except Exception as e:
            logger.error(f"Failed to update download status: {e}")
            return False

async def get_download_stats() -> Optional[Dict[str, Any]]:
    """Get overall download statistics."""
    async with get_db_connection() as conn:
        if not conn:
            return None
        
        try:
            # Get overall stats
            overall = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_downloads,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_downloads,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_downloads,
                    COUNT(DISTINCT url_domain) as unique_domains,
                    SUM(tracks_count) as total_tracks,
                    SUM(total_size_bytes) as total_bytes
                FROM download_logs
            """)
            
            # Get recent downloads
            recent = await conn.fetch("""
                SELECT job_id, url_domain, custom_name, status, 
                       tracks_count, created_at, duration_seconds
                FROM download_logs
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            # Get top domains
            top_domains = await conn.fetch("""
                SELECT url_domain, COUNT(*) as download_count
                FROM download_logs
                WHERE url_domain IS NOT NULL
                GROUP BY url_domain
                ORDER BY download_count DESC
                LIMIT 10
            """)
            
            return {
                "overall": dict(overall),
                "recent_downloads": [dict(r) for r in recent],
                "top_domains": [dict(d) for d in top_domains]
            }
        except Exception as e:
            logger.error(f"Failed to get download stats: {e}")
            return None