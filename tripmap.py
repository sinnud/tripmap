#!/usr/bin/env python3
"""
Trip Map Visualizer
Reads a CSV file with date and place columns, plots locations on a map,
and connects them with lines based on chronological order.
Supports both flight (straight line) and car (road routing) connections.
"""

import pandas as pd
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import sys
import os
from datetime import datetime
import requests
import time
import polyline


def geocode_places(df, place_column='place'):
    """Convert place names to coordinates using geopy."""
    geolocator = Nominatim(
        user_agent="tripmap_visualizer",
        timeout=10
    )
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.5,
        max_retries=3,
        error_wait_seconds=2.0
    )
    
    coords = []
    locations_found = []
    for idx, place in enumerate(df[place_column], 1):
        print(f"[{idx}/{len(df)}] Geocoding: {place}...", end=" ")
        try:
            location = geocode(place)
            if location:
                coords.append((location.latitude, location.longitude))
                locations_found.append(location.address)
                print(f"✓ ({location.latitude:.4f}, {location.longitude:.4f})")
                # Show the interpreted address for verification
                if location.address:
                    # Extract country/region for quick verification
                    address_parts = location.address.split(', ')
                    if len(address_parts) >= 2:
                        region_info = ', '.join(address_parts[-2:])
                        print(f"      → Found: {region_info}")
            else:
                coords.append((None, None))
                locations_found.append(None)
                print(f"✗ Not found")
        except Exception as e:
            coords.append((None, None))
            locations_found.append(None)
            print(f"✗ Error: {type(e).__name__}")
    
    df['latitude'] = [c[0] for c in coords]
    df['longitude'] = [c[1] for c in coords]
    df['geocoded_address'] = locations_found
    return df


