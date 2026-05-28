"""
Circuit Breaker implementation for external service integrations.
Follows the design: Open after 5 consecutive failures, retry after 60 seconds.
"""

import time
import logging
import functools
from enum import Enum
from typing import Callable, Any, Dict, Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Service unavailable, fail fast
    HALF_OPEN = "HALF_OPEN" # Testing if service has recovered

class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern to prevent cascading failures.
    """
    def __init__(
        self, 
        service_name: str, 
        failure_threshold: int = 5, 
        recovery_timeout: int = 60
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap service calls with circuit breaker logic."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self._update_state()

            if self.state == CircuitState.OPEN:
                logger.warning(f"Circuit for {self.service_name} is OPEN. Failing fast.")
                raise CircuitBreakerOpenException(f"Service {self.service_name} is currently unavailable")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure(e)
                raise e

        return wrapper

    def _update_state(self):
        """Check if an OPEN circuit should transition to HALF_OPEN."""
        if self.state == CircuitState.OPEN and self.last_failure_time:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"Circuit for {self.service_name} transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN

    def _on_success(self):
        """Reset circuit on successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit for {self.service_name} recovered. Closing circuit.")
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def _on_failure(self, exception: Exception):
        """Track failures and open circuit if threshold reached."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        logger.error(f"Failure {self.failure_count}/{self.failure_threshold} for {self.service_name}: {str(exception)}")

        if self.failure_count >= self.failure_threshold:
            logger.critical(f"Failure threshold reached. Opening circuit for {self.service_name}")
            self.state = CircuitState.OPEN

class CircuitBreakerOpenException(Exception):
    """Raised when a call is attempted while the circuit is OPEN."""
    pass

# Global registry for circuit breakers to be used across services
circuit_breakers: Dict[str, CircuitBreaker] = {
    "ecb_api": CircuitBreaker("ECB API"),
    "nvidia_nim": CircuitBreaker("NVIDIA NIM LLM"),
    "erp_system": CircuitBreaker("ERP System"),
    "payment_processor": CircuitBreaker("Payment Processor"),
    "gmail_imap": CircuitBreaker("Gmail IMAP"),
}

def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Retrieve a circuit breaker from the registry."""
    if service_name not in circuit_breakers:
        circuit_breakers[service_name] = CircuitBreaker(service_name)
    return circuit_breakers[service_name]
