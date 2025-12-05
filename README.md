# Trip Map Visualizer

Create interactive animated maps from your trip data! Watch a marker travel along your route with smooth animations, showing both flight and driving segments.

## Features

- 📍 Automatically geocodes place names to coordinates
- 🗺️ Creates interactive maps with markers for each location
- 🎬 **Animated playback** - Watch an orange marker travel along your entire route
- ⏯️ **Play/Pause controls** - Control the animation with an easy-to-use button
- 📅 Connects locations chronologically based on dates
- ✈️ **Flight routes**: Blue dashed lines (straight geodesic)
- 🚗 **Car routes**: Green solid lines following actual roads
- 🎨 Color-coded markers (red=start, green=end, blue=middle points)
- 🔢 Numbered markers showing visit sequence

## Installation

```bash
pip install -r requirements.txt
```

## Usage

1. Create a CSV file with your trip data (see `example_trips.csv`):
   - Required columns: `date` and `place`
   - Optional column: `type` (values: `car`, `flight`, `drive`, `driving`)
   - Date format: YYYY-MM-DD (or any format pandas can parse)

2. Run the script:
```bash
python tripmap.py your_trips.csv
```

3. Open the generated `trip_map.html` in your browser!

4. Click the **"▶️ Play Trip Animation"** button to watch your journey!

### Custom output filename:
```bash
python tripmap.py your_trips.csv my_custom_map.html
```

### Using Google Maps for car routing (optional):
```bash
# Set your Google Maps API key
export GOOGLE_MAPS_API_KEY='your-api-key-here'

# Then run normally
python tripmap.py your_trips.csv
```

**Note**: Without a Google API key, the tool uses free OSRM routing which works great for most routes!

## Animation Features

The generated map includes an interactive animation that:
- Shows an **orange marker** that travels along your route
- Animates at **~20 frames per second** for smooth movement
- Can be **paused and resumed** at any time
- Shows all routes statically in the background
- Automatically moves through all segments (flights and drives)
- Displays a **restart button** when complete

## Example CSV Format

### With route types:
```csv
date,place,type
2024-01-15,"Paris, France",flight
2024-01-20,"Lyon, France",car
2024-01-25,"Marseille, France",car
2024-02-01,"Rome, Italy",flight
```

### Without route types (defaults to flight):
```csv
date,place
2024-01-15,"Paris, France"
2024-02-20,"Rome, Italy"
```

## Route Types

- **`flight`** or **`airline`**: Blue dashed straight line (geodesic)
- **`car`**, **`drive`**, or **`driving`**: Green solid line following roads

## How it works

1. Reads your CSV file
2. Sorts locations by date
3. Geocodes place names using OpenStreetMap (free!)
4. For each connection:
   - **Flights**: Draws straight dashed lines
   - **Car trips**: Fetches actual road routes (OSRM or Google Maps)
5. Creates an interactive Folium map with all routes
6. Injects custom JavaScript for smooth animation
7. Adds play/pause controls for interactive playback

## Google Maps API Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable "Directions API"
3. Create an API key
4. Set it as environment variable:
   ```bash
   export GOOGLE_MAPS_API_KEY='your-api-key-here'
   ```

Perfect for visualizing road trips, backpacking adventures, or any travel timeline with smooth animated playback!
