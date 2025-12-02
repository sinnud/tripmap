# Trip Map Visualizer

Create interactive maps from your trip data with places connected by timeline!

## Features

- 📍 Automatically geocodes place names to coordinates
- 🗺️ Creates interactive maps with markers for each location
- 📅 Connects locations with lines based on chronological order
- 🎨 Color-coded markers (red=start, green=end, blue=middle points)
- 🔢 Numbered markers showing visit sequence

## Installation

```bash
pip install -r requirements.txt
```

## Usage

1. Create a CSV file with your trip data (see `example_trips.csv`):
   - Required columns: `date` and `place`
   - Date format: YYYY-MM-DD (or any format pandas can parse)

2. Run the script:
```bash
python tripmap.py your_trips.csv
```

3. Open the generated `trip_map.html` in your browser!

### Custom output filename:
```bash
python tripmap.py your_trips.csv my_custom_map.html
```

## Example CSV Format

```csv
date,place
2024-01-15,Paris, France
2024-02-20,Rome, Italy
2024-03-10,Barcelona, Spain
```

## How it works

1. Reads your CSV file
2. Sorts locations by date
3. Geocodes place names using OpenStreetMap (free!)
4. Creates an interactive Folium map
5. Adds markers for each location
6. Connects them with lines showing your journey

Perfect for visualizing road trips, backpacking adventures, or any travel timeline!
