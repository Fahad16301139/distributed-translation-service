"""
Rate Limiting Module
Prevents overload and abuse of the translation service
"""
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config

logger = logging.getLogger(__name__)


def init_rate_limiter(app, storage_uri: str = None):
    """
    Initialize rate limiter with Flask app.
    
    Args:
        app: Flask application instance
        storage_uri: Redis URI for rate limit storage
        
    Returns:
        Limiter instance
    """
    if storage_uri is None:
        storage_uri = config.REDIS_URL
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=[
            f"{config.RATE_LIMIT_PER_MINUTE} per minute",
            f"{config.RATE_LIMIT_PER_HOUR} per hour"
        ],
        strategy="fixed-window",
        headers_enabled=True,
        swallow_errors=True  # Don't crash if Redis is unavailable
    )
    
    @limiter.request_filter
    def exempt_health_check():
        """Don't apply rate limiting to health check endpoints"""
        return request.endpoint == 'health'
    
    logger.info(f"Rate limiter initialized with {config.RATE_LIMIT_PER_MINUTE}/min")
    
    return limiter


# Custom rate limit decorators for specific use cases
def translation_rate_limit(limiter):
    """
    Custom rate limit for translation endpoints.
    More restrictive than default.
    """
    return limiter.limit("30 per minute;500 per hour")


def feedback_rate_limit(limiter):
    """
    Custom rate limit for feedback endpoints.
    Less restrictive for polling.
    """
    return limiter.limit("120 per minute;2000 per hour")

