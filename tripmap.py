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
import argparse
import json


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


def create_animated_trip_map(csv_file, output_file='trip_map_animated.html', date_column='date', place_column='place', type_column='type'):
    """Create an animated map with a single moving marker traveling along routes (AllTrails style)."""
    
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
        df[type_column] = 'flight'
    
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
    
    # Get routing information if needed
    google_api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    if not google_api_key and has_type_column:
        print("  Note: GOOGLE_MAPS_API_KEY not set, using free OSRM routing for car trips")
    
    print(f"\nDrawing static routes...")
    
    # Store route data for animation
    route_segments = []
    all_coordinates = []
    
    # Add all routes as static lines (no animation on routes)
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
        
        # Get route coordinates
        if is_car:
            print(f"  [{i+1}→{i+2}] Car route: {start_row[place_column]} → {end_row[place_column]}", end="")
            route_coords = get_driving_route(start_coords, end_coords, google_api_key)
            if route_coords:
                print(f" ✓ ({len(route_coords)} points)")
                path_coords = route_coords
            else:
                print()
                path_coords = [start_coords, end_coords]
            
            # Add static route line
            folium.PolyLine(
                path_coords,
                color='green',
                weight=4,
                opacity=0.6,
                popup=f"🚗 Drive: {start_row[place_column]} → {end_row[place_column]}"
            ).add_to(trip_map)
            
            time.sleep(0.5)
        else:
            print(f"  [{i+1}→{i+2}] Flight: {start_row[place_column]} → {end_row[place_column]}")
            path_coords = [start_coords, end_coords]
            
            # Add static route line
            folium.PolyLine(
                path_coords,
                color='blue',
                weight=3,
                opacity=0.6,
                dash_array='10, 5',
                popup=f"✈️ Flight: {start_row[place_column]} → {end_row[place_column]}"
            ).add_to(trip_map)
        
        # Store segment info for animation
        route_segments.append({
            'start_idx': i,
            'end_idx': i + 1,
            'coords': path_coords,
            'is_car': is_car,
            'start_place': start_row[place_column],
            'end_place': end_row[place_column]
        })
    
    print(f"\nAdding destination markers...")
    
    # Add permanent markers for each location
    for idx, row in df_valid.iterrows():
        date_str = row[date_column].strftime('%Y-%m-%d')
        marker_color = 'red' if idx == 0 else ('green' if idx == len(df_valid) - 1 else 'blue')
        
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=8,
            popup=f"<b>{row[place_column]}</b><br>{date_str}<br>Stop {idx+1} of {len(df_valid)}",
            tooltip=f"{row[place_column]} ({date_str})",
            color='black',
            fillColor=marker_color,
            fillOpacity=0.9,
            weight=2
        ).add_to(trip_map)
    
    # Prepare data for JavaScript animation
    print(f"\nPreparing animation data...")
    
    # Build JavaScript arrays for animation
    js_segments = []
    for seg in route_segments:
        coords_js = [[lat, lon] for lat, lon in seg['coords']]
        js_segments.append({
            'path': coords_js,
            'iscar': seg['is_car'],
            'startPlace': seg['start_place'],
            'endPlace': seg['end_place']
        })
    
    # Save the base map first
    trip_map.save(output_file)
    
    # Now inject custom JavaScript for moving marker animation
    print(f"\nInjecting animation JavaScript...")
    
    with open(output_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Convert route segments to JSON
    js_segments_json = json.dumps(js_segments)
    
    # Find the map variable name from the HTML
    import re
    map_var_match = re.search(r'var (map_[a-f0-9]+) = L\.map\(', html_content)
    if not map_var_match:
        print("  Warning: Could not find map variable name, animation may not work")
        map_var_name = "map"
    else:
        map_var_name = map_var_match.group(1)
        print(f"  Found map variable: {map_var_name}")
    
    # Build animation script
    animation_script = f"""
    <script>
        // Animation data
        var routeSegments = ROUTE_SEGMENTS_PLACEHOLDER;
        
        var currentSegmentIndex = 0;
        var movingMarker = null;
        var isPlaying = false;
        var animationTimeoutId = null;
        var currentPointIndex = 0;
        var currentSegmentPath = [];
        
        // Wait for map to be fully loaded
        setTimeout(function() {{
            if (typeof {map_var_name} !== 'undefined') {{
                // Create custom control for play/pause
                var playControl = L.Control.extend({{
                    options: {{ position: 'topleft' }},
                    onAdd: function(map) {{
                        var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
                        container.style.background = 'white';
                        container.style.padding = '10px';
                        container.style.cursor = 'pointer';
                        
                        var playButton = L.DomUtil.create('button', '', container);
                        playButton.innerHTML = '▶️ Play Trip Animation';
                        playButton.id = 'playButton';
                        playButton.style.fontSize = '16px';
                        playButton.style.padding = '10px 20px';
                        playButton.style.border = 'none';
                        playButton.style.background = '#4CAF50';
                        playButton.style.color = 'white';
                        playButton.style.borderRadius = '5px';
                        playButton.style.cursor = 'pointer';
                        
                        L.DomEvent.on(playButton, 'click', function(e) {{
                            L.DomEvent.stopPropagation(e);
                            toggleAnimation();
                        }});
                        
                        return container;
                    }}
                }});
                
                {map_var_name}.addControl(new playControl());
            }} else {{
                console.error('Map variable not found');
            }}
        }}, 500);
        
        function toggleAnimation() {{
            var btn = document.getElementById('playButton');
            if (!isPlaying) {{
                if (currentSegmentIndex >= routeSegments.length) {{
                    // Reset animation
                    currentSegmentIndex = 0;
                    currentPointIndex = 0;
                    if (movingMarker) {{
                        movingMarker.remove();
                        movingMarker = null;
                    }}
                }}
                isPlaying = true;
                btn.innerHTML = '⏸️ Pause';
                btn.style.background = '#ff9800';
                startAnimation();
            }} else {{
                isPlaying = false;
                pauseAnimation();
                btn.innerHTML = '▶️ Resume';
                btn.style.background = '#4CAF50';
            }}
        }}
        
        function startAnimation() {{
            if (currentSegmentIndex >= routeSegments.length) {{
                var btn = document.getElementById('playButton');
                btn.innerHTML = '🔄 Restart Animation';
                btn.style.background = '#2196F3';
                isPlaying = false;
                return;
            }}
            
            animateSegment();
        }}
        
        function pauseAnimation() {{
            if (animationTimeoutId) {{
                clearTimeout(animationTimeoutId);
                animationTimeoutId = null;
            }}
        }}
        
        function animateSegment() {{
            var segment = routeSegments[currentSegmentIndex];
            currentSegmentPath = segment.path;
            
            if (currentPointIndex === 0) {{
                // Create marker at start of segment
                if (movingMarker) {{
                    movingMarker.remove();
                }}
                
                movingMarker = L.marker(currentSegmentPath[0], {{
                    icon: L.divIcon({{
                        className: 'moving-marker-icon',
                        html: '<div style="background-color: orange; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5);"></div>',
                        iconSize: [22, 22],
                        iconAnchor: [11, 11]
                    }})
                }}).addTo({map_var_name});
            }}
            
            // Animate through points
            var stepSize = Math.max(1, Math.floor(currentSegmentPath.length / 100));
            
            function animateStep() {{
                if (!isPlaying) {{
                    return;
                }}
                
                currentPointIndex += stepSize;
                
                if (currentPointIndex >= currentSegmentPath.length) {{
                    // Segment complete, move to next
                    currentPointIndex = 0;
                    currentSegmentIndex++;
                    
                    if (currentSegmentIndex < routeSegments.length) {{
                        setTimeout(function() {{
                            if (isPlaying) animateSegment();
                        }}, 500);
                    }} else {{
                        // All segments complete
                        var btn = document.getElementById('playButton');
                        btn.innerHTML = '🔄 Restart Animation';
                        btn.style.background = '#2196F3';
                        isPlaying = false;
                    }}
                    return;
                }}
                
                // Update marker position
                var point = currentSegmentPath[currentPointIndex];
                movingMarker.setLatLng(point);
                
                // Continue animation
                animationTimeoutId = setTimeout(animateStep, 50);
            }}
            
            animateStep();
        }}
    </script>
    <style>
        .moving-marker-icon {{
            z-index: 1000 !important;
        }}
    </style>
"""
    
    # Replace placeholder with actual data
    animation_script = animation_script.replace('ROUTE_SEGMENTS_PLACEHOLDER', js_segments_json)
    
    # Inject before </body>
    html_content = html_content.replace('</body>', animation_script + '\n</body>')
    
    # Write back
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Save map
    print(f"\n✓ Animated map saved to: {output_file}")
    print(f"  Open this file in your browser to see the AllTrails-style animation!")
    print(f"  - All routes are visible (static, no animation)")
    print(f"  - Click 'Play Trip Animation' to see a moving marker travel along your route")
    print(f"  - The marker moves from place to place, leaving markers behind")
    print(f"  - Green routes = car, Blue routes = flights")


def create_trip_map(csv_file, output_file='trip_map.html', date_column='date', place_column='place', type_column='type'):
    """Create a basic interactive map with markers and timeline connections (no animation).
    
    Note: This is a simpler version without animation. For animated maps with play/pause controls,
    use create_animated_trip_map() instead (which is the default when running from command line).
    """
    
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
    parser = argparse.ArgumentParser(
        description='Trip Map Visualizer - Create animated interactive maps from trip CSV data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tripmap.py trips.csv
  python tripmap.py trips.csv my_trip_map.html

CSV file should have columns: date, place, [type]
  - type: 'car', 'drive', 'driving' or 'flight' (optional, defaults to flight)

The generated map includes:
  - Interactive play/pause animation button
  - Smooth animated marker traveling along your route
  - All routes visible as static lines
  - Color-coded routes: green=car, blue=flight

For car routes with Google Maps:
  export GOOGLE_MAPS_API_KEY='your-api-key'
  (Otherwise uses free OSRM routing)
        """
    )
    
    parser.add_argument('csv_file', help='Path to CSV file with trip data')
    parser.add_argument('output_file', nargs='?', default='trip_map.html',
                        help='Output HTML file (default: trip_map.html)')
    
    args = parser.parse_args()
    
    # Create the map with animation
    create_animated_trip_map(args.csv_file, args.output_file)
