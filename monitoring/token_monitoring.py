# monitoring/token_monitoring.py

import asyncio
import logging
from aiohttp import ClientSession
from data_fetching.token_data_fetching import fetch_tokens_and_pair_data
from analytics.sentiment_analysis import analyze_social_media
from analytics.anomaly_detection import detect_anomalies
from analytics.performance_prediction import predict_token_performance
from utils.db_setup import update_historical_data, solana_client
from utils.logging_setup import logging
from utils.config import (
    MIN_LIQUIDITY,
    MIN_VOLUME_24H,
    MIN_TOKEN_AGE_HOURS,
    MIN_MENTION_VOLUME,
    MIN_AVERAGE_SENTIMENT,
)
from monitoring.raydium_logs import get_token_creation_time

async def analyze_token(token):
    """
    Analyzes a single token to determine if it's a high-potential token.

    Args:
        token (dict): The token data.

    Returns:
        bool: True if the token is high-potential, False otherwise.
    """
    try:
        token_mint = token.get('mint')
        token_symbol = token.get('symbol', '').upper()
        logging.info(f"Analyzing token {token_symbol} ({token_mint})")

        # Skip tokens with symbol 'UNKNOWN'
        if token_symbol == 'UNKNOWN':
            return False

        total_liquidity = token.get('liquidityUsd', 0)
        total_volume_24h = token.get('volumeUsd24h', 0)

        # Update historical data
        update_historical_data(token)

        # Check liquidity and volume
        if total_liquidity < MIN_LIQUIDITY:
            return False

        if total_volume_24h < MIN_VOLUME_24H:
            return False

        # Check for anomalies
        anomalies = detect_anomalies([token])
        if token_mint in anomalies:
            return False

        # Check token age
        token_age_hours = await get_token_creation_time(token_mint, solana_client)
        if token_age_hours is None or token_age_hours < MIN_TOKEN_AGE_HOURS:
            return False

        # Social Media Analysis
        social_media_data = await analyze_social_media(token_symbol)
        if social_media_data is None:
            return False

        average_sentiment = social_media_data['average_sentiment']
        mention_volume = social_media_data['mention_volume']

        if mention_volume < MIN_MENTION_VOLUME or average_sentiment < MIN_AVERAGE_SENTIMENT:
            return False

        # Predict token performance
        predicted_performance = predict_token_performance(token)
        if predicted_performance is not None and predicted_performance < 0:
            return False

        logging.info(f"Token {token_symbol} passed analysis.")
        return True
    except Exception as e:
        logging.error(f"Error analyzing token {token_symbol}: {e}")
        return False

async def monitor_new_tokens():
    """
    Monitors and analyzes new tokens by fetching data and performing analysis.
    """
    existing_tokens = set()
    high_potential_tokens = []

    async with ClientSession() as session:
        try:
            while True:
                try:
                    tokens = await fetch_tokens_and_pair_data(session)

                    logging.info(f"Processing {len(tokens)} tokens.")

                    # Analyze tokens concurrently
                    tasks = []
                    token_list = []
                    for token in tokens:
                        token_id = token.get('mint')
                        if not token_id:
                            logging.error(f"Token missing 'mint' key: {token}")
                            continue

                        if token_id not in existing_tokens:
                            existing_tokens.add(token_id)
                            task = analyze_token(token)
                            tasks.append(task)
                            token_list.append(token)

                    results = await asyncio.gather(*tasks)

                    for token, should_buy in zip(token_list, results):
                        if should_buy:
                            token_symbol = token.get('symbol', '')
                            token_id = token.get('mint')
                            logging.info(f"Token {token_symbol} ({token_id}) is a high-potential token.")
                            high_potential_tokens.append((token_symbol, token_id))

                    if high_potential_tokens:
                        logging.info(f"High-potential tokens found: {high_potential_tokens}")
                        # Implement alerting or further processing here
                        # Reset high_potential_tokens after processing
                        high_potential_tokens = []
                    else:
                        logging.info("No high-potential tokens found in this cycle.")
                    await asyncio.sleep(60)  # Adjust as needed
                except Exception as e:
                    logging.error(f"Error: {e}")
                    logging.exception("Exception occurred")
                    await asyncio.sleep(60)
        finally:
            await solana_client.close()
