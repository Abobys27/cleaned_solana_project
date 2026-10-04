# utils/config.py

import concurrent.futures
import os
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Executor for running synchronous code in async functions
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

# Configuration flag to enable or disable social media analysis
ENABLE_SOCIAL_MEDIA_ANALYSIS = True  # Set to False to bypass social media analysis

# Sentiment analysis model
sentiment_model_name = 'nlptown/bert-base-multilingual-uncased-sentiment'

# Solana client setup
HTTP_URL = "https://api.mainnet-beta.solana.com"
WSS_URL = "wss://api.mainnet-beta.solana.com"

# QuickNode session hash (if using QuickNode)
SESSION_HASH = f'QNDEMO{np.random.randint(1e9)}'

# Raydium program public key
RAYDIUM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

# Criteria thresholds
MIN_LIQUIDITY = 500_000    # Increased threshold
MIN_VOLUME_24H = 250_000   # Increased threshold
MIN_TOKEN_AGE_HOURS = 24
MIN_MENTION_VOLUME = 10    # Increased for more significant data
MIN_AVERAGE_SENTIMENT = 0.1  # Adjusted for stricter sentiment
