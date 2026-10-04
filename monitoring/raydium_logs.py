# monitoring/raydium_logs.py

import asyncio
import logging
from solders.pubkey import Pubkey
import json
import websockets
import aiohttp
from utils.logging_setup import logging
from utils.config import WSS_URL, SESSION_HASH, RAYDIUM_PROGRAM_ID, HTTP_URL

raydium_program_pubkey = RAYDIUM_PROGRAM_ID  # It's already a string


async def fetch_raydium_accounts(signature_str):
    """
    Fetches and processes Raydium accounts from a transaction signature.

    Args:
        signature_str (str): The transaction signature.
    """
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature_str,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0
                    }
                ]
            }
            async with session.post(HTTP_URL, json=payload) as response:
                result = await response.json()
                if 'result' not in result or not result['result']:
                    logging.error(f"Transaction not found: {signature_str}")
                    return
                transaction = result['result']
                instructions = transaction['transaction']['message']['instructions']
                for ix in instructions:
                    if ix['programId'] == raydium_program_pubkey:
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
                            logging.info(f"Transaction: https://solscan.io/tx/{signature_str}")
                            logging.info(f"Token A Account: {token_a_account}")
                            logging.info(f"Token B Account: {token_b_account}")
                            # Further processing can be added here
                        else:
                            logging.info("Not enough accounts in the transaction.")
    except Exception as e:
        logging.error(f"Error fetching Raydium accounts for transaction {signature_str}: {e}")


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
                            "mentions": [raydium_program_pubkey]
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
