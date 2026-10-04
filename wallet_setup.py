import json
import os
import asyncio
import traceback
from dotenv import load_dotenv
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

load_dotenv()

async def main():
    """
    Main function to load the wallet from keypair.json and check balance.
    """
    # Constants
    QUICKNODE_NETWORK = os.getenv("QUICKNODE_NETWORK")

    # Initialize RPC client
    client = AsyncClient(QUICKNODE_NETWORK, commitment=Confirmed)
    print(f"Using QuickNode RPC endpoint: {QUICKNODE_NETWORK}")

    # Load the wallet from keypair.json
    try:
        with open("keypair.json", "r") as f:
            keypair_list = json.load(f)
            keypair_bytes = bytes(keypair_list)
            wallet = Keypair.from_bytes(keypair_bytes)
            public_key = wallet.pubkey()
            print(f"Loaded wallet with public key: {public_key}")
    except FileNotFoundError:
        print("keypair.json file not found. Please ensure the file exists in the script directory.")
        return
    except Exception as e:
        print(f"Error loading keypair: {e}")
        traceback.print_exc()
        return

    # Check the balance using your QuickNode endpoint
    try:
        balance_response = await client.get_balance(public_key, commitment=Confirmed)
        print(f"Balance response: {balance_response}")
        balance = balance_response.value
        if balance is not None:
            print(f"Wallet balance: {balance} lamports")
        else:
            print(f"Error getting balance: {balance_response}")
    except Exception as e:
        print(f"Error fetching balance: {e}")
        traceback.print_exc()

    # Close the client connection
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
