# 日志系统模块
import logging
import os
from datetime import datetime
import threading
import sys

import re

class GameLogger:
    """Game Logger System (Singleton)"""
    
    _instance = None
    _lock = threading.Lock()
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.logger = None
        self.log_file_path = None
        self.is_test_mode = False
        self._setup_logger()
    
    def _setup_logger(self):
        self.logger = logging.getLogger('game_logger')
        self.logger.setLevel(logging.INFO)
        # Clear existing handlers
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        # Optional: Add console handler for development visibility if needed, 
        # but user asked to NOT print to console.
        # So we leave it empty until start_game_session is called for file logging.
    
    def start_game_session(self, is_test: bool = False) -> str:
        """Start a new logging session."""
        self.is_test_mode = is_test
        
        # Log directory: UNO-RL/log
        # We assume this file is in UNO-RL/backend/utils/logger.py
        # So root is ../../../
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(base_dir, 'log')
        if is_test:
            log_dir = os.path.join(log_dir, 'test')
        else:
            log_dir = os.path.join(log_dir, 'game')
        
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "test_session" if is_test else "game_session"
        filename = f"{prefix}_{timestamp}.log"
        
        self.log_file_path = os.path.join(log_dir, filename)
        
        file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
        self.log_game_start()
        return self.log_file_path

    def end_game_session(self):
        if self.logger and self.log_file_path:
            self.logger.info("=" * 50)
            self.logger.info("Session Ended")
            self.logger.info("=" * 50)
            
            for handler in self.logger.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    self.logger.removeHandler(handler)
                    handler.close()
            self.log_file_path = None

    def log_game_start(self):
        if self.logger:
            self.logger.info("=" * 50)
            self.logger.info("Game Started")
            self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info("=" * 50)

    def strip_ansi(self, message: str) -> str:
        """Remove ANSI color codes from string."""
        return self.ANSI_ESCAPE.sub('', message)

    def log_info(self, message: str):
        if self.logger:
            self.logger.info(self.strip_ansi(message))

    def log_warning(self, message: str):
        if self.logger:
            self.logger.warning(self.strip_ansi(message))

    def log_error(self, message: str):
        if self.logger:
            self.logger.error(self.strip_ansi(message))

    # Aliases for compatibility with standard logging calls
    def info(self, message: str):
        self.log_info(message)

    def warning(self, message: str):
        self.log_warning(message)

    def error(self, message: str):
        self.log_error(message)

# Global Instance
game_logger = GameLogger()
