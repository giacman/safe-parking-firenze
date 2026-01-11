#!/usr/bin/env python3
"""
Safe Parking Florence - Telegram Bot
Prevents parking fines by monitoring street cleaning schedules
"""

import os
import sys
import logging
import yaml
from pathlib import Path

from src.kml_parser import KMLParser
from src.state_manager import StateManager
from src.bot import SafeParkingBot
from src.scheduler import ReminderScheduler
from src.overrides import DataOverrides


def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from some libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.INFO)


def load_config(config_path: str = 'config/config.yaml') -> dict:
    """Load configuration from YAML file"""
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}")
        print("Please copy config/config.example.yaml to config/config.yaml and fill in your details")
        sys.exit(1)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)


def validate_config(config: dict):
    """Validate that all required configuration is present"""
    required_fields = {
        'telegram.bot_token': config.get('telegram', {}).get('bot_token'),
        'telegram.allowed_user_id': config.get('telegram', {}).get('allowed_user_id'),
        'open_data.kml_url': config.get('open_data', {}).get('kml_url'),
    }

    missing_fields = [
        field for field, value in required_fields.items()
        if not value or (isinstance(value, str) and 'YOUR_' in value.upper())
    ]

    if missing_fields:
        print("Error: Missing or invalid configuration fields:")
        for field in missing_fields:
            print(f"  - {field}")
        print("\nPlease update config/config.yaml with your actual values")
        sys.exit(1)


def main():
    """Main entry point"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Starting Safe Parking Florence Bot")
    logger.info("=" * 60)

    # Load and validate configuration
    config = load_config()
    validate_config(config)

    # Extract configuration
    telegram_config = config['telegram']
    open_data_config = config['open_data']
    parking_config = config.get('parking', {})

    bot_token = telegram_config['bot_token']
    allowed_user_id = telegram_config['allowed_user_id']
    kml_url = open_data_config['kml_url']

    max_distance = parking_config.get('max_distance_meters', 20)
    reminder_hours = parking_config.get('reminder_hours', [8, 20])
    warning_days = parking_config.get('warning_days_advance', 2)

    # Initialize components
    logger.info("Initializing components...")

    # Load data overrides (manual corrections for known data errors)
    overrides = DataOverrides(overrides_file='config/overrides.yaml')

    state_manager = StateManager(state_dir='state')
    kml_parser = KMLParser(kml_url=kml_url, cache_dir='data', overrides=overrides)

    # Load initial data
    logger.info("Loading street cleaning data...")
    streets = kml_parser.load_data()

    if not streets:
        logger.warning("No street cleaning data loaded. Bot will continue but won't have schedule information.")
        logger.warning("Try running with internet connection or check the KML URL in config.")
    else:
        logger.info(f"Loaded {len(streets)} street cleaning schedules")

    # Create bot instance
    bot = SafeParkingBot(
        token=bot_token,
        allowed_user_id=allowed_user_id,
        kml_parser=kml_parser,
        state_manager=state_manager,
        max_distance_meters=max_distance
    )

    # Create application
    app = bot.create_application()

    # Create and start scheduler
    logger.info("Setting up scheduler...")
    scheduler = ReminderScheduler(
        state_manager=state_manager,
        kml_parser=kml_parser,
        bot_instance=bot,
        allowed_user_id=allowed_user_id,
        reminder_hours=reminder_hours,
        warning_days_advance=warning_days
    )

    scheduler.start()
    logger.info(f"Scheduler started with reminders at: {reminder_hours}")

    # Start the bot
    logger.info("Bot is ready! Starting polling...")
    logger.info(f"Authorized user ID: {allowed_user_id}")

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        scheduler.stop()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        scheduler.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()
