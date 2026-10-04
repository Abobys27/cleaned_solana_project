# analbot

Async monitoring and analysis pipeline for newly launched tokens on Solana's Raydium DEX. Watches on-chain pool creation and new-token events in real time, then scores each token on liquidity/volume anomalies, social sentiment, and a lightweight performance model before logging it as a candidate worth a closer look.

## What it does

- **Live monitoring** — concurrently watches new token mints and Raydium pool creation logs via async tasks (`monitoring/`)
- **Anomaly detection** — flags tokens with unusual liquidity/volume profiles using DBSCAN clustering (`analytics/anomaly_detection.py`)
- **Sentiment analysis** — pulls recent Twitter and Reddit mentions for a token and scores them with a pretrained multilingual BERT sentiment model (`analytics/sentiment_analysis.py`)
- **Performance prediction** — fits a lightweight linear regression over a token's historical liquidity/volume data to estimate near-term trend (`analytics/performance_prediction.py`)
- **Persistence** — stores observed token snapshots in SQLite for later analysis (`utils/db_setup.py`)

A token only surfaces as a candidate once it clears configurable thresholds on liquidity, 24h volume, age, mention volume, and sentiment (`utils/config.py`).

## Stack

Python (asyncio), `aiohttp`, `solana-py`, `scikit-learn` (DBSCAN, linear regression), HuggingFace `transformers` (sentiment pipeline), `tweepy`, SQLite.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

Requires a `.env` with your own Twitter API bearer token and Solana RPC endpoint — see `utils/config.py` for the full list of environment-driven settings. **Never commit `.env` or any wallet keypair file.**

## Run

```bash
analbot
```

## Status

Personal project, built to learn async Python architecture and apply ML (clustering, regression, pretrained sentiment models) to a live data stream rather than a static dataset.
