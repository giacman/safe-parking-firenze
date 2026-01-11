"""
Geometry utilities for calculating distances between points and streets
Uses simple mathematical distance calculations without heavy GIS libraries
"""

import math
from typing import Tuple, List
from haversine import haversine, Unit


def point_to_line_segment_distance(
    point: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float]
) -> float:
    """
    Calculate the minimum distance from a point to a line segment.
    Uses the Haversine formula for accurate Earth surface distances.

    Args:
        point: (lat, lon) of the point
        line_start: (lat, lon) of line segment start
        line_end: (lat, lon) of line segment end

    Returns:
        Distance in meters
    """
    # If the line segment is actually a point
    if line_start == line_end:
        return haversine(point, line_start, unit=Unit.METERS)

    # Convert to radians for calculations
    lat1, lon1 = math.radians(point[0]), math.radians(point[1])
    lat2, lon2 = math.radians(line_start[0]), math.radians(line_start[1])
    lat3, lon3 = math.radians(line_end[0]), math.radians(line_end[1])

    # Calculate the along-track distance and cross-track distance
    # This is a simplified approach using spherical geometry

    # Distance from start to point
    d13 = haversine(line_start, point, unit=Unit.METERS)

    # Distance from start to end of line segment
    d12 = haversine(line_start, line_end, unit=Unit.METERS)

    # If line segment is too short, just return distance to start
    if d12 < 1:  # Less than 1 meter
        return d13

    # Calculate bearing from start to end
    bearing12 = calculate_bearing(line_start, line_end)

    # Calculate bearing from start to point
    bearing13 = calculate_bearing(line_start, point)

    # Angular difference
    delta_bearing = abs(bearing13 - bearing12)
    while delta_bearing > 180:
        delta_bearing = 360 - delta_bearing

    # Cross-track distance
    cross_track = abs(d13 * math.sin(math.radians(delta_bearing)))

    # Along-track distance
    along_track = d13 * math.cos(math.radians(delta_bearing))

    # If the projection falls outside the line segment, return distance to nearest endpoint
    if along_track < 0:
        return haversine(point, line_start, unit=Unit.METERS)
    elif along_track > d12:
        return haversine(point, line_end, unit=Unit.METERS)
    else:
        return cross_track


def calculate_bearing(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    """
    Calculate the bearing from point1 to point2

    Args:
        point1: (lat, lon) of first point
        point2: (lat, lon) of second point

    Returns:
        Bearing in degrees (0-360)
    """
    lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
    lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])

    dlon = lon2 - lon1

    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    initial_bearing = math.atan2(x, y)

    # Convert to degrees and normalize to 0-360
    initial_bearing = math.degrees(initial_bearing)
    bearing = (initial_bearing + 360) % 360

    return bearing


def point_to_polyline_distance(
    point: Tuple[float, float],
    polyline: List[Tuple[float, float]]
) -> float:
    """
    Calculate the minimum distance from a point to a polyline (street).

    Args:
        point: (lat, lon) of the point
        polyline: List of (lat, lon) coordinates forming the street

    Returns:
        Minimum distance in meters
    """
    if not polyline:
        return float('inf')

    if len(polyline) == 1:
        return haversine(point, polyline[0], unit=Unit.METERS)

    min_distance = float('inf')

    # Check distance to each line segment
    for i in range(len(polyline) - 1):
        distance = point_to_line_segment_distance(
            point,
            polyline[i],
            polyline[i + 1]
        )
        min_distance = min(min_distance, distance)

    return min_distance


def convert_coordinates(coordinates: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Convert coordinates from (lon, lat) to (lat, lon) format if needed.

    KML files typically use (lon, lat) order, but most libraries expect (lat, lon).

    Args:
        coordinates: List of (lon, lat) tuples

    Returns:
        List of (lat, lon) tuples
    """
    return [(lat, lon) for lon, lat in coordinates]


def is_point_near_street(
    point_lat: float,
    point_lon: float,
    street_coordinates: List[Tuple[float, float]],
    max_distance_meters: float = 20.0
) -> Tuple[bool, float]:
    """
    Determine if a point is near a street within a given threshold.

    Args:
        point_lat: Latitude of the point
        point_lon: Longitude of the point
        street_coordinates: List of (lon, lat) coordinates from KML
        max_distance_meters: Maximum distance in meters to consider "near"

    Returns:
        Tuple of (is_near: bool, distance: float in meters)
    """
    # Convert to (lat, lon) format for calculations
    point = (point_lat, point_lon)
    polyline = convert_coordinates(street_coordinates)

    distance = point_to_polyline_distance(point, polyline)

    return (distance <= max_distance_meters, distance)
