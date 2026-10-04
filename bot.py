# bot.py

import asyncio
from monitoring.token_monitoring import monitor_new_tokens
from monitoring.raydium_logs import monitor_raydium_logs
from utils.db_setup import close_db_connection
from utils.logging_setup import logging

async def main():
    """
    The main entry point of the bot. Runs both monitoring tasks concurrently.
    """
    task1 = asyncio.create_task(monitor_new_tokens())
    task2 = asyncio.create_task(monitor_raydium_logs())
    await asyncio.gather(task1, task2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped manually.")
    finally:
        close_db_connection()
