"""
KML Parser for Florence Street Cleaning Data
Downloads and parses the Pulizia Strade KML file from Florence Open Data
"""

import os
import logging
import requests
import zipfile
import io
import re
from datetime import datetime, timedelta
from lxml import etree
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class StreetCleaningData:
    """Represents a street cleaning schedule entry"""

    def __init__(self, name: str, description: str, coordinates: List[Tuple[float, float]]):
        self.name = name
        self.description = description
        self.coordinates = coordinates  # List of (lon, lat) tuples
        self.cleaning_schedule = self._parse_schedule(description)

    def _parse_schedule(self, description: str) -> Dict:
        """
        Parse the cleaning schedule from the HTML description.
        Extracts structured data: street name, day of week, weeks, time range
        """
        schedule = {
            'raw_description': description,
            'street_name': None,
            'day_of_week': None,
            'day_of_week_code': None,
            'weeks': [],  # Which weeks of month (1-5)
            'time_start': None,
            'time_end': None,
            'weekly': False,  # True if every week
            'section': None,  # Street section
            'even_days': False,  # True if only even days of month
            'odd_days': False    # True if only odd days of month
        }

        # Day of week codes used in Florence data
        day_codes = {
            'LU': 0,  # Lunedì
            'MA': 1,  # Martedì
            'ME': 2,  # Mercoledì
            'GI': 3,  # Giovedì
            'VE': 4,  # Venerdì
            'SA': 5,  # Sabato
            'DO': 6   # Domenica
        }

        # Extract indirizzo (street name)
        match = re.search(r'<span class="atr-name">indirizzo</span>.*?<span class="atr-value">(.*?)</span>', description)
        if match:
            schedule['street_name'] = match.group(1).strip()

        # Extract giorno_settimana (day of week code)
        match = re.search(r'<span class="atr-name">giorno_settimana</span>.*?<span class="atr-value">(.*?)</span>', description)
        if match:
            day_code = match.group(1).strip()
            schedule['day_of_week_code'] = day_code
            schedule['day_of_week'] = day_codes.get(day_code)

        # Extract which weeks (prima_settimana through quinta_settimana)
        for week_num in range(1, 6):
            week_names = {
                1: 'prima_settimana',
                2: 'seconda_settimana',
                3: 'terza_settimana',
                4: 'quarta_settimana',
                5: 'quinta_settimana'
            }
            match = re.search(
                rf'<span class="atr-name">{week_names[week_num]}</span>.*?<span class="atr-value">(\d+)</span>',
                description
            )
            if match and match.group(1) == '1':
                schedule['weeks'].append(week_num)

        # Check if it's weekly (settimanale = 1)
        match = re.search(r'<span class="atr-name">settimanale</span>.*?<span class="atr-value">(\d+)</span>', description)
        if match and match.group(1) == '1':
            schedule['weekly'] = True

        # Extract time range
        match = re.search(r'<span class="atr-name">ora_inizio</span>.*?<span class="atr-value">(.*?)</span>', description)
        if match:
            schedule['time_start'] = match.group(1).strip()

        match = re.search(r'<span class="atr-name">ora_fine</span>.*?<span class="atr-value">(.*?)</span>', description)
        if match:
            schedule['time_end'] = match.group(1).strip()

        # Extract tratto_strada (street section)
        match = re.search(r'<span class="atr-name">tratto_strada</span>.*?<span class="atr-value">(.*?)</span>', description)
        if match:
            schedule['section'] = match.group(1).strip()

        # Check for pari (even days) - pari = 1 means even days only
        match = re.search(r'<span class="atr-name">pari</span>.*?<span class="atr-value">(\d+)</span>', description)
        if match and match.group(1) == '1':
            schedule['even_days'] = True

        # Check for dispari (odd days) - dispari = 1 means odd days only
        match = re.search(r'<span class="atr-name">dispari</span>.*?<span class="atr-value">(\d+)</span>', description)
        if match and match.group(1) == '1':
            schedule['odd_days'] = True

        return schedule

    def get_next_cleaning_date(self, from_date: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate the next cleaning date based on the schedule"""
        if from_date is None:
            from_date = datetime.now()

        if self.cleaning_schedule['day_of_week'] is None:
            return None

        target_day = self.cleaning_schedule['day_of_week']
        weekly = self.cleaning_schedule.get('weekly', False)
        weeks = self.cleaning_schedule.get('weeks', [])
        even_days = self.cleaning_schedule.get('even_days', False)
        odd_days = self.cleaning_schedule.get('odd_days', False)

        # If weekly cleaning, find next occurrence of that weekday
        if weekly or not weeks:
            days_ahead = (target_day - from_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # If today, schedule for next week
            next_date = from_date + timedelta(days=days_ahead)

            # Check even/odd constraint
            if even_days and next_date.day % 2 != 0:
                # Need even day, but got odd - try next week
                next_date = next_date + timedelta(days=7)
            elif odd_days and next_date.day % 2 == 0:
                # Need odd day, but got even - try next week
                next_date = next_date + timedelta(days=7)

            return next_date

        # For specific weeks of the month, find all possibilities in current and next month
        candidates = []

        for month_offset in range(0, 3):  # Check current month and next 2 months
            if from_date.month + month_offset <= 12:
                check_month = from_date.month + month_offset
                check_year = from_date.year
            else:
                check_month = (from_date.month + month_offset) % 12
                if check_month == 0:
                    check_month = 12
                check_year = from_date.year + ((from_date.month + month_offset - 1) // 12)

            first_of_month = datetime(check_year, check_month, 1)

            # Find all occurrences of target day in this month
            for week_num in weeks:
                cleaning_date = self._find_nth_weekday(first_of_month, target_day, week_num)
                if cleaning_date and cleaning_date > from_date:
                    # Check even/odd day constraint
                    day_of_month = cleaning_date.day

                    # Skip if doesn't match even/odd requirement
                    if even_days and day_of_month % 2 != 0:
                        continue  # Need even, got odd
                    if odd_days and day_of_month % 2 == 0:
                        continue  # Need odd, got even

                    candidates.append(cleaning_date)

        # Return the earliest future date
        if candidates:
            return min(candidates)

        return None

    def _find_nth_weekday(self, start_date: datetime, weekday: int, n: int) -> Optional[datetime]:
        """Find the nth occurrence of a weekday in the month starting from start_date"""
        # Move to the first occurrence of the target weekday
        days_to_add = (weekday - start_date.weekday()) % 7
        first_occurrence = start_date + timedelta(days=days_to_add)

        # Add weeks to get to the nth occurrence
        target_date = first_occurrence + timedelta(weeks=n-1)

        # Make sure we're still in the same month
        if target_date.month != start_date.month:
            return None

        return target_date


class KMLParser:
    """Parser for Florence street cleaning KML data"""

    def __init__(self, kml_url: str, cache_dir: str = "data", overrides=None):
        self.kml_url = kml_url
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "pulizia_strade.kml")
        self.streets: List[StreetCleaningData] = []
        self.overrides = overrides  # DataOverrides instance for filtering bad data

        os.makedirs(cache_dir, exist_ok=True)

    def download_kml(self, force: bool = False) -> bool:
        """Download the KML/KMZ file from the open data portal"""
        # Check if we have a recent cached version
        if not force and os.path.exists(self.cache_file):
            file_age = datetime.now() - datetime.fromtimestamp(
                os.path.getmtime(self.cache_file)
            )
            if file_age < timedelta(hours=24):
                logger.info(f"Using cached KML file (age: {file_age})")
                return True

        try:
            logger.info(f"Downloading from {self.kml_url}")
            response = requests.get(self.kml_url, timeout=30)
            response.raise_for_status()

            # Check if the file is a KMZ (ZIP) file by checking magic bytes
            content = response.content
            is_kmz = content[:2] == b'PK'  # ZIP file signature

            if is_kmz:
                logger.info("Detected KMZ (zipped KML) file, extracting...")
                try:
                    # Extract KML from KMZ
                    with zipfile.ZipFile(io.BytesIO(content)) as kmz:
                        # Find the KML file inside (usually named doc.kml or similar)
                        kml_files = [name for name in kmz.namelist() if name.endswith('.kml')]

                        if not kml_files:
                            logger.error("No KML file found inside KMZ archive")
                            return False

                        # Extract the first KML file found
                        kml_filename = kml_files[0]
                        logger.info(f"Extracting {kml_filename} from KMZ")

                        with kmz.open(kml_filename) as kml_file:
                            kml_content = kml_file.read()

                        # Write extracted KML to cache
                        with open(self.cache_file, 'wb') as f:
                            f.write(kml_content)

                except zipfile.BadZipFile as e:
                    logger.error(f"Failed to extract KMZ file: {e}")
                    return False
            else:
                # Direct KML file
                logger.info("Detected plain KML file")
                with open(self.cache_file, 'wb') as f:
                    f.write(content)

            logger.info(f"KML file saved successfully to {self.cache_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to download KML file: {e}")
            return False

    def parse_kml(self) -> List[StreetCleaningData]:
        """Parse the KML file and extract street cleaning data"""
        if not os.path.exists(self.cache_file):
            logger.error("KML file not found. Please download it first.")
            return []

        try:
            tree = etree.parse(self.cache_file)
            root = tree.getroot()

            # KML uses namespaces
            namespaces = {
                'kml': 'http://www.opengis.net/kml/2.2',
                'gx': 'http://www.google.com/kml/ext/2.2'
            }

            streets = []

            # Find all Placemark elements
            for placemark in root.findall('.//kml:Placemark', namespaces):
                name_elem = placemark.find('kml:name', namespaces)
                desc_elem = placemark.find('kml:description', namespaces)

                name = name_elem.text if name_elem is not None else "Unknown"
                description = desc_elem.text if desc_elem is not None else ""

                # Extract coordinates
                coordinates = []

                # Try LineString first
                linestring = placemark.find('.//kml:LineString/kml:coordinates', namespaces)
                if linestring is not None and linestring.text:
                    coords_text = linestring.text.strip()
                    for coord in coords_text.split():
                        parts = coord.split(',')
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            coordinates.append((lon, lat))

                # Try Polygon if LineString not found
                if not coordinates:
                    polygon = placemark.find('.//kml:Polygon//kml:coordinates', namespaces)
                    if polygon is not None and polygon.text:
                        coords_text = polygon.text.strip()
                        for coord in coords_text.split():
                            parts = coord.split(',')
                            if len(parts) >= 2:
                                lon, lat = float(parts[0]), float(parts[1])
                                coordinates.append((lon, lat))

                if coordinates:
                    street_data = StreetCleaningData(name, description, coordinates)
                    streets.append(street_data)

            logger.info(f"Parsed {len(streets)} street cleaning entries from KML")
            self.streets = streets
            return streets

        except Exception as e:
            logger.error(f"Failed to parse KML file: {e}")
            return []

    def load_data(self, force_download: bool = False) -> List[StreetCleaningData]:
        """Load street cleaning data (download and parse)"""
        if self.download_kml(force=force_download):
            streets = self.parse_kml()

            # Apply overrides if configured
            if self.overrides:
                streets = self.overrides.filter_streets(streets)

            self.streets = streets
            return streets
        return []
