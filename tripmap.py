#!/usr/bin/env python3
"""
Trip Map Visualizer
Reads a CSV file with date and place columns, plots locations on a map,
and connects them with lines based on chronological order.
"""

import pandas as pd
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import sys
from datetime import datetime


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
    for idx, place in enumerate(df[place_column], 1):
        print(f"[{idx}/{len(df)}] Geocoding: {place}...", end=" ")
        try:
            location = geocode(place)
            if location:
                coords.append((location.latitude, location.longitude))
                print(f"✓ ({location.latitude:.4f}, {location.longitude:.4f})")
            else:
                coords.append((None, None))
                print(f"✗ Not found")
        except Exception as e:
            coords.append((None, None))
            print(f"✗ Error: {type(e).__name__}")
    
    df['latitude'] = [c[0] for c in coords]
    df['longitude'] = [c[1] for c in coords]
    return df


def create_trip_map(csv_file, output_file='trip_map.html', date_column='date', place_column='place'):
    """Create an interactive map with markers and timeline connections."""
    
    # Read CSV
    df = pd.read_csv(csv_file)
    
    # Validate columns
    if date_column not in df.columns or place_column not in df.columns:
        print(f"Error: CSV must have '{date_column}' and '{place_column}' columns")
        print(f"Found columns: {', '.join(df.columns)}")
        sys.exit(1)
    
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
    
    # Connect locations with a line (chronological order)
    coordinates = df_valid[['latitude', 'longitude']].values.tolist()
    folium.PolyLine(
        coordinates,
        color='blue',
        weight=2,
        opacity=0.7,
        popup='Trip Route'
    ).add_to(trip_map)
    
    # Save map
    trip_map.save(output_file)
    print(f"\n✓ Map saved to: {output_file}")
    print(f"  Open this file in your web browser to view the trip map!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tripmap.py <csv_file> [output_file]")
        print("\nCSV file should have columns: date, place")
        print("Example: python tripmap.py trips.csv my_trip_map.html")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'trip_map.html'
    
    create_trip_map(csv_file, output_file)
