"""
Structured logging and error handling configuration for AP Workflow Agent.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "ap_workflow"),
            "trace_id": getattr(record, "trace_id", None),
            "user_id": getattr(record, "user_id", None),
            "invoice_id": getattr(record, "invoice_id", None),
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno
        }
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_structured_logging():
    """
    Configure the root logger to use JSON formatting.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Remove default handlers to avoid duplicate logs
    for h in root_logger.handlers[:]:
        if not isinstance(h, logging.StreamHandler):
            root_logger.removeHandler(h)

    logging.info("Structured JSON logging initialized")
