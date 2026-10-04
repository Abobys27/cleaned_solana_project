# utils/logging_setup.py

import logging
from logging.handlers import RotatingFileHandler

# Setup logging with file handler and log rotation
logging.basicConfig(
    level=logging.INFO,  # Set logging level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    ]
)
