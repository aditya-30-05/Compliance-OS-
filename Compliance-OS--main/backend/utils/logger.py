"""
Production logging configuration for ComplianceOS.
================================================
Features:
- Structured JSON logging for ELK/Sentry ingestion
- Context-aware tracing (request IDs)
- Dynamic log levels
"""

import sys
import json
import logging
from datetime import datetime
from backend.config import settings

class JSONFormatter(logging.Formatter):
    """Encodes log records to JSON string."""
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
            "env": settings.ENV
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

def setup_logger():
    """Configures the root logger with production settings."""
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.DEBUG:
        # Human readable in dev
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        # JSON in prod
        formatter = JSONFormatter()
        
    handler.setFormatter(formatter)
    
    logger = logging.getLogger("complianceos")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    logger.addHandler(handler)
    
    # Pre-configure external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logger

# Singleton instance
logger = setup_logger()
