# analytics.py

import asyncio
import logging
import os
import concurrent.futures
from dotenv import load_dotenv
import tweepy
from transformers import pipeline
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.linear_model import LinearRegression
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from logging.handlers import RotatingFileHandler
import websockets
import json
import sqlite3
from datetime import datetime
from aiohttp import ClientSession
import requests  # Added for Reddit API calls

# Import the token data fetching function
from token_data_fetching import fetch_tokens_and_pair_data

# Suppress Hugging Face symlink warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Load environment variables
load_dotenv()

# Twitter API credentials
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Initialize Twitter client
twitter_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

# Setup logging with file handler and log rotation
logging.basicConfig(
    level=logging.INFO,  # Set logging level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler('bot.log', maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
    ]
)

# Executor for running synchronous code in async functions
executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

# Configuration flag to enable or disable social media analysis
ENABLE_SOCIAL_MEDIA_ANALYSIS = True  # Set to False to bypass social media analysis

# Initialize sentiment analysis pipeline with a more advanced model
sentiment_pipeline = pipeline('sentiment-analysis', model='nlptown/bert-base-multilingual-uncased-sentiment')

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

# Raydium program public key
RAYDIUM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
raydium_program_pubkey = Pubkey.from_string(RAYDIUM_PROGRAM_ID)

# QuickNode session hash (if using QuickNode)
SESSION_HASH = f'QNDEMO{np.random.randint(1e9)}'

# Solana client setup
HTTP_URL = "https://api.mainnet-beta.solana.com"
WSS_URL = "wss://api.mainnet-beta.solana.com"

# Initialize AsyncClient
solana_client = AsyncClient(endpoint=HTTP_URL)

# Global constants
MAX_HISTORICAL_DATA_ENTRIES = 10000  # Adjust as needed


async def detect_anomalies(token_data):
    """
    Detects anomalies in token data using DBSCAN clustering.

    Args:
        token_data (list): A list of token dictionaries.

    Returns:
        list: A list of token mints identified as anomalies.
    """
    try:
        df = pd.DataFrame(token_data)
        if df.empty:
            return []
        features = df[['liquidityUsd', 'volumeUsd24h']].values

        # Use DBSCAN for anomaly detection
        clustering = DBSCAN(eps=0.5, min_samples=5).fit(features)
        df['cluster'] = clustering.labels_

        # Identify noise points (label == -1)
        anomalies = df[df['cluster'] == -1]
        logging.info(f"Detected {len(anomalies)} anomalies in token data.")
        return anomalies['mint'].tolist()
    except Exception as e:
        logging.error(f"Error in anomaly detection: {e}")
        return []


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

        # Limit the size of historical_data
        db_cursor.execute('SELECT COUNT(*) FROM historical_data')
        count = db_cursor.fetchone()[0]
        if count > MAX_HISTORICAL_DATA_ENTRIES:
            db_cursor.execute('''
                DELETE FROM historical_data WHERE timestamp IN (
                    SELECT timestamp FROM historical_data ORDER BY timestamp ASC LIMIT ?
                )
            ''', (count - MAX_HISTORICAL_DATA_ENTRIES,))
            db_conn.commit()
    except Exception as e:
        logging.error(f"Error updating historical data: {e}")


async def fetch_raydium_accounts(signature):
    """
    Fetches and processes Raydium accounts from a transaction signature.

    Args:
        signature (str): The transaction signature.
    """
    try:
        # Get transaction with parsed data
        tx = await solana_client.get_transaction(signature, encoding='jsonParsed', commitment='confirmed')
        transaction = tx.value
        if not transaction:
            logging.error(f"Transaction not found: {signature}")
            return
        instructions = transaction['transaction']['message']['instructions']
        # Find the instruction that matches the Raydium program
        for ix in instructions:
            if ix['programId'] == str(raydium_program_pubkey):
                accounts = ix.get('accounts', [])
                if not accounts:
                    logging.info("No accounts found in the transaction.")
                    return
                token_a_index = 8
                token_b_index = 9
                if len(accounts) > max(token_a_index, token_b_index):
                    token_a_account = accounts[token_a_index]
                    token_b_account = accounts[token_b_index]
                    logging.info("New LP Found")
                    logging.info(f"Transaction: https://solscan.io/tx/{signature}")
                    logging.info(f"Token A Account: {token_a_account}")
                    logging.info(f"Token B Account: {token_b_account}")
                    # Further processing can be added here
                else:
                    logging.info("Not enough accounts in the transaction.")
    except Exception as e:
        logging.error(f"Error fetching Raydium accounts for transaction {signature}: {e}")


