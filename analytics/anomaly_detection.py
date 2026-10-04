# analytics/anomaly_detection.py

import pandas as pd
from sklearn.cluster import DBSCAN
from utils.logging_setup import logging

def detect_anomalies(token_data):
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
