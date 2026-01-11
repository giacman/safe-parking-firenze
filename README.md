# 🚗 Safe Parking Florence

A personal Telegram bot that prevents parking fines by monitoring street cleaning schedules in Florence, Italy using Open Data.

## 📋 Overview

This bot helps you avoid parking tickets by:
- Downloading and parsing Florence's street cleaning schedule from Open Data
- Detecting when you park on a street with scheduled cleaning
- Sending timely reminders before cleaning days
- Monitoring your favorite streets even when not parked there
- Using lightweight geometry calculations instead of heavy GIS libraries

## ✨ Features

- **Location-based detection**: Send your GPS location to check if you're parked on a scheduled street
- **Smart reminders**: Receive notifications at 8 AM and 8 PM when cleaning is upcoming
- **Favorite streets**: Monitor specific streets around your home
- **Countdown alerts**: Get warnings 2 days before, 1 day before, and on the cleaning day
- **Automatic data refresh**: Daily updates of street cleaning schedules
- **JSON persistence**: No database needed, everything stored in simple JSON files
- **Resource-efficient**: Designed to run on Google Cloud e2-micro (free tier)

## 🏗️ Architecture

### Technology Stack
- **Python 3.9+**: Main programming language
- **python-telegram-bot**: Telegram Bot API wrapper
- **lxml**: Fast KML/XML parsing
- **haversine**: Earth surface distance calculations
- **APScheduler**: Job scheduling for reminders
- **PyYAML**: Configuration management

### Design Decisions
- **No heavy GIS libraries**: Uses simple mathematical distance calculations instead of geopandas/gdal
- **No SQL database**: JSON files for state persistence (lightweight and portable)
- **Direct OS deployment**: Runs in Python venv without Docker (lower resource usage)
- **Async architecture**: Efficient handling of bot updates and scheduled tasks

## 📁 Project Structure

```
safe-parking-firenze/
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
├── .gitignore                # Git ignore rules
├── bot.log                   # Application logs
├── README.md                 # This file
├── config/
│   ├── config.yaml           # Your configuration (git-ignored)
│   └── config.example.yaml   # Configuration template
├── src/
│   ├── __init__.py
│   ├── bot.py                # Telegram bot handlers
│   ├── kml_parser.py         # KML data downloader and parser
│   ├── geometry.py           # Distance calculation utilities
│   ├── state_manager.py      # JSON persistence layer
│   └── scheduler.py          # Reminder scheduler
├── data/
│   └── pulizia_strade.kml    # Cached street cleaning data
└── state/
    ├── parking.json          # Current parking and history
    ├── favorites.json        # Favorite streets
    └── settings.json         # Bot settings
```

## 🚀 Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Telegram account
- Internet connection (for initial setup and data updates)

### 1. Create a Telegram Bot