async def analyze_social_media(token_symbol):
    """
    Performs sentiment analysis on social media mentions of a token.

    Args:
        token_symbol (str): The symbol of the token.

    Returns:
        dict or None: A dictionary with average sentiment and mention volume, or None if no data.
    """
    try:
        loop = asyncio.get_event_loop()
        twitter_task = loop.run_in_executor(executor, fetch_and_analyze_tweets, token_symbol)
        reddit_task = loop.run_in_executor(executor, fetch_and_analyze_reddit, token_symbol)
        twitter_result, reddit_result = await asyncio.gather(twitter_task, reddit_task)

        # Combine results
        if twitter_result and reddit_result:
            average_sentiment = (twitter_result['average_sentiment'] + reddit_result['average_sentiment']) / 2
            mention_volume = twitter_result['mention_volume'] + reddit_result['mention_volume']
        elif twitter_result:
            average_sentiment = twitter_result['average_sentiment']
            mention_volume = twitter_result['mention_volume']
        elif reddit_result:
            average_sentiment = reddit_result['average_sentiment']
            mention_volume = reddit_result['mention_volume']
        else:
            return None

        return {
            "average_sentiment": average_sentiment,
            "mention_volume": mention_volume
        }
    except Exception as e:
        logging.error(f"Error in analyze_social_media for {token_symbol}: {e}")
        return None


def fetch_and_analyze_tweets(token_symbol):
    """
    Fetches recent tweets about a token and performs sentiment analysis.

    Args:
        token_symbol (str): The symbol of the token.

    Returns:
        dict or None: A dictionary with average sentiment and mention volume, or None if no data.
    """
    try:
        query = f"#{token_symbol} OR {token_symbol} -is:retweet lang:en"
        tweets = twitter_client.search_recent_tweets(
            query=query,
            max_results=100,
            tweet_fields=["public_metrics"]
        )

        if not tweets.data:
            logging.info(f"No tweets found for {token_symbol}")
            return None

        tweet_texts = [tweet.text for tweet in tweets.data]

        # Advanced sentiment analysis using transformers
        sentiments = sentiment_pipeline(tweet_texts)
        sentiment_scores = []
        for result in sentiments:
            label = result['label']
            score = result['score']
            if '1 star' in label or '2 stars' in label:
                sentiment_scores.append(-score)
            elif '4 stars' in label or '5 stars' in label:
                sentiment_scores.append(score)
            else:
                sentiment_scores.append(0)

        average_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0
        mention_volume = len(tweet_texts)

        return {
            "average_sentiment": average_sentiment,
            "mention_volume": mention_volume
        }
    except Exception as e:
        logging.error(f"Error analyzing tweets for {token_symbol}: {e}")
        return None


def fetch_and_analyze_reddit(token_symbol):
    """
    Fetches recent Reddit posts about a token and performs sentiment analysis.

    Args:
        token_symbol (str): The symbol of the token.

    Returns:
        dict or None: A dictionary with average sentiment and mention volume, or None if no data.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_url = f"https://www.reddit.com/search.json?q={token_symbol}&limit=100"

        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            logging.error(f"Failed to fetch Reddit data for {token_symbol}")
            return None

        data = response.json()
        posts = data.get('data', {}).get('children', [])
        if not posts:
            logging.info(f"No Reddit posts found for {token_symbol}")
            return None

        post_texts = [post['data']['title'] + ' ' + post['data'].get('selftext', '') for post in posts]

        # Sentiment analysis
        sentiments = sentiment_pipeline(post_texts)
        sentiment_scores = []
        for result in sentiments:
            label = result['label']
            score = result['score']
            if '1 star' in label or '2 stars' in label:
                sentiment_scores.append(-score)
            elif '4 stars' in label or '5 stars' in label:
                sentiment_scores.append(score)
            else:
                sentiment_scores.append(0)

        average_sentiment = np.mean(sentiment_scores) if sentiment_scores else 0
        mention_volume = len(post_texts)

        return {
            "average_sentiment": average_sentiment,
            "mention_volume": mention_volume
        }
    except Exception as e:
        logging.error(f"Error analyzing Reddit for {token_symbol}: {e}")
        return None


async def analyze_token(token, solana_client):
    """
    Analyzes a single token to determine if it's a high-potential token.

    Args:
        token (dict): The token data.
        solana_client (AsyncClient): The Solana RPC client.

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

        # Criteria thresholds
        MIN_LIQUIDITY = 500_000  # Increased threshold
        MIN_VOLUME_24H = 250_000  # Increased threshold
        MIN_TOKEN_AGE_HOURS = 24
        MIN_MENTION_VOLUME = 10  # Increased for more significant data
        MIN_AVERAGE_SENTIMENT = 0.1  # Adjusted for stricter sentiment

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
        anomalies = await detect_anomalies([token])
        if token_mint in anomalies:
            return False

        # Check token age
        token_age_hours = await get_token_creation_time(token_mint, solana_client)
        if token_age_hours is None or token_age_hours < MIN_TOKEN_AGE_HOURS:
            return False

        # Social Media Analysis
        if ENABLE_SOCIAL_MEDIA_ANALYSIS:
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


