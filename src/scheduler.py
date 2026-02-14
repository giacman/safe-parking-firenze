"""
Scheduler for periodic tasks and reminders
Checks parking status and sends reminders about upcoming street cleaning
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.state_manager import StateManager
from src.kml_parser import KMLParser
from src.links import build_google_maps_url, build_google_calendar_url
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Manages scheduled tasks for reminders and data updates"""

    def __init__(
        self,
        state_manager: StateManager,
        kml_parser: KMLParser,
        bot_instance,  # SafeParkingBot instance
        allowed_user_id: int,
        reminder_hours: list = None,
        warning_days_advance: int = 2
    ):
        self.state_manager = state_manager
        self.kml_parser = kml_parser
        self.bot = bot_instance
        self.allowed_user_id = allowed_user_id
        self.warning_days_advance = warning_days_advance
        self.reminder_hours = reminder_hours or [8, 20]  # 8 AM and 8 PM by default

        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Start the scheduler"""
        # Add jobs for reminders at specified hours
        for hour in self.reminder_hours:
            self.scheduler.add_job(
                self.check_and_send_reminders,
                CronTrigger(hour=hour, minute=0),
                id=f'reminder_{hour}',
                name=f'Check reminders at {hour}:00'
            )

        # Add job to refresh data daily at midnight
        self.scheduler.add_job(
            self.refresh_kml_data,
            CronTrigger(hour=0, minute=30),
            id='refresh_data',
            name='Refresh KML data daily'
        )

        # Check favorites daily at noon
        self.scheduler.add_job(
            self.check_favorite_streets,
            CronTrigger(hour=12, minute=0),
            id='check_favorites',
            name='Check favorite streets'
        )

        # Daily countdown message (if enabled by user)
        self.scheduler.add_job(
            self.send_daily_countdown,
            CronTrigger(hour=20, minute=0),  # 8 PM daily
            id='daily_countdown',
            name='Send daily countdown message'
        )

        self.scheduler.start()
        logger.info(f"Scheduler started with reminders at hours: {self.reminder_hours}")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def check_and_send_reminders(self):
        """Check parking status and send reminders if needed"""
        try:
            logger.info("Checking parking status for reminders...")

            parking = self.state_manager.get_current_parking()

            if not parking:
                logger.info("No current parking location")
                return

            next_cleaning_str = parking.get('next_cleaning_date')

            if not next_cleaning_str:
                logger.info("No next cleaning date for current parking")
                return

            next_cleaning = datetime.fromisoformat(next_cleaning_str)
            now = datetime.now()
            days_until = (next_cleaning.date() - now.date()).days

            # Treat the day BEFORE cleaning as the last valid day.
            # On the cleaning day itself (days_until == 0) it's already too late,
            # so we clear the parking location and stop sending reminders.
            if days_until <= 0:
                # Cleaning day reached or passed, clear parking
                logger.info("Cleaning day reached or passed, clearing parking location")
                self.state_manager.clear_parking_location()
                return

            # Check if we should send a reminder
            should_remind = False
            urgency_level = "info"

            if days_until == 1:
                # Last day to move the car (cleaning is tonight / tomorrow morning)
                should_remind = True
                urgency_level = "high"

            elif 1 < days_until <= self.warning_days_advance:
                # Within warning window (2, 3, ... days before)
                should_remind = True
                urgency_level = "medium"

            if not should_remind:
                logger.info(f"No reminder needed. Cleaning in {days_until} days")
                return

            # Check if we already sent a reminder recently (within last 6 hours)
            last_reminded = parking.get('last_reminded')
            if last_reminded:
                last_reminded_dt = datetime.fromisoformat(last_reminded)
                hours_since_last = (now - last_reminded_dt).total_seconds() / 3600

                if hours_since_last < 6:
                    logger.info(f"Already reminded {hours_since_last:.1f} hours ago")
                    return

            # Prepare and send reminder message
            street_name = parking.get('street_name', 'Unknown')
            next_cleaning_formatted = next_cleaning.strftime("%A, %d %B %Y at %H:%M")

            if urgency_level == "high":
                # Last-day alert: cleaning is coming up very soon
                message = (
                    f"⚠️ *LAST DAY TO MOVE YOUR CAR* ⚠️\n\n"
                    f"Street cleaning is *TONIGHT / TOMORROW* on:\n"
                    f"📍 {street_name}\n"
                    f"📅 {next_cleaning_formatted}\n\n"
                    f"Don't forget to move your car!"
                )
            else:
                # Medium urgency: multiple days in advance
                message = (
                    f"🔔 *Parking Reminder*\n\n"
                    f"Street cleaning in *{days_until} days* on:\n"
                    f"📍 {street_name}\n"
                    f"📅 {next_cleaning_formatted}\n\n"
                    f"Remember to move your car!"
                )
            
            # Build inline keyboard with Google Maps and Calendar buttons
            keyboard_buttons = []
            maps_url = build_google_maps_url(parking)
            if maps_url:
                keyboard_buttons.append([InlineKeyboardButton("📍 Open in Google Maps", url=maps_url)])
            
            calendar_url = build_google_calendar_url(
                street_name,
                next_cleaning,
                parking.get('street_description', '')
            )
            keyboard_buttons.append([InlineKeyboardButton("📅 Add to Google Calendar", url=calendar_url)])
            
            reply_markup = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

            await self.bot.send_reminder(self.allowed_user_id, message, reply_markup=reply_markup)

            # Update last reminded timestamp
            self.state_manager.update_last_reminded()

            logger.info(f"Reminder sent for {street_name} (urgency: {urgency_level})")

        except Exception as e:
            logger.error(f"Error in check_and_send_reminders: {e}", exc_info=True)

    async def check_favorite_streets(self):
        """Check favorite streets for upcoming cleaning and send notifications"""
        try:
            logger.info("Checking favorite streets...")

            favorites = self.state_manager.get_favorite_streets()

            if not favorites:
                logger.info("No favorite streets to check")
                return

            upcoming_cleanings = []

            for favorite in favorites:
                street_name = favorite['name']

                # Find the street in KML data
                street_data = self._find_street_by_name(street_name)

                if not street_data:
                    continue

                next_cleaning = street_data.get_next_cleaning_date()

                if not next_cleaning:
                    continue

                days_until = (next_cleaning.date() - datetime.now().date()).days

                # Only notify for days where you can still move the car:
                # 1..warning_days_advance days before cleaning.
                if 1 <= days_until <= self.warning_days_advance:
                    upcoming_cleanings.append({
                        'name': street_name,
                        'date': next_cleaning,
                        'days': days_until,
                        'description': street_data.description
                    })

            if not upcoming_cleanings:
                logger.info("No upcoming cleaning on favorite streets")
                return

            # Sort by days until cleaning
            upcoming_cleanings.sort(key=lambda x: x['days'])

            # Prepare message
            message = "⭐ *Favorite Streets Cleaning Alert* ⭐\n\n"

            for cleaning in upcoming_cleanings:
                if cleaning['days'] == 1:
                    when = "⚠️ *TONIGHT / TOMORROW*"
                else:
                    when = f"in {cleaning['days']} days"

                message += (
                    f"📍 *{cleaning['name']}*\n"
                    f"📅 {cleaning['date'].strftime('%A, %d %B %H:%M')}\n"
                    f"⏰ {when}\n"
                    f"🧹 {cleaning['description']}\n\n"
                )

            await self.bot.send_reminder(self.allowed_user_id, message)

            logger.info(f"Sent favorite streets alert for {len(upcoming_cleanings)} streets")

        except Exception as e:
            logger.error(f"Error in check_favorite_streets: {e}", exc_info=True)

    async def send_daily_countdown(self):
        """Send daily countdown message if countdown is enabled"""
        try:
            # Only send if countdown is enabled
            if not self.state_manager.is_countdown_enabled():
                return

            parking = self.state_manager.get_current_parking()

            if not parking:
                return

            next_cleaning_str = parking.get('next_cleaning_date')

            if not next_cleaning_str:
                return

            next_cleaning = datetime.fromisoformat(next_cleaning_str)
            now = datetime.now()
            days_until = (next_cleaning.date() - now.date()).days

            # Only send countdown if cleaning is in the future
            if days_until <= 0:
                return

            street_name = parking.get('street_name', 'Unknown')
            next_cleaning_formatted = next_cleaning.strftime("%A, %d %B %Y")

            # Build countdown message
            if days_until == 1:
                countdown_msg = "⏳ *1 giorno rimasto*"
                urgency_emoji = "⚠️"
            else:
                countdown_msg = f"⏳ *{days_until} giorni rimasti*"
                urgency_emoji = "📅"

            message = (
                f"{urgency_emoji} *Countdown Pulizia Strade*\n\n"
                f"📍 {street_name}\n"
                f"📅 Prossima pulizia: {next_cleaning_formatted}\n\n"
                f"{countdown_msg}"
            )

            # Build inline keyboard with Google Maps and Calendar buttons
            keyboard_buttons = []
            from src.links import build_google_maps_url, build_google_calendar_url
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            maps_url = build_google_maps_url(parking)
            if maps_url:
                keyboard_buttons.append([InlineKeyboardButton("📍 Open in Google Maps", url=maps_url)])

            calendar_url = build_google_calendar_url(
                street_name,
                next_cleaning,
                parking.get('street_description', '')
            )
            keyboard_buttons.append([InlineKeyboardButton("📅 Add to Google Calendar", url=calendar_url)])

            reply_markup = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

            await self.bot.send_reminder(self.allowed_user_id, message, reply_markup=reply_markup)

            logger.info(f"Sent daily countdown for {street_name} ({days_until} days remaining)")

        except Exception as e:
            logger.error(f"Error in send_daily_countdown: {e}", exc_info=True)

    async def refresh_kml_data(self):
        """Refresh KML data from the open data portal"""
        try:
            logger.info("Refreshing KML data...")

            streets = self.kml_parser.load_data(force_download=True)
            self.state_manager.set_last_kml_update()

            logger.info(f"KML data refreshed: {len(streets)} streets loaded")
            # Don't notify user on successful refresh - data source is static
            # Only notify on errors (see except block below)

        except Exception as e:
            logger.error(f"Error refreshing KML data: {e}", exc_info=True)

            # Notify user of error (only when refresh fails)
            error_message = (
                f"⚠️ *Data Update Failed*\n\n"
                f"Could not refresh street cleaning data.\n"
                f"Error: {str(e)}\n\n"
                f"The bot will continue using cached data."
            )

            try:
                await self.bot.send_reminder(self.allowed_user_id, error_message)
            except:
                pass

    def _find_street_by_name(self, street_name: str):
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