1. Open Telegram and talk to [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the instructions
3. Choose a name (e.g., "Safe Parking Florence")
4. Choose a username (e.g., "safe_parking_firenze_bot")
5. Save the **bot token** you receive

### 2. Get Your Telegram User ID

1. Talk to [@userinfobot](https://t.me/userinfobot)
2. It will send you your user ID (a number like `123456789`)
3. Save this number

### 3. Clone and Setup the Project

```bash
# Navigate to your project directory
cd /path/to/safe-parking-firenze

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure the Bot

```bash
# Copy the example configuration
cp config/config.example.yaml config/config.yaml

# Edit the configuration with your values
nano config/config.yaml  # or use your preferred editor
```

Update these fields in `config/config.yaml`:

```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN_FROM_BOTFATHER"
  allowed_user_id: 123456789  # Your Telegram user ID

open_data:
  kml_url: "https://opendata.comune.fi.it/mobilita_sicurezza/pulizia_strade.kml"
  refresh_interval_hours: 24

parking:
  max_distance_meters: 20
  reminder_hours: [20, 8]  # 8 PM and 8 AM
  warning_days_advance: 2

favorite_streets:
  enabled: true
  streets:
    - "VIA EXAMPLE"
    # Add your favorite street names here
```

### 5. Run the Bot Locally

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Run the bot
python main.py
```

You should see output like:
```
2025-01-10 10:00:00 - __main__ - INFO - Starting Safe Parking Florence Bot
2025-01-10 10:00:00 - __main__ - INFO - Loading street cleaning data...
2025-01-10 10:00:00 - __main__ - INFO - Loaded 150 street cleaning schedules
2025-01-10 10:00:00 - __main__ - INFO - Bot is ready! Starting polling...
```

### 6. Test the Bot

1. Open Telegram and find your bot by username
2. Send `/start` to begin
3. Try these commands:
   - `/help` - See all commands
   - `/status` - Check parking status
   - `/favorites` - View favorite streets
   - Send your location to test parking detection

## 🛠️ Data Overrides (Fixing Data Errors)

The Florence Open Data may contain errors or outdated information. The bot includes an override system to manually exclude incorrect entries.

### How It Works

The bot loads override rules from `config/overrides.yaml` and filters out entries that match the exclusion criteria.

### Configuration File

Edit `config/overrides.yaml` to add exclusions:

```yaml
exclude_entries:
  # Example: BORGO TEGOLAIO has wrong section for Friday
  - street_name: "BORGO TEGOLAIO"
    section: "DA MICHELOZZI A MAZZETTA"
    day_code: "VE"  # VE = Venerdì (Friday)
    reason: "Wrong section - Friday should be DA MAZZETTA A VIA DEL CAMPUCCIO"
```

### Fields

- **street_name**: Exact street name (case-sensitive)
- **section**: Street section (optional - if omitted, matches any section)
- **day_code**: Italian day abbreviation
  - `LU` = Lunedì (Monday)
  - `MA` = Martedì (Tuesday)
  - `ME` = Mercoledì (Wednesday)
  - `GI` = Giovedì (Thursday)
  - `VE` = Venerdì (Friday)
  - `SA` = Sabato (Saturday)
  - `DO` = Domenica (Sunday)
- **reason**: Description (optional, for documentation)

### Example: Known Issues

**BORGO TEGOLAIO** - The Open Data incorrectly shows:
- Friday: "DA MICHELOZZI A MAZZETTA" (should be "DA MAZZETTA A VIA DEL CAMPUCCIO")
- Wednesday: "DA MICHELOZZI A MAZZETTA" (correct)

The default `overrides.yaml` excludes the incorrect Friday entry.

### Reporting Data Errors

If you find data errors, please report them to:
- Email: `opendata@comune.fi.it`
- Subject: "Errore dati Pulizia Strade"

This helps improve the dataset for everyone!

## ☁️ Deployment to Google Cloud

### Option 1: Google Cloud VM (e2-micro Free Tier)

#### 1. Create a VM Instance

```bash
# Create an e2-micro instance (free tier)
gcloud compute instances create safe-parking-bot \
    --zone=europe-west1-b \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=10GB \
    --boot-disk-type=pd-standard
```

#### 2. Connect to the VM

```bash
gcloud compute ssh safe-parking-bot --zone=europe-west1-b
```

#### 3. Install Dependencies on VM

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv git -y

# Create project directory
mkdir -p ~/safe-parking-firenze
cd ~/safe-parking-firenze
```

#### 4. Upload Your Code

From your local machine:

```bash
# Upload the project files (excluding venv and data)
gcloud compute scp --recurse \
    --exclude="venv/*" --exclude="data/*" --exclude="state/*" \
    ./* safe-parking-bot:~/safe-parking-firenze/ \
    --zone=europe-west1-b
```

#### 5. Setup and Run on VM

```bash
# On the VM
cd ~/safe-parking-firenze

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create and edit config
cp config/config.example.yaml config/config.yaml
nano config/config.yaml  # Add your bot token and user ID
```

#### 6. Create a Systemd Service (Run as daemon)

```bash
# Create service file
sudo nano /etc/systemd/system/safe-parking-bot.service
```

Add this content:

```ini
[Unit]
Description=Safe Parking Florence Telegram Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/safe-parking-firenze
Environment="PATH=/home/YOUR_USERNAME/safe-parking-firenze/venv/bin"
ExecStart=/home/YOUR_USERNAME/safe-parking-firenze/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_USERNAME` with your VM username (check with `whoami`).

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable safe-parking-bot
sudo systemctl start safe-parking-bot

# Check status
sudo systemctl status safe-parking-bot

# View logs
journalctl -u safe-parking-bot -f
```

#### 7. Useful Commands

```bash
# Check if bot is running
sudo systemctl status safe-parking-bot

# Restart the bot
sudo systemctl restart safe-parking-bot

# View logs
journalctl -u safe-parking-bot -f

# Stop the bot
sudo systemctl stop safe-parking-bot
```

### Resource Usage on e2-micro

The bot is designed to be extremely lightweight:
- **Memory**: ~50-80 MB
- **CPU**: Minimal (mostly idle, brief spikes during checks)
- **Storage**: ~20 MB for code + dependencies, < 1 MB for data
- **Network**: Minimal (only for Telegram API and daily data refresh)

Perfect fit for Google Cloud's e2-micro free tier (0.25-1 GB RAM, 1 vCPU).

## 🎯 Usage

### Basic Commands

- `/start` - Initialize the bot and see the welcome message
- `/help` - Display help information
- `/status` - Check current parking status and next cleaning
- `/clear` - Clear current parking location
- `/refresh` - Manually refresh street cleaning data

### Managing Favorites

- `/favorites` - List all favorite streets with next cleaning dates
- `/addfav VIA ROMA` - Add a street to favorites
- `/removefav VIA ROMA` - Remove a street from favorites

### Parking Flow

1. **Park your car**
2. **Open Telegram** and send your location to the bot
3. **Bot responds** with street name, cleaning schedule, and next cleaning date
4. **Receive reminders** automatically before cleaning day
5. **Send `/clear`** when you move your car

### How Reminders Work

The bot checks your parking status twice daily (8 AM and 8 PM) and sends reminders based on:

- **2+ days before**: Informational reminder
- **1 day before**: Important warning
- **On cleaning day**: Urgent alert

For favorite streets, the bot checks at noon and notifies you of any upcoming cleaning.

## 🔧 Configuration Options

### Parking Detection

```yaml
parking:
  max_distance_meters: 20  # Maximum distance to consider you "on" a street
```

Increase this if you're not getting matches, decrease for more accuracy.

### Reminder Schedule

```yaml
parking:
  reminder_hours: [8, 20]  # Check at 8 AM and 8 PM
  warning_days_advance: 2  # Start warning 2 days before
```

Customize when you want to receive reminders.

### Data Refresh

```yaml
open_data:
  refresh_interval_hours: 24  # Refresh data daily
```

The bot automatically downloads fresh data every 24 hours.

## 🐛 Troubleshooting

### Bot doesn't respond

1. Check the bot is running: `sudo systemctl status safe-parking-bot`
2. Check logs: `journalctl -u safe-parking-bot -f`
3. Verify your user ID matches the one in config
4. Ensure bot token is correct

### No street found when sending location

1. Make sure you're actually in Florence, Italy
2. Increase `max_distance_meters` in config
3. Check if data loaded successfully in logs
4. Try `/refresh` to update the street data

### Data not loading

1. Check internet connection
2. Verify KML URL is accessible: `curl -I https://opendata.comune.fi.it/mobilita_sicurezza/pulizia_strade.kml`
3. Check file permissions in `data/` directory
4. Look for errors in `bot.log`

### Memory issues on e2-micro

The bot is designed to be lightweight, but if you experience issues:

1. Check memory usage: `free -h`
2. Restart the service: `sudo systemctl restart safe-parking-bot`
3. Consider disabling other services on the VM

## 📊 Data Sources

The bot uses official Open Data from the Municipality of Florence:
- **Dataset**: Pulizia Strade (Street Cleaning)
- **Format**: KML (Keyhole Markup Language)
- **Update frequency**: Updated by the municipality as needed
- **License**: Open Data (check municipality website for specific license)

## 🔐 Security Notes

- The bot only accepts commands from your Telegram user ID (configured in `config.yaml`)
- Bot token and config are git-ignored to prevent accidental commits
- State files contain only parking locations and preferences (no sensitive data)
- All communication goes through Telegram's encrypted API

## 🛠️ Development

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot in debug mode
python main.py
```

### Adding Features

The modular structure makes it easy to extend:

- `src/bot.py` - Add new Telegram commands
- `src/scheduler.py` - Add new scheduled tasks
- `src/kml_parser.py` - Modify how schedule data is parsed
- `src/geometry.py` - Adjust distance calculations

### Logging

Logs are written to both `bot.log` and console. Adjust logging level in `main.py`:

```python
logging.basicConfig(level=logging.DEBUG)  # More verbose
logging.basicConfig(level=logging.WARNING)  # Less verbose
```

## 📝 License

This is a personal project. Feel free to fork and modify for your own use.

## 🙏 Acknowledgments

- Florence Municipality for providing Open Data
- Telegram Bot API for the excellent bot platform
- Python community for the great libraries used in this project

## 📮 Support

If you encounter issues:
1. Check the logs: `bot.log` or `journalctl -u safe-parking-bot -f`
2. Verify your configuration in `config/config.yaml`
3. Make sure you're using Python 3.9+
4. Ensure all dependencies are installed correctly

---

Made with ❤️ for Florence residents who are tired of parking fines!