def predict_token_performance(token):
    """
    Predicts token performance using Linear Regression based on historical data.

    Args:
        token (dict): The token data.

    Returns:
        float: The predicted performance score.
    """
    try:
        # Fetch historical data from the database
        df = pd.read_sql_query('SELECT * FROM historical_data WHERE token_mint = ?', db_conn, params=(token['mint'],))
        if df.empty or len(df) < 10:
            logging.info(f"Not enough historical data for prediction for token {token['symbol']}.")
            return None

        # Calculate future performance as the percentage change in liquidity over the next entry
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.sort_values('timestamp', inplace=True)

        df['liquidity_change'] = df['liquidityUsd'].pct_change().shift(-1)
        df.dropna(subset=['liquidity_change'], inplace=True)

        if df.empty:
            return None

        # Prepare data
        X = df[['liquidityUsd', 'volumeUsd24h']].values
        y = df['liquidity_change'].values

        # Train model
        model = LinearRegression()
        model.fit(X, y)

        # Predict future performance
        latest_data = np.array([[token['liquidityUsd'], token['volumeUsd24h']]])
        prediction = model.predict(latest_data)
        logging.info(f"Predicted future performance for {token['symbol']}: {prediction[0]}")
        return prediction[0]
    except Exception as e:
        logging.error(f"Error in token performance prediction for {token['symbol']}: {e}")
        return None


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
                            task = analyze_token(token, solana_client)
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


async def monitor_raydium_logs():
    """
    Monitors Raydium logs for new liquidity pools (LPs) using WebSocket.
    """
    uri = WSS_URL
    # Include headers if necessary
    extra_headers = {"x-session-hash": SESSION_HASH} if SESSION_HASH else None

    while True:
        try:
            async with websockets.connect(uri, extra_headers=extra_headers) as websocket:
                # Subscribe to logs for the Raydium program
                subscription_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [
                        {
                            "mentions": [str(raydium_program_pubkey)]
                        },
                        {
                            "commitment": "finalized"
                        }
                    ]
                }
                await websocket.send(json.dumps(subscription_request))
                response = await websocket.recv()
                response_data = json.loads(response)
                subscription_id = response_data.get("result")
                logging.info(f"Subscribed to logs with subscription ID: {subscription_id}")

                # Listen for log notifications
                while True:
                    try:
                        message = await websocket.recv()
                        message_data = json.loads(message)
                        if "method" in message_data and message_data["method"] == "logsNotification":
                            params = message_data["params"]
                            logs = params["result"]["value"]["logs"]
                            signature = params["result"]["value"]["signature"]
                            # Filter logs early to process only relevant ones
                            if any("initialize2" in log for log in logs):
                                logging.info(f"Signature for 'initialize2': {signature}")
                                await fetch_raydium_accounts(signature)
                    except websockets.ConnectionClosed:
                        logging.warning("WebSocket connection closed. Reconnecting...")
                        await asyncio.sleep(5)
                        break  # Exit the current connection and attempt to reconnect
                    except Exception as e:
                        logging.error(f"Error in monitor_raydium_logs: {e}")
        except Exception as e:
            logging.error(f"Failed to connect to WebSocket: {e}")
            await asyncio.sleep(5)  # Wait before retrying


async def get_token_creation_time(token_mint, solana_client):
    """
    Retrieves the creation time of a token based on its mint address.

    Args:
        token_mint (str): The mint address of the token.
        solana_client (AsyncClient): The Solana RPC client.

    Returns:
        float or None: The age of the token in hours, or None if not found.
    """
    try:
        response = await solana_client.get_account_info(Pubkey.from_string(token_mint))
        if response.value:
            slot = response.context.slot
            # Convert slot to approximate timestamp
            # Solana has approximately 400ms per slot
            current_slot_response = await solana_client.get_slot()
            current_slot = current_slot_response.value
            slots_since_creation = current_slot - slot
            hours_since_creation = (slots_since_creation * 0.4) / 3600  # Convert ms to hours
            return hours_since_creation
        else:
            logging.info(f"Token {token_mint} account not found.")
            return None
    except Exception as e:
        logging.error(f"Error fetching token creation time for {token_mint}: {e}")
        return None


async def main():
    """
    The main entry point of the analytics bot. Runs both monitoring tasks concurrently.
    """
    task1 = asyncio.create_task(monitor_new_tokens())
    task2 = asyncio.create_task(monitor_raydium_logs())
    await asyncio.gather(task1, task2)


# Run the analytical bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped manually.")
    finally:
        db_conn.close()
