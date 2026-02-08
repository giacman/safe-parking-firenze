"""
Utility functions for generating Google Maps and Google Calendar URLs
"""

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote


def build_google_maps_url(parking: dict) -> Optional[str]:
    """
    Build a Google Maps URL for the parking location.
    
    Args:
        parking: Dictionary containing parking info with 'latitude' and 'longitude' keys
        
    Returns:
        Google Maps URL string, or None if no valid location data
    """
    latitude = parking.get('latitude', 0.0)
    longitude = parking.get('longitude', 0.0)
    street_name = parking.get('street_name', '')
    
    # If we have valid GPS coordinates, use them
    if latitude != 0.0 and longitude != 0.0:
        return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    
    # Otherwise, fall back to street name search
    if street_name:
        # Search for street name in Florence
        query = quote(f"{street_name}, Firenze, Italy")
        return f"https://www.google.com/maps/search/?api=1&query={query}"
    
    return None


def build_google_calendar_url(
    street_name: str,
    next_cleaning: datetime,
    description: str = ""
) -> str:
    """
    Build a Google Calendar event URL for the next cleaning.
    
    Args:
        street_name: Name of the street
        next_cleaning: Datetime of the next cleaning
        description: Optional description/schedule details
        
    Returns:
        Google Calendar event creation URL
    """
    # Format dates as YYYYMMDDTHHMMSS (local time)
    start_time = next_cleaning.strftime('%Y%m%dT%H%M%S')
    
    # Default duration: 2 hours (typical street cleaning window)
    # Calculate end time
    end_time = (next_cleaning + timedelta(hours=2)).strftime('%Y%m%dT%H%M%S')
    
    # Build event title
    title = quote(f"Street Cleaning: {street_name}")
    
    # Build event details
    details_parts = [f"Street cleaning scheduled for {street_name}"]
    if description:
        details_parts.append(f"Schedule: {description}")
    details = quote("\n".join(details_parts))
    
    # Build Google Calendar URL
    url = (
        f"https://calendar.google.com/calendar/render?"
        f"action=TEMPLATE&"
        f"text={title}&"
        f"dates={start_time}/{end_time}&"
        f"details={details}"
    )
    
    return url
