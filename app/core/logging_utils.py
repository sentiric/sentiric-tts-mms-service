import logging
import sys
import uvicorn.logging
from datetime import datetime
from pythonjsonlogger import jsonlogger
from app.core.config import settings

# Yakalanacak loglar
LOGGERS = ("uvicorn.asgi", "uvicorn.access", "uvicorn")

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # [FIX] Daha geniş kapsamlı filtreleme
        return record.getMessage().find("GET /health") == -1
        
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Production için JSON Formatter"""
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
        log_record['service'] = "tts-mms-service"
        log_record['env'] = settings.ENV

class RustStyleFormatter(logging.Formatter):
    """Development için Okunabilir Formatter"""
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    # [Zaman] [LEVEL] [Logger] Mesaj
    FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

    FORMATS = {
        logging.DEBUG: grey + FORMAT + reset,
        logging.INFO: green + FORMAT + reset,
        logging.WARNING: yellow + FORMAT + reset,
        logging.ERROR: red + FORMAT + reset,
        logging.CRITICAL: bold_red + FORMAT + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logging():
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.getLogger().handlers = []

    handler = logging.StreamHandler(sys.stdout)

    if settings.ENV == "development":
        handler.setFormatter(RustStyleFormatter())
    else:
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Uvicorn Loglarını Ele Geçir
    for logger_name in LOGGERS:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = []
        logging_logger.addHandler(handler)
        logging_logger.propagate = False

    # [FIX] Transformers Kütüphanesini Sustur
    logging.getLogger("transformers").setLevel(logging.ERROR)
    
    # [FIX] Access log logger'ına filtreyi zorla ekle
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

    logger = logging.getLogger("INIT")
    mode = "DEVELOPMENT (Pretty)" if settings.ENV == "development" else "PRODUCTION (JSON)"
    logger.info(f"Log system initialized in {mode}")