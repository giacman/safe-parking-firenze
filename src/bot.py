"""
Telegram Bot Handler for Safe Parking Florence
Handles all bot commands and user interactions
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.kml_parser import KMLParser, StreetCleaningData
from src.geometry import is_point_near_street
from src.state_manager import StateManager

logger = logging.getLogger(__name__)


class SafeParkingBot:
    """Main bot class handling all Telegram interactions"""

    def __init__(
        self,
        token: str,
        allowed_user_id: int,
        kml_parser: KMLParser,
        state_manager: StateManager,
        max_distance_meters: float = 20.0
    ):
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.kml_parser = kml_parser
        self.state_manager = state_manager
        self.max_distance_meters = max_distance_meters
        self.application: Optional[Application] = None

    def create_application(self) -> Application:
        """Create and configure the Telegram application"""
        self.application = Application.builder().token(self.token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("clear", self.clear_command))
        self.application.add_handler(CommandHandler("favorites", self.favorites_command))
        self.application.add_handler(CommandHandler("addfav", self.add_favorite_command))
        self.application.add_handler(CommandHandler("removefav", self.remove_favorite_command))
        self.application.add_handler(CommandHandler("refresh", self.refresh_data_command))

        # Handle location messages
        self.application.add_handler(
            MessageHandler(filters.LOCATION & ~filters.COMMAND, self.handle_location)
        )

        return self.application

    async def check_user_authorized(self, update: Update) -> bool:
        """Check if user is authorized to use the bot"""
        if update.effective_user.id != self.allowed_user_id:
            await update.message.reply_text(
                "⛔ Sorry, you are not authorized to use this bot."
            )
            return False
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not await self.check_user_authorized(update):
            return

        # Create custom keyboard with location button
        location_button = KeyboardButton("📍 Send Location", request_location=True)
        keyboard = ReplyKeyboardMarkup(
            [[location_button]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

        welcome_message = (
            "🚗 *Welcome to Safe Parking Florence!*\n\n"
            "I'll help you avoid parking fines by monitoring street cleaning schedules.\n\n"
            "*How to use:*\n"
            "1. Send me your location when you park\n"
            "2. I'll check if you're on a street with cleaning schedule\n"
            "3. I'll remind you before the next cleaning\n\n"
            "*Commands:*\n"
            "/status - Check your current parking\n"
            "/clear - Clear parking location\n"
            "/favorites - View favorite streets\n"
            "/addfav <street name> - Add favorite street\n"
            "/removefav <street name> - Remove favorite\n"
            "/refresh - Update street cleaning data\n"
            "/help - Show this help message"
        )

        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not await self.check_user_authorized(update):
            return

        await self.start_command(update, context)

    async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle location messages from the user"""
        if not await self.check_user_authorized(update):
            return

        location = update.message.location
        latitude = location.latitude
        longitude = location.longitude

        await update.message.reply_text("🔍 Checking your location...")

        # Find nearby streets with cleaning schedules
        nearby_streets = self._find_nearby_streets(latitude, longitude)

        if not nearby_streets:
            await update.message.reply_text(
                "ℹ️ No street cleaning schedule found for this location.\n"
                "You might be:\n"
                "• On a street without scheduled cleaning\n"
                "• Too far from mapped streets (>20m)\n"
                "• In an area not covered by the data"
            )
            return

        # Get the closest street
        closest_street = nearby_streets[0]
        street_data = closest_street['street']
        distance = closest_street['distance']

        # Extract street name from schedule
        street_name = street_data.cleaning_schedule.get('street_name', 'Unknown Street')
        schedule_formatted = self._format_schedule(street_data)

        # Calculate next cleaning date
        next_cleaning = street_data.get_next_cleaning_date()

        if next_cleaning:
            next_cleaning_str = next_cleaning.strftime("%A, %d %B %Y")
            days_until = (next_cleaning.date() - datetime.now().date()).days

            # Save parking location
            self.state_manager.save_parking_location(
                latitude=latitude,
                longitude=longitude,
                street_name=street_name,
                street_description=schedule_formatted,
                next_cleaning=next_cleaning.isoformat()
            )

            # Prepare message
            if days_until < 0:
                days_msg = "⚠️ *Cleaning was scheduled in the past!*"
            elif days_until == 0:
                days_msg = "🚨 *TODAY!*"
            elif days_until == 1:
                days_msg = "⚠️ *TOMORROW!*"
            else:
                days_msg = f"in *{days_until} days*"

            message = (
                f"✅ *Parking location saved!*\n\n"
                f"📍 *Street:* {street_name}\n"
                f"📏 *Distance:* {distance:.1f} meters\n"
                f"🧹 *Schedule:* {schedule_formatted}\n"
                f"📅 *Next cleaning:* {next_cleaning_str}\n"
                f"⏰ {days_msg}\n\n"
                f"I'll remind you before the cleaning!"
            )

            if days_until <= 1:
                message += "\n\n⚠️ *Please move your car soon!*"

        else:
            # Save without next cleaning date
            self.state_manager.save_parking_location(
                latitude=latitude,
                longitude=longitude,
                street_name=street_name,
                street_description=schedule_formatted,
                next_cleaning=None
            )

            message = (
                f"✅ *Parking location saved!*\n\n"
                f"📍 *Street:* {street_name}\n"
                f"📏 *Distance:* {distance:.1f} meters\n"
                f"🧹 *Schedule:* {schedule_formatted}\n\n"
                f"⚠️ Could not determine next cleaning date.\n"
                f"Please check the schedule manually."
            )

        await update.message.reply_text(message, parse_mode='Markdown')

    def _format_schedule(self, street_data) -> str:
        """Format cleaning schedule for display"""
        sched = street_data.cleaning_schedule

        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_names_it = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']

        parts = []

        # Day of week
        if sched.get('day_of_week') is not None:
            day_name = day_names_it[sched['day_of_week']]
            parts.append(f"Every {day_name}")

        # Weeks
        weeks = sched.get('weeks', [])
        if weeks and len(weeks) < 5:
            week_str = ", ".join([f"{w}°" for w in weeks])
            parts.append(f"week {week_str}")

        # Even/Odd days
        if sched.get('even_days'):
            parts.append("(even days)")
        elif sched.get('odd_days'):
            parts.append("(odd days)")

        # Time
        if sched.get('time_start') and sched.get('time_end'):
            parts.append(f"{sched['time_start']}-{sched['time_end']}")

        # Section
        if sched.get('section'):
            parts.append(f"[{sched['section']}]")

        return " ".join(parts) if parts else "Schedule unknown"

    def _find_nearby_streets(self, latitude: float, longitude: float) -> List[dict]:
        """Find streets near the given coordinates"""
        nearby = []

        for street in self.kml_parser.streets:
            is_near, distance = is_point_near_street(
                latitude,
                longitude,
                street.coordinates,
                self.max_distance_meters
            )

            if is_near:
                nearby.append({
                    'street': street,
                    'distance': distance
                })

        # Sort by distance
        nearby.sort(key=lambda x: x['distance'])

        return nearby

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not await self.check_user_authorized(update):
            return

        parking = self.state_manager.get_current_parking()

        if not parking:
            await update.message.reply_text(
                "ℹ️ No parking location saved.\n\n"
                "Send me your location when you park your car!"
            )
            return

        # Parse parking info
        street_name = parking.get('street_name', 'Unknown')
        parked_at = datetime.fromisoformat(parking['parked_at'])
        next_cleaning_str = parking.get('next_cleaning_date')

        parked_duration = datetime.now() - parked_at
        hours_parked = int(parked_duration.total_seconds() / 3600)

        message = (
            f"🚗 *Current Parking Status*\n\n"
            f"📍 *Street:* {street_name}\n"
            f"⏱ *Parked:* {hours_parked} hours ago\n"
            f"🧹 *Schedule:* {parking.get('street_description', 'N/A')}\n"
        )

        if next_cleaning_str:
            next_cleaning = datetime.fromisoformat(next_cleaning_str)
            next_cleaning_formatted = next_cleaning.strftime("%A, %d %B %Y")
            days_until = (next_cleaning.date() - datetime.now().date()).days

            if days_until < 0:
                days_msg = "⚠️ Cleaning was scheduled in the past!"
            elif days_until == 0:
                days_msg = "🚨 *TODAY!* Move your car now!"
            elif days_until == 1:
                days_msg = "⚠️ *TOMORROW!* Don't forget!"
            else:
                days_msg = f"in {days_until} days"

            message += (
                f"📅 *Next cleaning:* {next_cleaning_formatted}\n"
                f"⏰ {days_msg}"
            )
        else:
            message += "📅 *Next cleaning:* Unknown"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        if not await self.check_user_authorized(update):
            return

        self.state_manager.clear_parking_location()
        await update.message.reply_text(
            "✅ Parking location cleared!\n\n"
            "Send me your location when you park again."
        )

    async def favorites_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /favorites command"""
        if not await self.check_user_authorized(update):
            return

        favorites = self.state_manager.get_favorite_streets()

        if not favorites:
            await update.message.reply_text(
                "ℹ️ No favorite streets added yet.\n\n"
                "Use /addfav <street name> to add favorites."
            )
            return

        message = "⭐ *Your Favorite Streets:*\n\n"

        for i, fav in enumerate(favorites, 1):
            # Find the street in KML data to get next cleaning
            street_data = self._find_street_by_name(fav['name'])

            if street_data:
                next_cleaning = street_data.get_next_cleaning_date()
                if next_cleaning:
                    days_until = (next_cleaning.date() - datetime.now().date()).days
                    cleaning_info = f"Next: {next_cleaning.strftime('%d/%m')} ({days_until}d)"
                else:
                    cleaning_info = "Schedule unknown"
            else:
                cleaning_info = "Not found in data"

            message += f"{i}. *{fav['name']}*\n   {cleaning_info}\n\n"

        message += "\nUse /removefav <name> to remove a street"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def add_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addfav command"""
        if not await self.check_user_authorized(update):
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a street name.\n"
                "Example: /addfav VIA ROMA"
            )
            return

        street_name = " ".join(context.args).upper()

        # Check if street exists in data
        street_data = self._find_street_by_name(street_name)

        if street_data:
            actual_name = street_data.cleaning_schedule.get('street_name', street_name)
            schedule_formatted = self._format_schedule(street_data)

            self.state_manager.add_favorite_street(
                street_name=actual_name,
                street_description=schedule_formatted
            )
            await update.message.reply_text(
                f"✅ Added *{actual_name}* to favorites!\n\n"
                f"🧹 Schedule: {schedule_formatted}",
                parse_mode='Markdown'
            )
        else:
            # Still allow adding even if not found in current data
            self.state_manager.add_favorite_street(
                street_name=street_name,
                street_description=""
            )
            await update.message.reply_text(
                f"✅ Added *{street_name}* to favorites!\n\n"
                f"⚠️ Street not found in current data.\n"
                f"I'll monitor it when data is updated.",
                parse_mode='Markdown'
            )

    async def remove_favorite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removefav command"""
        if not await self.check_user_authorized(update):
            return

        if not context.args:
            await update.message.reply_text(
                "Please provide a street name.\n"
                "Example: /removefav VIA ROMA"
            )
            return

        street_name = " ".join(context.args).upper()

        if self.state_manager.remove_favorite_street(street_name):
            await update.message.reply_text(
                f"✅ Removed *{street_name}* from favorites!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ *{street_name}* not found in favorites.",
                parse_mode='Markdown'
            )

    async def refresh_data_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /refresh command"""
        if not await self.check_user_authorized(update):
            return

        await update.message.reply_text("🔄 Refreshing street cleaning data...")

        try:
            streets = self.kml_parser.load_data(force_download=True)
            self.state_manager.set_last_kml_update()

            await update.message.reply_text(
                f"✅ Data refreshed successfully!\n\n"
                f"📊 Loaded {len(streets)} street cleaning schedules."
            )
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            await update.message.reply_text(
                f"❌ Error refreshing data: {str(e)}"
            )

    def _find_street_by_name(self, street_name: str) -> Optional[StreetCleaningData]:
        """Find a street by name in the KML data, returning the entry with earliest next cleaning"""
        street_name_upper = street_name.upper()

        # Find all matching streets
        matching_streets = []
        for street in self.kml_parser.streets:
            actual_name = street.cleaning_schedule.get('street_name', '')
            if actual_name and street_name_upper in actual_name.upper():
                matching_streets.append(street)

        if not matching_streets:
            return None

        # If only one match, return it
        if len(matching_streets) == 1:
            return matching_streets[0]

        # Multiple matches - return the one with earliest next cleaning
        streets_with_dates = []
        for street in matching_streets:
            next_date = street.get_next_cleaning_date()
            if next_date:
                streets_with_dates.append((street, next_date))

        if streets_with_dates:
            # Sort by date and return earliest
            streets_with_dates.sort(key=lambda x: x[1])
            return streets_with_dates[0][0]

        # No dates found, return first match
        return matching_streets[0]

    async def send_reminder(self, chat_id: int, message: str):
        """Send a reminder message to the user"""
        if self.application:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )

    def run(self):
        """Run the bot"""
        if not self.application:
            self.create_application()

        logger.info("Starting bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
