# analytics/performance_prediction.py

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from utils.db_setup import db_conn
from utils.logging_setup import logging

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
