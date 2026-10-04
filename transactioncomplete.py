import json
import os
import asyncio
import traceback
import requests
from base64 import b64decode
from dotenv import load_dotenv

# Import from solders
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solana.rpc.types import TxOpts

# Import constants and instructions from spl.token
from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
from spl.token.instructions import (
    get_associated_token_address,
    create_associated_token_account,
)

# Define SYS_PROGRAM_ID manually
SYS_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")

load_dotenv()

async def main():
    # Constants
    NETWORK = os.getenv("QUICKNODE_NETWORK")
    async_client = AsyncClient(NETWORK)
    print(f"Using RPC endpoint: {NETWORK}")

    # Load the wallet from keypair.json
    try:
        with open("keypair.json", "r") as f:
            secret_key_list = json.load(f)
            secret_key_bytes = bytes(secret_key_list)  # Should be 64 bytes
            if len(secret_key_bytes) != 64:
                print("Keypair JSON does not contain 64 bytes. Please provide the full keypair.")
                return
            wallet = Keypair.from_bytes(secret_key_bytes)
            public_key = wallet.pubkey()
            print(f"Loaded wallet with public key: {public_key}")
    except Exception as e:
        print(f"Error loading keypair: {e}")
        traceback.print_exc()
        return

    # Check the wallet balance
    try:
        balance_response = await async_client.get_balance(public_key)
        balance = balance_response.value  # Accessing the value attribute
        print(f"Wallet balance: {balance} lamports")
    except Exception as e:
        print(f"Error fetching balance: {e}")
        traceback.print_exc()
        return

    # Print the program IDs
    print(f"TOKEN_PROGRAM_ID: {TOKEN_PROGRAM_ID}")
    print(f"ASSOCIATED_TOKEN_PROGRAM_ID: {ASSOCIATED_TOKEN_PROGRAM_ID}")
    print(f"SYS_PROGRAM_ID: {SYS_PROGRAM_ID}")

    # Token mint addresses on Devnet
    source_token_mint = Pubkey.from_string("So11111111111111111111111111111111111111112")  # Wrapped SOL Devnet Mint
    target_token_mint = Pubkey.from_string("7XSsZLKfQv7YeEK4vKQ5qVZsc3zv6Szj1dgQY2VAnvL5")  # USDC Devnet Mint

    # Amount to swap (in smallest unit of the token)
    amount_in = 1_000_000_000  # 1 SOL in lamports
    slippage = 0.5  # Slippage tolerance in percent

    # Jupiter Devnet API endpoints
    JUPITER_QUOTE_API = "https://quote-api.jup.ag/dev/v4/quote"
    JUPITER_SWAP_API = "https://quote-api.jup.ag/dev/v4/swap"

    # Ensure the associated token account for USDC exists
    try:
        usdc_account = get_associated_token_address(public_key, target_token_mint)
        print(f"USDC Associated Token Account: {usdc_account}")

        # Check if the associated token account exists
        usdc_account_info = await async_client.get_account_info(usdc_account)
        if usdc_account_info.value is None:
            print("USDC associated token account does not exist. Creating it...")
            # Create the instruction to create associated token account
            create_ata_ix = create_associated_token_account(
                payer=public_key,
                owner=public_key,
                mint=target_token_mint,
            )
            # Get latest blockhash
            latest_blockhash_resp = await async_client.get_latest_blockhash()
            blockhash = latest_blockhash_resp.value.blockhash

            # Create transaction
            tx = Transaction()
            tx.add(create_ata_ix)
            tx.recent_blockhash = blockhash
            tx.fee_payer = public_key

            # Send the transaction and pass the wallet as signer
            response = await async_client.send_transaction(tx, wallet)
            print(f"Created USDC associated token account. Transaction signature: {response.value}")
        else:
            print("USDC associated token account already exists.")
    except Exception as e:
        print(f"Error creating or fetching USDC associated token account: {e}")
        traceback.print_exc()
        return

    # Get a swap quote from Jupiter API
    try:
        params = {
            "inputMint": str(source_token_mint),
            "outputMint": str(target_token_mint),
            "amount": str(amount_in),
            "slippageBps": int(slippage * 100),
            "userPublicKey": str(public_key),
        }
        response = requests.get(JUPITER_QUOTE_API, params=params)
        quote = response.json()
        if "data" not in quote or not quote["data"]:
            print(f"No quote data available: {quote}")
            return
        route = quote["data"][0]
        print("Obtained swap quote.")
    except Exception as e:
        print(f"Error obtaining swap quote: {e}")
        traceback.print_exc()
        return

    # Get the swap transaction from Jupiter API
    try:
        swap_params = {
            "route": route,
            "userPublicKey": str(public_key),
            "wrapUnwrapSOL": False,
        }
        swap_response = requests.post(JUPITER_SWAP_API, json=swap_params)
        swap_data = swap_response.json()
        if "swapTransaction" not in swap_data:
            print(f"Error in swap response: {swap_data}")
            return
        swap_transaction_encoded = swap_data["swapTransaction"]
        print("Obtained swap transaction from Jupiter API.")
    except Exception as e:
        print(f"Error obtaining swap transaction: {e}")
        traceback.print_exc()
        return

    # Decode and send the transaction
    try:
        swap_transaction_bytes = b64decode(swap_transaction_encoded)
        tx = Transaction.deserialize(swap_transaction_bytes)
        # Update recent blockhash
        latest_blockhash_resp = await async_client.get_latest_blockhash()
        blockhash = latest_blockhash_resp.value.blockhash
        tx.recent_blockhash = blockhash
        # Send the transaction and pass the wallet as signer
        response = await async_client.send_transaction(tx, wallet, opts=TxOpts(skip_preflight=True))
        print(f"Swap transaction sent with signature: {response.value}")
    except Exception as e:
        print(f"Error sending swap transaction: {e}")
        traceback.print_exc()
        return

    # Close the client connection
    await async_client.close()

if __name__ == "__main__":
    asyncio.run(main())
