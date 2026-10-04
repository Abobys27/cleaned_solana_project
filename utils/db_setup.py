# utils/db_setup.py

import sqlite3
from datetime import datetime
from solana.rpc.async_api import AsyncClient
from utils.config import HTTP_URL
from utils.logging_setup import logging

# Initialize database connection
db_conn = sqlite3.connect('historical_data.db', check_same_thread=False)
db_cursor = db_conn.cursor()

# Create historical_data table if it doesn't exist
db_cursor.execute('''
    CREATE TABLE IF NOT EXISTS historical_data (
        timestamp TEXT,
        token_mint TEXT,
        token_symbol TEXT,
        liquidityUsd REAL,
        volumeUsd24h REAL,
        future_performance REAL
    )
''')
db_conn.commit()

def update_historical_data(token):
    """
    Updates the historical data in the SQLite database with the latest token information.

    Args:
        token (dict): The token data.
    """
    try:
        timestamp = datetime.utcnow().isoformat()
        token_mint = token['mint']
        token_symbol = token['symbol']
        liquidity_usd = token['liquidityUsd']
        volume_usd_24h = token['volumeUsd24h']

        # Insert data into the database
        db_cursor.execute('''
            INSERT INTO historical_data (timestamp, token_mint, token_symbol, liquidityUsd, volumeUsd24h)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, token_mint, token_symbol, liquidity_usd, volume_usd_24h))
        db_conn.commit()
    except Exception as e:
        logging.error(f"Error updating historical data: {e}")

def close_db_connection():
    """
    Closes the database connection.
    """
    db_conn.close()

# Initialize AsyncClient
solana_client = AsyncClient(endpoint=HTTP_URL)
