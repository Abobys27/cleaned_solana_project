# token_data_fetching.py

import aiohttp
import logging
from solders.pubkey import Pubkey

async def fetch_tokens_and_pair_data(session):
    """
    Fetches token pair data from Raydium API and processes it to extract individual tokens.

    Args:
        session (aiohttp.ClientSession): The HTTP session to use for making requests.

    Returns:
        list: A list of dictionaries, each representing a unique token with its liquidity and volume.
    """
    pair_data_url = "https://api.raydium.io/pairs"
    try:
        async with session.get(pair_data_url) as response:
            if response.status != 200:
                logging.error(f"Failed to fetch pair data. HTTP status code: {response.status}")
                return []

            try:
                pair_data_response = await response.json()
            except Exception as e:
                logging.error(f"Error parsing pair data JSON: {e}")
                return []

            if isinstance(pair_data_response, list):
                pair_data = pair_data_response
                logging.info(f"Fetched {len(pair_data)} pairs from pair data.")
            else:
                logging.error("Unexpected pair data format: Not a list")
                pair_data = []

    except Exception as e:
        logging.error(f"Exception occurred while fetching pair data: {e}")
        return []

    # Log the first pair data item for debugging
    if len(pair_data) > 0:
        logging.info(f"First pair data item: {pair_data[0]}")

    # Process pairs to build tokens data
    tokens_data = {}
    for pair in pair_data:
        # Ensure 'pair' is a dictionary
        if not isinstance(pair, dict):
            logging.error(f"Invalid pair data format: {pair}")
            continue

        # Skip unofficial pairs
        if not pair.get('official', False):
            continue

        # Extract base and quote mints and symbols from 'pair_id' and 'name'
        pair_id = pair.get('pair_id')
        name = pair.get('name')

        if not pair_id or not name:
            continue

        # Attempt to split 'pair_id' and 'name' into base and quote tokens
        try:
            pair_id_parts = pair_id.split('-')
            name_parts = name.split('-')

            # Ensure there are at least two parts
            if len(pair_id_parts) < 2 or len(name_parts) < 2:
                logging.error(f"Error splitting pair_id or name: {pair_id}, {name}")
                continue

            base_mint = pair_id_parts[0]
            quote_mint = pair_id_parts[-1]
            base_symbol = name_parts[0].upper()
            quote_symbol = name_parts[-1].upper()
        except Exception as e:
            logging.error(f"Error processing pair_id or name: {pair_id}, {name}: {e}")
            continue

        # Handle 'UNKNOWN' symbols
        if base_symbol == 'UNKNOWN' or quote_symbol == 'UNKNOWN':
            continue

        liquidity_usd = float(pair.get('liquidity') or 0)
        volume_usd_24h = float(pair.get('volume_24h') or 0)

        # Update base token data
        if base_mint:
            token = tokens_data.setdefault(base_mint, {
                'mint': base_mint,
                'symbol': base_symbol,
                'liquidityUsd': 0,
                'volumeUsd24h': 0,
            })
            token['liquidityUsd'] += liquidity_usd
            token['volumeUsd24h'] += volume_usd_24h

        # Update quote token data
        if quote_mint:
            token = tokens_data.setdefault(quote_mint, {
                'mint': quote_mint,
                'symbol': quote_symbol,
                'liquidityUsd': 0,
                'volumeUsd24h': 0,
            })
            token['liquidityUsd'] += liquidity_usd
            token['volumeUsd24h'] += volume_usd_24h

    logging.info(f"Processed {len(tokens_data)} tokens from pair data.")
    return list(tokens_data.values())