def get_driving_route(start_coords, end_coords, google_api_key=None):
    """
    Get driving route between two points using Google Maps Directions API.
    Falls back to OSRM if Google API key is not provided.
    Returns list of coordinate points along the route.
    """
    if google_api_key:
        # Use Google Maps Directions API
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                'origin': f"{start_coords[0]},{start_coords[1]}",
                'destination': f"{end_coords[0]},{end_coords[1]}",
                'mode': 'driving',
                'key': google_api_key
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 'OK':
                # Decode polyline from Google's encoded format
                encoded_polyline = data['routes'][0]['overview_polyline']['points']
                route_coords = polyline.decode(encoded_polyline)
                return route_coords
            else:
                print(f"    ⚠ Google routing failed: {data['status']}, using straight line")
                return None
        except Exception as e:
            print(f"    ⚠ Google routing error: {type(e).__name__}, using straight line")
            return None
    else:
        # Use OSRM (free, no API key required)
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}"
            params = {
                'overview': 'full',
                'geometries': 'polyline'
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data['code'] == 'Ok':
                # Decode polyline from OSRM
                encoded_polyline = data['routes'][0]['geometry']
                route_coords = polyline.decode(encoded_polyline)
                return route_coords
            else:
                print(f"    ⚠ OSRM routing failed, using straight line")
                return None
        except Exception as e:
            print(f"    ⚠ OSRM routing error: {type(e).__name__}, using straight line")
            return None


def create_trip_map(csv_file, output_file='trip_map.html', date_column='date', place_column='place', type_column='type'):
    """Create an interactive map with markers and timeline connections."""
    
    # Read CSV
    df = pd.read_csv(csv_file)
    
    # Validate columns
    if date_column not in df.columns or place_column not in df.columns:
        print(f"Error: CSV must have '{date_column}' and '{place_column}' columns")
        print(f"Found columns: {', '.join(df.columns)}")
        sys.exit(1)
    
    # Check if type column exists
    has_type_column = type_column in df.columns
    if not has_type_column:
        print(f"Note: No '{type_column}' column found, using straight lines for all connections")
        df[type_column] = 'flight'  # Default to flight (straight line)
    
    # Parse dates and sort by date
    df[date_column] = pd.to_datetime(df[date_column], format='mixed')
    df = df.sort_values(by=date_column).reset_index(drop=True)
    
    print(f"\nProcessing {len(df)} locations...")
    
    # Geocode places
    df = geocode_places(df, place_column)
    
    # Remove rows without valid coordinates
    df_valid = df.dropna(subset=['latitude', 'longitude'])
    
    if len(df_valid) == 0:
        print("\nError: No valid locations found!")
        sys.exit(1)
    
    print(f"\n{len(df_valid)} locations successfully geocoded")
    
    # Create map centered on the mean coordinates
    center_lat = df_valid['latitude'].mean()
    center_lon = df_valid['longitude'].mean()
    
    trip_map = folium.Map(location=[center_lat, center_lon], zoom_start=5)
    
    # Add markers for each location
    for idx, row in df_valid.iterrows():
        date_str = row[date_column].strftime('%Y-%m-%d')
        
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=f"<b>{row[place_column]}</b><br>{date_str}",
            tooltip=f"{row[place_column]} ({date_str})",
            icon=folium.Icon(color='red' if idx == 0 else ('green' if idx == len(df_valid) - 1 else 'blue'))
        ).add_to(trip_map)
        
        # Add date label
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            icon=folium.DivIcon(html=f'<div style="font-size: 10pt; color: black; font-weight: bold;">{idx+1}</div>')
        ).add_to(trip_map)
    
    # Connect locations with lines based on type (chronological order)
    print(f"\nDrawing route connections...")
    google_api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    if not google_api_key and has_type_column:
        print("  Note: GOOGLE_MAPS_API_KEY not set, using free OSRM routing for car trips")
    
    for i in range(len(df_valid) - 1):
        start_row = df_valid.iloc[i]
        end_row = df_valid.iloc[i + 1]
        
        start_coords = [start_row['latitude'], start_row['longitude']]
        end_coords = [end_row['latitude'], end_row['longitude']]
        
        trip_type = start_row.get(type_column, 'flight')
        if pd.isna(trip_type):
            trip_type = 'flight'
        trip_type = str(trip_type).lower().strip()
        
        # Determine if this is a car trip
        is_car = trip_type in ['car', 'drive', 'driving']
        
        if is_car:
            print(f"  [{i+1}→{i+2}] Car route: {start_row[place_column]} → {end_row[place_column]}", end="")
            route_coords = get_driving_route(start_coords, end_coords, google_api_key)
            
            if route_coords:
                print(f" ✓ ({len(route_coords)} points)")
                folium.PolyLine(
                    route_coords,
                    color='green',
                    weight=3,
                    opacity=0.8,
                    popup=f"🚗 Drive: {start_row[place_column]} → {end_row[place_column]}"
                ).add_to(trip_map)
            else:
                # Fallback to straight line
                print()
                folium.PolyLine(
                    [start_coords, end_coords],
                    color='green',
                    weight=3,
                    opacity=0.6,
                    dash_array='5, 5',
                    popup=f"🚗 Drive: {start_row[place_column]} → {end_row[place_column]}"
                ).add_to(trip_map)
            
            time.sleep(0.5)  # Rate limiting
        else:
            # Flight or default - straight line
            print(f"  [{i+1}→{i+2}] Flight: {start_row[place_column]} → {end_row[place_column]}")
            folium.PolyLine(
                [start_coords, end_coords],
                color='blue',
                weight=2,
                opacity=0.7,
                dash_array='10, 5',
                popup=f"✈️ Flight: {start_row[place_column]} → {end_row[place_column]}"
            ).add_to(trip_map)
    
    # Save map
    trip_map.save(output_file)
    print(f"\n✓ Map saved to: {output_file}")
    print(f"  Open this file in your web browser to view the trip map!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tripmap.py <csv_file> [output_file]")
        print("\nCSV file should have columns: date, place, [type]")
        print("  - type: 'car' or 'flight' (optional, defaults to flight)")
        print("\nFor car routes with Google Maps:")
        print("  export GOOGLE_MAPS_API_KEY='your-api-key'")
        print("  (Otherwise uses free OSRM routing)")
        print("\nExamples:")
        print("  python tripmap.py trips.csv")
        print("  python tripmap.py trips.csv my_trip_map.html")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'trip_map.html'
    
    create_trip_map(csv_file, output_file)
