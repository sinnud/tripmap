#!/usr/bin/env python3
"""
CSV Cleanup Tool for Trip Data
Validates dates and ensures proper CSV formatting with quoted place names.
Supports optional 'type' column for route types (car/flight).
"""

import pandas as pd
import sys
from pathlib import Path


def clean_trip_csv(input_file, output_file=None, date_column='date', place_column='place', type_column='type'):
    """
    Clean and validate trip CSV file.
    - Validates date format
    - Ensures proper quoting for place names with commas
    - Sorts by date
    """
    
    # Determine output filename
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.stem + '_clean' + input_path.suffix
    
    print(f"Reading: {input_file}")
    
    try:
        # Read CSV with proper handling of quoted fields
        df = pd.read_csv(input_file)
    except Exception as e:
        print(f"✗ Error reading CSV: {e}")
        sys.exit(1)
    
    # Validate required columns
    if date_column not in df.columns or place_column not in df.columns:
        print(f"✗ Error: CSV must have '{date_column}' and '{place_column}' columns")
        print(f"  Found columns: {', '.join(df.columns)}")
        sys.exit(1)
    
    # Check for optional type column
    has_type_column = type_column in df.columns
    if has_type_column:
        print(f"  Found {len(df)} rows with '{type_column}' column")
    else:
        print(f"  Found {len(df)} rows (no '{type_column}' column)")
    
    print(f"  Columns: {', '.join(df.columns)}")
    
    # Validate and parse dates
    print(f"\nValidating dates in '{date_column}' column...")
    original_dates = df[date_column].copy()
    
    try:
        df[date_column] = pd.to_datetime(df[date_column], format='mixed')
        valid_dates = df[date_column].notna()
        
        if valid_dates.all():
            print(f"  ✓ All {len(df)} dates are valid")
        else:
            invalid_count = (~valid_dates).sum()
            print(f"  ⚠ Warning: {invalid_count} invalid date(s) found:")
            for idx in df[~valid_dates].index:
                print(f"    Row {idx + 2}: '{original_dates[idx]}'")
            
            # Remove invalid dates
            df = df[valid_dates].reset_index(drop=True)
            print(f"  Keeping {len(df)} rows with valid dates")
    
    except Exception as e:
        print(f"✗ Error parsing dates: {e}")
        sys.exit(1)
    
    # Sort by date
    df = df.sort_values(by=date_column).reset_index(drop=True)
    print(f"  ✓ Sorted by date")
    
    # Format dates consistently
    df[date_column] = df[date_column].dt.strftime('%Y-%m-%d')
    
    # Check place names
    print(f"\nValidating places in '{place_column}' column...")
    empty_places = df[place_column].isna() | (df[place_column].str.strip() == '')
    
    if empty_places.any():
        print(f"  ⚠ Warning: {empty_places.sum()} empty place(s) found:")
        for idx in df[empty_places].index:
            print(f"    Row {idx + 2}: date={df.loc[idx, date_column]}")
        df = df[~empty_places].reset_index(drop=True)
        print(f"  Keeping {len(df)} rows with valid places")
    else:
        print(f"  ✓ All {len(df)} places are valid")
    
    # Strip whitespace from places
    df[place_column] = df[place_column].str.strip()
    
    # Validate and clean type column if present
    if has_type_column:
        print(f"\nValidating types in '{type_column}' column...")
        
        # Standardize type values
        df[type_column] = df[type_column].fillna('flight').str.lower().str.strip()
        
        # Map variations to standard values
        type_mapping = {
            'car': 'car',
            'drive': 'car',
            'driving': 'car',
            'flight': 'flight',
            'fly': 'flight',
            'airline': 'flight',
            'plane': 'flight'
        }
        
        df[type_column] = df[type_column].map(lambda x: type_mapping.get(x, 'flight'))
        
        # Count types
        type_counts = df[type_column].value_counts()
        print(f"  ✓ Route types:")
        for route_type, count in type_counts.items():
            icon = "🚗" if route_type == "car" else "✈️"
            print(f"    {icon} {route_type}: {count}")
    
    # Save with proper quoting (quotes fields with commas automatically)
    print(f"\nWriting cleaned CSV to: {output_file}")
    df.to_csv(output_file, index=False, quoting=1)  # quoting=1 means QUOTE_ALL
    
    print(f"✓ Done! Cleaned {len(df)} rows")
    print(f"\nSummary:")
    print(f"  Date range: {df[date_column].min()} to {df[date_column].max()}")
    print(f"  Locations: {len(df)}")
    if has_type_column:
        print(f"  Route types: {', '.join([f'{k}={v}' for k, v in type_counts.items()])}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python clean_csv.py <input_csv> [output_csv]")
        print("\nCleans and validates trip CSV files:")
        print("  - Validates date format")
        print("  - Ensures proper quoting for place names")
        print("  - Validates and standardizes 'type' column (if present)")
        print("  - Sorts by date")
        print("  - Removes invalid rows")
        print("\nSupported columns:")
        print("  - date (required): Trip date")
        print("  - place (required): Location name")
        print("  - type (optional): 'car', 'drive', 'flight', 'fly', etc.")
        print("\nExamples:")
        print("  python clean_csv.py 2025_trip.csv")
        print("  python clean_csv.py 2025_trip.csv 2025_trip_clean.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    clean_trip_csv(input_file, output_file)
