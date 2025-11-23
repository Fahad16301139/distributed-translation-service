"""
Ambassador Pattern Implementation
Handles communication with external Translation API
- Adds API keys
- Manages retries
- Handles timeouts
- Provides logging
"""
import time
import logging
import requests
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import config
from shared.circuit_breaker import external_api_breaker

logger = logging.getLogger(__name__)


class AmbassadorException(Exception):
    """Custom exception for Ambassador pattern errors"""
    pass


class TranslationAmbassador:
    """
    Ambassador for external translation API.
    Acts as a proxy that adds cross-cutting concerns:
    - Authentication (API keys)
    - Retry logic
    - Timeout handling
    - Logging and monitoring
    - Error handling
    """
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Translation Ambassador.
        
        Args:
            api_url: External translation API URL
            api_key: API authentication key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_url = api_url or config.EXTERNAL_TRANSLATION_API_URL
        self.api_key = api_key or config.GOOGLE_TRANSLATE_API_KEY
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            logger.warning("No API key configured for external translation service")
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with authentication"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'DistributedTranslationSystem/1.0'
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        return headers
    
    def _log_request(self, method: str, url: str, data: Dict[str, Any]):
        """Log outgoing request"""
        logger.info(f"Ambassador: {method} {url}")
        logger.debug(f"Request data: {data}")
    
    def _log_response(self, response: requests.Response, duration: float):
        """Log API response"""
        logger.info(
            f"Ambassador: Response {response.status_code} "
            f"in {duration:.2f}s"
        )
        logger.debug(f"Response body: {response.text[:200]}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, 
                                      requests.exceptions.ConnectionError)),
        reraise=True
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters
            
        Returns:
            Response data as dictionary
            
        Raises:
            AmbassadorException: If request fails after retries
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        headers = self._build_headers()
        
        self._log_request(method, url, data or {})
        start_time = time.time()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            duration = time.time() - start_time
            self._log_response(response, duration)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Ambassador: Request timeout after {self.timeout}s")
            raise AmbassadorException(f"Request timeout: {str(e)}")
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ambassador: Connection error: {str(e)}")
            raise AmbassadorException(f"Connection error: {str(e)}")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Ambassador: HTTP error {response.status_code}: {response.text}")
            raise AmbassadorException(f"HTTP error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Ambassador: Unexpected error: {str(e)}")
            raise AmbassadorException(f"Unexpected error: {str(e)}")
    
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict[str, Any]:
        """
        Translate text using external API with circuit breaker protection.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translation result dictionary
            
        Raises:
            AmbassadorException: If translation fails
        """
        if not self.api_key:
            raise AmbassadorException("API key not configured")
        
        translation_data = {
            'q': text,
            'source': source_lang,
            'target': target_lang,
            'format': 'text'
        }
        
        try:
            # Use circuit breaker to protect against cascading failures
            result = external_api_breaker.call(
                self._make_request,
                method='POST',
                endpoint='',
                data=translation_data
            )
            
            return {
                'translated_text': result.get('data', {}).get('translations', [{}])[0].get('translatedText', ''),
                'source_language': source_lang,
                'target_language': target_lang,
                'provider': 'external_api'
            }
            
        except Exception as e:
            logger.error(f"Translation failed through ambassador: {str(e)}")
            raise AmbassadorException(f"Translation failed: {str(e)}")
    
    def health_check(self) -> bool:
        """
        Check if external API is accessible.
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Attempt a lightweight request to check API health
            self._make_request(method='GET', endpoint='/health')
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False


# Global ambassador instance
translation_ambassador = TranslationAmbassador()

