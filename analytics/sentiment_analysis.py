# analytics/sentiment_analysis.py

import asyncio
import logging
import concurrent.futures
import numpy as np
from transformers import pipeline
from utils.logging_setup import logging
from utils.config import ENABLE_SOCIAL_MEDIA_ANALYSIS, executor, sentiment_model_name
import tweepy
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Twitter API credentials
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Initialize Twitter client
twitter_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

# Initialize sentiment analysis pipeline
sentiment_pipeline = pipeline('sentiment-analysis', model=sentiment_model_name)

async def analyze_social_media(token_symbol):
    """
    Performs sentiment analysis on social media mentions of a token.

    Args:
        token_symbol (str): The symbol of the token.

    Returns:
        dict or None: A dictionary with average sentiment and mention volume, or None if no data.
    """
    if not ENABLE_SOCIAL_MEDIA_ANALYSIS:
        return None

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
