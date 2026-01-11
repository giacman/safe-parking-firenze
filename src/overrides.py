"""
Data Override Manager
Handles manual corrections for known data quality issues in the Open Data
"""

import os
import logging
import yaml
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DataOverrides:
    """Manages data overrides from configuration file"""

    def __init__(self, overrides_file: str = "config/overrides.yaml"):
        self.overrides_file = overrides_file
        self.exclude_entries: List[Dict] = []
        self.load_overrides()

    def load_overrides(self):
        """Load override configuration from YAML file"""
        if not os.path.exists(self.overrides_file):
            logger.warning(f"Overrides file not found: {self.overrides_file}")
            return

        try:
            with open(self.overrides_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if not config:
                logger.info("No overrides configured")
                return

            self.exclude_entries = config.get('exclude_entries', [])

            if self.exclude_entries:
                logger.info(f"Loaded {len(self.exclude_entries)} exclusion rules")
                for rule in self.exclude_entries:
                    street = rule.get('street_name', 'N/A')
                    day = rule.get('day_code', 'N/A')
                    reason = rule.get('reason', 'No reason specified')
                    logger.info(f"  - Exclude: {street} on {day} - {reason}")
            else:
                logger.info("No exclusion rules configured")

        except Exception as e:
            logger.error(f"Failed to load overrides: {e}")
            self.exclude_entries = []

    def should_exclude(self, street_data) -> bool:
        """
        Check if a street entry should be excluded based on override rules

        Args:
            street_data: StreetCleaningData object

        Returns:
            True if this entry should be excluded, False otherwise
        """
        if not self.exclude_entries:
            return False

        schedule = street_data.cleaning_schedule
        entry_street = schedule.get('street_name', '')
        entry_section = schedule.get('section', '')
        entry_day = schedule.get('day_of_week_code', '')

        for rule in self.exclude_entries:
            # Check street name (required)
            rule_street = rule.get('street_name')
            if not rule_street or rule_street != entry_street:
                continue

            # Check day code (required)
            rule_day = rule.get('day_code')
            if not rule_day or rule_day != entry_day:
                continue

            # Check section (optional - if specified, must match)
            rule_section = rule.get('section')
            if rule_section and rule_section != entry_section:
                continue

            # All conditions matched - exclude this entry
            reason = rule.get('reason', 'Matched exclusion rule')
            logger.info(f"Excluding: {entry_street} ({entry_day}) - {reason}")
            return True

        return False

    def filter_streets(self, streets: List) -> List:
        """
        Filter out excluded entries from a list of streets

        Args:
            streets: List of StreetCleaningData objects

        Returns:
            Filtered list with excluded entries removed
        """
        if not self.exclude_entries:
            return streets

        original_count = len(streets)
        filtered = [s for s in streets if not self.should_exclude(s)]
        excluded_count = original_count - len(filtered)

        if excluded_count > 0:
            logger.info(f"Filtered out {excluded_count} entries based on override rules")

        return filtered
