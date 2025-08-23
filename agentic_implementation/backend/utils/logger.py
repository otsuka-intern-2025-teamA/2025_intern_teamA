import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

def setup_project_logging(log_level: str = "INFO", log_file: str = "log.txt") -> logging.Logger:
    """
    Setup centralized logging for the entire project.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Name of the log file
    
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    project_root = Path(__file__).parent.parent.parent
    logs_dir = project_root / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(levelname)-8s | %(message)s'
    )
    
    # File handler - detailed logging to specified log file
    log_file_path = logs_dir / log_file
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # File gets all levels
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler - simplified output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup message
    root_logger.info("=" * 100)
    root_logger.info("🚀 Company Research Agent - Logging System Initialized")
    root_logger.info(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    root_logger.info(f"📁 Log file: {log_file_path}")
    root_logger.info(f"🔧 Log level: {log_level.upper()}")
    root_logger.info("=" * 100)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Module name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def log_performance(logger: logging.Logger, operation: str, start_time: float, 
                   additional_info: Optional[dict] = None):
    """
    Helper function to log performance metrics consistently.
    
    Args:
        logger: Logger instance
        operation: Name of the operation
        start_time: Start time from time.perf_counter()
        additional_info: Additional information to log
    """
    execution_time = time.perf_counter() - start_time
    
    if additional_info:
        info_str = " | ".join([f"{k}: {v}" for k, v in additional_info.items()])
        logger.info(f"⏱️  {operation} completed in {execution_time:.2f}s | {info_str}")
    else:
        logger.info(f"⏱️  {operation} completed in {execution_time:.2f}s")

def log_error(logger: logging.Logger, operation: str, error: Exception, 
              start_time: Optional[float] = None, additional_info: Optional[dict] = None):
    """
    Helper function to log errors consistently.
    
    Args:
        logger: Logger instance
        operation: Name of the operation that failed
        error: Exception that occurred
        start_time: Start time if available
        additional_info: Additional information to log
    """
    if start_time:
        execution_time = time.perf_counter() - start_time
        time_info = f" after {execution_time:.2f}s"
    else:
        time_info = ""
    
    if additional_info:
        info_str = " | ".join([f"{k}: {v}" for k, v in additional_info.items()])
        logger.error(f"❌ {operation} failed{time_info} | {info_str} | Error: {str(error)}")
    else:
        logger.error(f"❌ {operation} failed{time_info} | Error: {str(error)}")

# Import time module for the helper functions
import time
