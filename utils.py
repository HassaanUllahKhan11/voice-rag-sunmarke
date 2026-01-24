"""
Utility functions for error handling and logging.
"""

import logging
import functools
from typing import Callable, Any

logger = logging.getLogger(__name__)


def handle_errors(default_return=None, log_error=True):
    """
    Decorator for graceful error handling.
    
    Args:
        default_return: Value to return on error
        log_error: Whether to log the error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator


def safe_execute(func: Callable, default_return=None, *args, **kwargs) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        default_return: Value to return on error
        *args, **kwargs: Arguments to pass to function
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing {func.__name__}: {e}", exc_info=True)
        return default_return
