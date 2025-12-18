import argparse
import sys
import time
from typing import Optional, Tuple
import re

import pandas as pd
import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# IMPORTANT: Per Nominatim usage policy, include a descriptive User-Agent with contact info.
# Replace the email below with your real contact email or project URL.
USER_AGENT = "Conway-GeoMap/1.0 (contact: danc@uark.edu)"


def geocode_address(address: str, country_codes: Optional[str] = None, timeout_seconds: int = 20) -> Tuple[float, float]:
    """Geocode an address to latitude and longitude using OpenStreetMap Nominatim.

    Args:
        address: Free-form address string.
        country_codes: Optional ISO 3166-1 alpha2 country code(s) to bias results, e.g. "us" or "us,ca".
        timeout_seconds: HTTP timeout per request.

    Returns:
        (latitude, longitude) as floats.

    Raises:
        RuntimeError: If no results are found or the service returns an error.
    """
    if not address or not address.strip():
        raise RuntimeError("Address must be a non-empty string.")

    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 0,
    }
    if country_codes:
        params["countrycodes"] = country_codes

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Geocoding request failed: {exc}") from exc

    try:
        results = response.json()
    except ValueError as exc:
        raise RuntimeError("Failed to parse geocoding response as JSON.") from exc

    if not isinstance(results, list) or len(results) == 0:
        raise RuntimeError("No geocoding results found for the provided address.")

    top = results[0]
    try:
        lat = float(top["lat"])  # type: ignore[index]
        lon = float(top["lon"])  # type: ignore[index]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Geocoding response missing latitude/longitude.") from exc

    return lat, lon


def _find_column_name_case_insensitive(df: pd.DataFrame, target_name: str) -> Optional[str]:
    target_lower = target_name.strip().lower()
    for col in df.columns:
        if isinstance(col, str) and col.strip().lower() == target_lower:
            return col
    return None


def _extract_state_from_text(address_text: str) -> Optional[str]:
    if not address_text:
        return None
    # Look for two-letter state abbreviation FL or GA bounded by word boundaries
    match = re.search(r"\b(FL|GA)\b", address_text.upper())
    if match:
        return match.group(1)
    return None


def process_excel_file(excel_file: str = "SurveySummaryAll.xlsx", worksheet: str = "truth", 
                      address_column: str = "G", country_codes: Optional[str] = None) -> None:
    """Read Excel file, geocode addresses only for FL/GA, and save results to CSV.
    
    Args:
        excel_file: Path to the Excel file.
        worksheet: Name of the worksheet to read.
        address_column: Column letter containing addresses (e.g., "G").
        country_codes: Optional country codes for geocoding bias.
    """
    try:
        # Read the Excel file
        print(f"Reading Excel file: {excel_file}")
        df = pd.read_excel(excel_file, sheet_name=worksheet)
        print(f"Loaded {len(df)} rows from worksheet '{worksheet}'")
        
        # Determine the address column name (by letter or name)
        if address_column.isalpha():
            col_index = 0
            for char in address_column.upper():
                col_index = col_index * 26 + (ord(char) - ord('A') + 1)
            col_index -= 1
            if col_index >= len(df.columns):
                raise ValueError(f"Column {address_column} is out of range. File has {len(df.columns)} columns.")
            address_col_name = df.columns[col_index]
        else:
            address_col_name = address_column
        print(f"Using address column: {address_col_name}")
        
        # Try to locate a 'state' column (case-insensitive)
        state_col_name = _find_column_name_case_insensitive(df, "state")
        if state_col_name:
            print(f"Using state column: {state_col_name}")
        else:
            print("No explicit 'state' column found; will attempt to infer from address text.")
        
        # Add latitude and longitude columns
        df['latitude'] = None
        df['longitude'] = None
        
        # Process each row
        total_rows = len(df)
        processed_rows = 0
        geocoded_rows = 0
        for index, row in df.iterrows():
            address_text = str(row[address_col_name]) if address_col_name in df.columns else ''
            if pd.isna(address_text) or address_text.strip() == '' or address_text.lower() == 'nan':
                print(f"Row {index + 1}: Skipping empty address")
                continue

            # Determine state: prefer state column, else infer from address
            state_value = None
            if state_col_name and state_col_name in df.columns:
                state_cell = row[state_col_name]
                if isinstance(state_cell, str):
                    state_value = state_cell.strip().upper()
                elif not pd.isna(state_cell):
                    state_value = str(state_cell).strip().upper()
            if not state_value:
                state_value = _extract_state_from_text(address_text)

            # Only geocode if state is FL or GA
            if state_value not in {"FL", "GA"}:
                print(f"Row {index + 1}: Skipping (state '{state_value}' not in {'FL','GA'})")
                continue

            print(f"Row {index + 1}/{total_rows}: Geocoding '{address_text}' (state={state_value})")
            try:
                lat, lon = geocode_address(address_text, country_codes=country_codes)
                df.at[index, 'latitude'] = lat
                df.at[index, 'longitude'] = lon
                geocoded_rows += 1
                print(f"  -> Lat: {lat}, Lon: {lon}")
                time.sleep(1.0)  # Be respectful of rate limits
            except RuntimeError as e:
                print(f"  -> Error: {e}")
                df.at[index, 'latitude'] = None
                df.at[index, 'longitude'] = None
            finally:
                processed_rows += 1
        
        # Save results
        output_file = "Truth.csv"
        df.to_csv(output_file, index=False)
        print(f"\nGeocoding complete! Results saved to {output_file}")
        print(f"Total rows: {total_rows}")
        print(f"Rows processed (attempted geocode): {processed_rows}")
        print(f"Rows geocoded (FL/GA): {geocoded_rows}")
        print(f"Rows skipped (non-FL/GA or errors): {total_rows - geocoded_rows}")
        
    except FileNotFoundError:
        print(f"Error: Excel file '{excel_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Geocode addresses from Excel file or single address.")
    parser.add_argument("--excel", action="store_true", help="Process Excel file SurveySummaryAll.xlsx worksheet 'truth'")
    parser.add_argument("--address", help="Single address to geocode")
    parser.add_argument("--country-codes", "-c", help="Optional comma-separated country codes to bias results (e.g., 'us' or 'us,ca')")
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional sleep seconds before request (respect rate limits if batching)")
    args = parser.parse_args(argv)

    if args.excel:
        process_excel_file(country_codes=args.country_codes)
        return 0
    
    # Single address geocoding (original functionality)
    address = args.address
    if not address:
        print("Enter address to geocode:", end=" ")
        try:
            address = input().strip()
        except KeyboardInterrupt:
            print()
            return 130

    if args.sleep > 0:
        time.sleep(args.sleep)

    try:
        lat, lon = geocode_address(address, country_codes=args.country_codes)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Latitude: {lat}, Longitude: {lon}")
    print(f"{lat},{lon}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
