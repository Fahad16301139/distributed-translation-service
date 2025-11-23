"""
Circuit Breaker Pattern Implementation
Protects system by isolating failures in Translation Service and Message Queue
"""
import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
from config import config

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failure threshold exceeded, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker implementation to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: After timeout, try a test request
    """
    
    def __init__(
        self,
        failure_threshold: int = None,
        timeout: int = None,
        name: str = "CircuitBreaker"
    ):
        """
        Initialize Circuit Breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Time in seconds before attempting to close circuit
            name: Name of the circuit breaker for logging
        """
        self.failure_threshold = failure_threshold or config.CIRCUIT_BREAKER_FAIL_MAX
        self.timeout = timeout or config.CIRCUIT_BREAKER_TIMEOUT
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"{self.name}: Circuit transitioning to HALF_OPEN")
            else:
                raise Exception(f"{self.name}: Circuit is OPEN, request blocked")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt circuit reset"""
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.timeout
    
    def _on_success(self):
        """Handle successful request"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"{self.name}: Circuit recovering, transitioning to CLOSED")
        
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.warning(
            f"{self.name}: Failure recorded ({self.failure_count}/{self.failure_threshold})"
        )
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"{self.name}: Circuit OPENED due to {self.failure_count} failures")
    
    def reset(self):
        """Manually reset the circuit breaker"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info(f"{self.name}: Circuit manually reset to CLOSED")
    
    def get_state(self) -> str:
        """Get current circuit state"""
        return self.state.value


def circuit_breaker(name: str = "default", failure_threshold: int = None, timeout: int = None):
    """
    Decorator for applying circuit breaker to functions.
    
    Usage:
        @circuit_breaker(name="translation_api", failure_threshold=5, timeout=60)
        def call_translation_api():
            # API call code
            pass
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        timeout=timeout,
        name=name
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        
        # Attach breaker instance to function for external access
        wrapper.circuit_breaker = breaker
        return wrapper
    
    return decorator


# Global circuit breaker instances
translation_service_breaker = CircuitBreaker(
    name="TranslationService",
    failure_threshold=config.CIRCUIT_BREAKER_FAIL_MAX,
    timeout=config.CIRCUIT_BREAKER_TIMEOUT
)

message_queue_breaker = CircuitBreaker(
    name="MessageQueue",
    failure_threshold=config.CIRCUIT_BREAKER_FAIL_MAX,
    timeout=config.CIRCUIT_BREAKER_TIMEOUT
)

external_api_breaker = CircuitBreaker(
    name="ExternalAPI",
    failure_threshold=config.CIRCUIT_BREAKER_FAIL_MAX,
    timeout=config.CIRCUIT_BREAKER_TIMEOUT
)

