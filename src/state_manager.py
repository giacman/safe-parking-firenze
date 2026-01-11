"""
State Manager for persisting bot state to JSON files
Stores parking locations, favorite streets, and user preferences
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from threading import Lock

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistent state using JSON files"""

    def __init__(self, state_dir: str = "state"):
        self.state_dir = state_dir
        self.parking_file = os.path.join(state_dir, "parking.json")
        self.favorites_file = os.path.join(state_dir, "favorites.json")
        self.settings_file = os.path.join(state_dir, "settings.json")

        # Thread-safe file operations
        self._lock = Lock()

        # Create state directory if it doesn't exist
        os.makedirs(state_dir, exist_ok=True)

        # Initialize files if they don't exist
        self._initialize_files()

    def _initialize_files(self):
        """Create initial JSON files if they don't exist"""
        if not os.path.exists(self.parking_file):
            self._write_json(self.parking_file, {
                "current_parking": None,
                "history": []
            })

        if not os.path.exists(self.favorites_file):
            self._write_json(self.favorites_file, {
                "streets": []
            })

        if not os.path.exists(self.settings_file):
            self._write_json(self.settings_file, {
                "last_kml_update": None,
                "notifications_enabled": True
            })

    def _read_json(self, file_path: str) -> Dict:
        """Read JSON file with thread safety"""
        with self._lock:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
                return {}

    def _write_json(self, file_path: str, data: Dict):
        """Write JSON file with thread safety"""
        with self._lock:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error writing {file_path}: {e}")

    # Parking Location Methods

    def save_parking_location(
        self,
        latitude: float,
        longitude: float,
        street_name: str,
        street_description: str,
        next_cleaning: Optional[str] = None
    ):
        """Save current parking location"""
        data = self._read_json(self.parking_file)

        parking_info = {
            "latitude": latitude,
            "longitude": longitude,
            "street_name": street_name,
            "street_description": street_description,
            "next_cleaning_date": next_cleaning,
            "parked_at": datetime.now().isoformat(),
            "last_reminded": None
        }

        # Save previous parking to history
        if data.get("current_parking"):
            if "history" not in data:
                data["history"] = []
            data["history"].append(data["current_parking"])

            # Keep only last 10 parking spots in history
            data["history"] = data["history"][-10:]

        data["current_parking"] = parking_info
        self._write_json(self.parking_file, data)

        logger.info(f"Saved parking location: {street_name}")

    def get_current_parking(self) -> Optional[Dict]:
        """Get current parking location"""
        data = self._read_json(self.parking_file)
        return data.get("current_parking")

    def clear_parking_location(self):
        """Clear current parking location"""
        data = self._read_json(self.parking_file)

        if data.get("current_parking"):
            if "history" not in data:
                data["history"] = []
            data["history"].append(data["current_parking"])
            data["history"] = data["history"][-10:]

        data["current_parking"] = None
        self._write_json(self.parking_file, data)

        logger.info("Cleared parking location")

    def update_last_reminded(self):
        """Update the last reminded timestamp for current parking"""
        data = self._read_json(self.parking_file)

        if data.get("current_parking"):
            data["current_parking"]["last_reminded"] = datetime.now().isoformat()
            self._write_json(self.parking_file, data)

    def get_parking_history(self) -> List[Dict]:
        """Get parking history"""
        data = self._read_json(self.parking_file)
        return data.get("history", [])

    # Favorite Streets Methods

    def add_favorite_street(self, street_name: str, street_description: str = ""):
        """Add a street to favorites"""
        data = self._read_json(self.favorites_file)

        # Check if already exists
        for street in data.get("streets", []):
            if street["name"].lower() == street_name.lower():
                logger.info(f"Street {street_name} already in favorites")
                return

        favorite = {
            "name": street_name,
            "description": street_description,
            "added_at": datetime.now().isoformat()
        }

        if "streets" not in data:
            data["streets"] = []

        data["streets"].append(favorite)
        self._write_json(self.favorites_file, data)

        logger.info(f"Added favorite street: {street_name}")

    def remove_favorite_street(self, street_name: str) -> bool:
        """Remove a street from favorites"""
        data = self._read_json(self.favorites_file)

        if "streets" not in data:
            return False

        original_count = len(data["streets"])
        data["streets"] = [
            s for s in data["streets"]
            if s["name"].lower() != street_name.lower()
        ]

        if len(data["streets"]) < original_count:
            self._write_json(self.favorites_file, data)
            logger.info(f"Removed favorite street: {street_name}")
            return True

        return False

    def get_favorite_streets(self) -> List[Dict]:
        """Get list of favorite streets"""
        data = self._read_json(self.favorites_file)
        return data.get("streets", [])

    # Settings Methods

    def get_settings(self) -> Dict:
        """Get user settings"""
        return self._read_json(self.settings_file)

    def update_setting(self, key: str, value: Any):
        """Update a specific setting"""
        data = self._read_json(self.settings_file)
        data[key] = value
        self._write_json(self.settings_file, data)

    def get_last_kml_update(self) -> Optional[datetime]:
        """Get timestamp of last KML data update"""
        data = self._read_json(self.settings_file)
        last_update = data.get("last_kml_update")

        if last_update:
            return datetime.fromisoformat(last_update)
        return None

    def set_last_kml_update(self, timestamp: Optional[datetime] = None):
        """Set timestamp of last KML data update"""
        if timestamp is None:
            timestamp = datetime.now()

        self.update_setting("last_kml_update", timestamp.isoformat())

    def is_notifications_enabled(self) -> bool:
        """Check if notifications are enabled"""
        data = self._read_json(self.settings_file)
        return data.get("notifications_enabled", True)

    def set_notifications_enabled(self, enabled: bool):
        """Enable or disable notifications"""
        self.update_setting("notifications_enabled", enabled)
