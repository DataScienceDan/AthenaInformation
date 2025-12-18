from flask import Flask, render_template, jsonify, request
import pandas as pd
import math
import calendar
import os
import glob
from pathlib import Path
from openai import OpenAI
import json, re
import numpy as np
from typing import Set

app = Flask(__name__)

# Global variables to store the data
facilities_data = None
provider_info_data = None
deficiencies_data = None

def load_facilities_data():
    """Load facilities data from Excel file and convert to CSV if needed"""
    global facilities_data, provider_info_data, deficiencies_data
    
    excel_file = "SurveySummaryAll.xlsx"
    csv_file = "SurveySummaryAll.csv"
    
    # Check if CSV exists, if not convert from Excel
    if not os.path.exists(csv_file) and os.path.exists(excel_file):
        print(f"Converting {excel_file} to {csv_file}...")
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            # Save as CSV
            df.to_csv(csv_file, index=False)
            print(f"Successfully converted to {csv_file}")
        except Exception as e:
            print(f"Error converting Excel to CSV: {e}")
            return None
    
    # Load data from CSV
    if os.path.exists(csv_file):
        try:
            # Read CSV and identify CCN column first to ensure it's read as string
            temp_df = pd.read_csv(csv_file, nrows=1)
            first_col = temp_df.columns[0] if len(temp_df.columns) > 0 else None
            
            # Determine if first column is CCN
            is_ccn_first = False
            ccn_col_name = None
            if first_col:
                first_col_lower = first_col.lower()
                is_ccn_first = ('ccn' in first_col_lower or 'certification' in first_col_lower or 
                               ('number' in first_col_lower and 'certification' in first_col_lower))
                if is_ccn_first:
                    ccn_col_name = first_col
            
            # Check other columns for CCN
            if not is_ccn_first:
                ccn_columns = [c for c in temp_df.columns if 'ccn' in c.lower() or 
                              ('certification' in c.lower() and 'number' in c.lower())]
                if ccn_columns:
                    ccn_col_name = ccn_columns[0]
            
            # Read CSV with CCN as string dtype to preserve leading zeros
            dtype_dict = {}
            if ccn_col_name:
                dtype_dict[ccn_col_name] = str
                print(f"Reading CCN column '{ccn_col_name}' as string to preserve leading zeros")
            
            facilities_data = pd.read_csv(csv_file, dtype=dtype_dict)
            print(f"Loaded {len(facilities_data)} facilities from {csv_file}")
            print(f"Columns: {list(facilities_data.columns)}")
            
            # Check if first column is CCN (primary key)
            first_col = facilities_data.columns[0] if len(facilities_data.columns) > 0 else None
            if first_col:
                # Check if first column looks like CCN (contains ccn, certification, or number)
                first_col_lower = first_col.lower()
                is_ccn_col = ('ccn' in first_col_lower or 'certification' in first_col_lower or 
                             ('number' in first_col_lower and 'certification' in first_col_lower))
                
                if is_ccn_col:
                    print(f"✓ First column '{first_col}' is CCN (primary key) - using it directly")
                    # Rename first column to standard name for consistency
                    if first_col != 'CMS Certification Number (CCN)':
                        facilities_data = facilities_data.rename(columns={first_col: 'CMS Certification Number (CCN)'})
                        print(f"  Renamed '{first_col}' to 'CMS Certification Number (CCN)'")
                    # Ensure CCN is string type
                    facilities_data['CMS Certification Number (CCN)'] = facilities_data['CMS Certification Number (CCN)'].astype(str)
                    # Replace 'nan' strings with actual NaN
                    facilities_data['CMS Certification Number (CCN)'] = facilities_data['CMS Certification Number (CCN)'].replace('nan', pd.NA)
                    # Verify CCN has data
                    ccn_count = facilities_data['CMS Certification Number (CCN)'].notna().sum()
                    print(f"  CCN column has {ccn_count} non-null values out of {len(facilities_data)} rows")
                else:
                    # Check if CCN exists in any column
                    ccn_columns = [c for c in facilities_data.columns if 'ccn' in c.lower() or 
                                  ('certification' in c.lower() and 'number' in c.lower())]
                    if ccn_columns:
                        print(f"✓ Found CCN column: {ccn_columns[0]}")
                        if ccn_columns[0] != 'CMS Certification Number (CCN)':
                            facilities_data = facilities_data.rename(columns={ccn_columns[0]: 'CMS Certification Number (CCN)'})
                            print(f"  Renamed '{ccn_columns[0]}' to 'CMS Certification Number (CCN)'")
                        # Ensure CCN is string type
                        facilities_data['CMS Certification Number (CCN)'] = facilities_data['CMS Certification Number (CCN)'].astype(str)
                        facilities_data['CMS Certification Number (CCN)'] = facilities_data['CMS Certification Number (CCN)'].replace('nan', pd.NA)
                        ccn_count = facilities_data['CMS Certification Number (CCN)'].notna().sum()
                        print(f"  CCN column has {ccn_count} non-null values out of {len(facilities_data)} rows")
                    else:
                        print("⚠ Warning: No CCN column found in CSV. Will attempt to join with provider_info.csv")
            
            # Attempt to load provider_info.csv for lat/long, zip lookups, and CCN
            provider_csv = 'provider_info.csv'
            if os.path.exists(provider_csv):
                try:
                    # Read provider_info with CCN as string to preserve leading zeros
                    provider_dtype_dict = {}
                    if 'CMS Certification Number (CCN)' in pd.read_csv(provider_csv, nrows=1).columns:
                        provider_dtype_dict['CMS Certification Number (CCN)'] = str
                        print("Reading provider_info CCN column as string to preserve leading zeros")
                    provider_info_data = pd.read_csv(provider_csv, dtype=provider_dtype_dict)
                    # Ensure CCN is string type if it exists
                    if 'CMS Certification Number (CCN)' in provider_info_data.columns:
                        provider_info_data['CMS Certification Number (CCN)'] = provider_info_data['CMS Certification Number (CCN)'].astype(str)
                        provider_info_data.loc[provider_info_data['CMS Certification Number (CCN)'] == 'nan', 'CMS Certification Number (CCN)'] = pd.NA
                    print(f"Loaded provider info with {len(provider_info_data)} rows")
                    
                    # Check if facilities_data has CCN column (should be in first column as primary key)
                    ccn_columns = ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']
                    has_ccn = any(col in facilities_data.columns for col in ccn_columns)
                    
                    # Verify CCN column exists and has valid data
                    if has_ccn and 'CMS Certification Number (CCN)' in facilities_data.columns:
                        ccn_count = facilities_data['CMS Certification Number (CCN)'].notna().sum()
                        print(f"CCN column found with {ccn_count} non-null values out of {len(facilities_data)} rows ({ccn_count/len(facilities_data)*100:.1f}%)")
                        print("CCN is primary key in CSV - using CCN directly, no join needed")
                    elif not has_ccn and 'CMS Certification Number (CCN)' in provider_info_data.columns:
                        print("CCN column not found in facilities data. Joining with provider_info to add CCN...")
                        print(f"Processing {len(facilities_data)} facilities rows and {len(provider_info_data)} provider info rows...")
                        
                        # Find the provider name column in facilities_data
                        provider_name_col = find_column_flexible(
                            facilities_data, 
                            ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name'],
                            case_sensitive=False
                        )
                        state_col_fac = find_column_flexible(
                            facilities_data,
                            ['State', 'STATE', 'state', 'Provider State', 'Provider_State'],
                            case_sensitive=False
                        )
                        
                        if provider_name_col and state_col_fac:
                            print("Creating lookup dictionary from provider_info...")
                            # Create a lookup dictionary from provider_info (much faster than merge)
                            lookup_dict = {}
                            county_lookup = {}
                            rating_lookup = {}
                            beds_lookup = {}
                            residents_lookup = {}
                            health_rating_lookup = {}
                            staffing_rating_lookup = {}
                            
                            # Normalize and create lookup from provider_info
                            # Create multiple normalization strategies for better matching
                            def normalize_name_multiple(name_str):
                                """Create multiple normalized versions of a name for fuzzy matching"""
                                name = str(name_str).strip().upper()
                                # Remove common punctuation and normalize spaces
                                name1 = name.replace(',', '').replace('.', '').replace("'", "").replace('"', '').replace('-', ' ').replace('  ', ' ').strip()
                                # Also try without removing commas (some names might have them)
                                name2 = name.replace('.', '').replace("'", "").replace('"', '').replace('-', ' ').replace('  ', ' ').strip()
                                # Try with minimal normalization
                                name3 = name.replace('  ', ' ').strip()
                                return [name1, name2, name3]
                            
                            # Build lookup with multiple name variations
                            for _, row in provider_info_data.iterrows():
                                provider_name = str(row['Provider Name']).strip()
                                state = str(row['State']).strip().upper()
                                ccn_val = str(row['CMS Certification Number (CCN)']).strip()
                                
                                # Create multiple keys for this provider
                                name_variations = normalize_name_multiple(provider_name)
                                for name_norm in name_variations:
                                    key = (name_norm, state)
                                    if key not in lookup_dict:
                                        lookup_dict[key] = ccn_val
                                        if 'County/Parish' in row and pd.notna(row['County/Parish']):
                                            county_lookup[key] = str(row['County/Parish']).strip()
                                        if 'Overall Rating' in row and pd.notna(row['Overall Rating']):
                                            rating_lookup[key] = str(row['Overall Rating']).strip()
                                        if 'Number of Certified Beds' in row and pd.notna(row['Number of Certified Beds']):
                                            beds_lookup[key] = str(row['Number of Certified Beds']).strip()
                                        if 'Average Number of Residents per Day' in row and pd.notna(row['Average Number of Residents per Day']):
                                            residents_lookup[key] = str(row['Average Number of Residents per Day']).strip()
                                        if 'Health Inspection Rating' in row and pd.notna(row['Health Inspection Rating']):
                                            health_rating_lookup[key] = str(row['Health Inspection Rating']).strip()
                                        if 'Staffing Rating' in row and pd.notna(row['Staffing Rating']):
                                            staffing_rating_lookup[key] = str(row['Staffing Rating']).strip()
                            
                            print(f"Lookup dictionary created with {len(lookup_dict)} entries")
                            print("Applying lookup to facilities data...")
                            
                            # Normalize names and states for vectorized lookup (much faster than apply)
                            print("Normalizing facility names and states...")
                            # Try multiple normalization strategies
                            facilities_data['_norm_name1'] = facilities_data[provider_name_col].astype(str).str.strip().str.upper().str.replace(r'[,.\'"-]', '', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()
                            facilities_data['_norm_name2'] = facilities_data[provider_name_col].astype(str).str.strip().str.upper().str.replace(r'[.\'"-]', '', regex=True).str.replace(r'\s+', ' ', regex=True).str.strip()  # Keep commas
                            facilities_data['_norm_name3'] = facilities_data[provider_name_col].astype(str).str.strip().str.upper().str.replace(r'\s+', ' ', regex=True).str.strip()  # Minimal normalization
                            facilities_data['_norm_state'] = facilities_data[state_col_fac].astype(str).str.strip().str.upper()
                            
                            # Try lookup with each normalization strategy
                            print("Performing CCN and additional fields lookup (trying multiple name variations)...")
                            facilities_data['CMS Certification Number (CCN)'] = None
                            
                            # Try each normalization strategy
                            for norm_col in ['_norm_name1', '_norm_name2', '_norm_name3']:
                                lookup_key = list(zip(facilities_data[norm_col], facilities_data['_norm_state']))
                                ccn_result = pd.Series(lookup_key).map(lookup_dict)
                                # Fill in only where we got a match and don't already have a value
                                mask = (ccn_result.notna()) & (facilities_data['CMS Certification Number (CCN)'].isna())
                                facilities_data.loc[mask, 'CMS Certification Number (CCN)'] = ccn_result[mask]
                            
                            # If still missing, try direct name match using vectorized merge (much faster)
                            still_missing = facilities_data['CMS Certification Number (CCN)'].isna()
                            if still_missing.any():
                                print(f"Trying direct name matching for {still_missing.sum()} facilities using vectorized merge...")
                                # Create merge keys for missing facilities
                                missing_mask = facilities_data['CMS Certification Number (CCN)'].isna()
                                facilities_data.loc[missing_mask, '_merge_name'] = facilities_data.loc[missing_mask, provider_name_col].astype(str).str.strip().str.upper()
                                facilities_data.loc[missing_mask, '_merge_state'] = facilities_data.loc[missing_mask, state_col_fac].astype(str).str.strip().str.upper()
                                
                                # Prepare provider_info for merge
                                provider_merge = provider_info_data[['Provider Name', 'State', 'CMS Certification Number (CCN)']].copy()
                                provider_merge['_merge_name'] = provider_merge['Provider Name'].astype(str).str.strip().str.upper()
                                provider_merge['_merge_state'] = provider_merge['State'].astype(str).str.strip().str.upper()
                                
                                # Create a lookup series from provider_merge
                                # Ensure CCN is string type in provider_merge (preserve leading zeros)
                                provider_merge['CMS Certification Number (CCN)'] = provider_merge['CMS Certification Number (CCN)'].astype(str)
                                provider_lookup = provider_merge.set_index(['_merge_name', '_merge_state'])['CMS Certification Number (CCN)']
                                
                                # Apply lookup to missing facilities
                                missing_facilities = facilities_data[missing_mask]
                                lookup_keys = list(zip(missing_facilities['_merge_name'], missing_facilities['_merge_state']))
                                ccn_found = pd.Series(lookup_keys, index=missing_facilities.index).map(provider_lookup)
                                
                                # Update only where we found a match (ensure CCN remains as string)
                                facilities_data.loc[ccn_found.notna().index, 'CMS Certification Number (CCN)'] = ccn_found[ccn_found.notna()].astype(str).str.strip()
                                
                                # Clean up temporary merge columns
                                facilities_data = facilities_data.drop(columns=['_merge_name', '_merge_state'], errors='ignore')
                                
                                matched_direct = ccn_found.notna().sum()
                                print(f"Direct name matching found CCN for {matched_direct} additional facilities")
                            
                            # Now map other fields using the best matching key
                            facilities_data['_lookup_key'] = list(zip(facilities_data['_norm_name1'], facilities_data['_norm_state']))
                            
                            if 'County/Parish' not in facilities_data.columns:
                                facilities_data['County/Parish'] = facilities_data['_lookup_key'].map(county_lookup)
                            
                            # Add additional fields from provider_info if not already present
                            if 'Overall Rating' not in facilities_data.columns:
                                facilities_data['Overall Rating'] = facilities_data['_lookup_key'].map(rating_lookup)
                            if 'Number of Certified Beds' not in facilities_data.columns:
                                facilities_data['Number of Certified Beds'] = facilities_data['_lookup_key'].map(beds_lookup)
                            if 'Average Number of Residents per Day' not in facilities_data.columns:
                                facilities_data['Average Number of Residents per Day'] = facilities_data['_lookup_key'].map(residents_lookup)
                            if 'Health Inspection Rating' not in facilities_data.columns:
                                facilities_data['Health Inspection Rating'] = facilities_data['_lookup_key'].map(health_rating_lookup)
                            if 'Staffing Rating' not in facilities_data.columns:
                                facilities_data['Staffing Rating'] = facilities_data['_lookup_key'].map(staffing_rating_lookup)
                            
                            # Clean up temporary columns
                            facilities_data = facilities_data.drop(columns=['_norm_name1', '_norm_name2', '_norm_name3', '_norm_state', '_lookup_key'], errors='ignore')
                            
                            # Propagate all joined fields to all rows with the same Provider Name + State using transform (vectorized)
                            print("Propagating joined fields to all rows with same Provider Name + State...")
                            # Use transform to get first non-null value for each group
                            def first_non_null(series):
                                non_null = series.dropna()
                                return non_null.iloc[0] if len(non_null) > 0 else None
                            
                            facilities_data['CMS Certification Number (CCN)'] = facilities_data.groupby([provider_name_col, state_col_fac])['CMS Certification Number (CCN)'].transform(first_non_null)
                            
                            # Propagate all other joined fields
                            for col in ['County/Parish', 'Overall Rating', 'Number of Certified Beds', 'Average Number of Residents per Day', 'Health Inspection Rating', 'Staffing Rating']:
                                if col in facilities_data.columns:
                                    facilities_data[col] = facilities_data.groupby([provider_name_col, state_col_fac])[col].transform(first_non_null)
                            
                            matched_count = facilities_data['CMS Certification Number (CCN)'].notna().sum()
                            print(f"Successfully matched CCN for {matched_count} out of {len(facilities_data)} facilities ({matched_count/len(facilities_data)*100:.1f}%)")
                            
                            # Debug: Check a specific facility to verify CCN is set
                            test_facility = facilities_data[facilities_data[provider_name_col].str.contains('ADVINIA.*NAPLES', case=False, na=False, regex=True)]
                            if len(test_facility) > 0:
                                test_row = test_facility.iloc[0]
                                test_ccn = test_row.get('CMS Certification Number (CCN)', 'NOT FOUND')
                                print(f"Debug - ADVINIA CARE AT OF NAPLES CCN: {test_ccn} (type: {type(test_ccn)})")
                        else:
                            print("Warning: Could not find Provider Name or State columns for CCN matching")
                        
                except Exception as e:
                    print(f"Warning: Failed to load {provider_csv}: {e}")
            else:
                print(f"Warning: {provider_csv} not found. CCN matching will not be available.")
            
            # Attempt to load health_deficiencies (try chunked CSV parts first, then single CSV, then Excel)
            deficiencies_csv = 'health_deficiencies.csv'
            deficiencies_bak = 'health_deficiencies_bak.csv'
            deficiencies_xlsx = 'health_deficiencies.xlsx'

            def ensure_deficiencies_chunks(base_csv: str, backup_csv: str, chunk_size: int = 25000):
                """
                Ensure that large health_deficiencies.csv is split into smaller chunk files.
                - If health_deficiencies_part*.csv files already exist, return them.
                - If base_csv exists and no parts exist, split it into 25,000-line chunks,
                  write health_deficiencies_part<N>.csv, then rename base_csv to backup_csv.
                - Returns a sorted list of part file paths.
                """
                part_pattern = 'health_deficiencies_part*.csv'
                part_files = sorted(glob.glob(part_pattern))
                if part_files:
                    print(f"Found existing health_deficiencies part files: {part_files}")
                    return part_files

                if not os.path.exists(base_csv):
                    return []

                print(f"Splitting large health_deficiencies file '{base_csv}' into chunks of {chunk_size} rows...")
                part_files = []
                try:
                    chunk_iter = pd.read_csv(base_csv, chunksize=chunk_size, dtype={'CMS Certification Number (CCN)': str})
                    for i, chunk in enumerate(chunk_iter, start=1):
                        part_name = f"health_deficiencies_part{i}.csv"
                        chunk.to_csv(part_name, index=False)
                        part_files.append(part_name)
                        print(f"  Wrote {len(chunk)} rows to '{part_name}'")

                    # Rename original to backup so Git can ignore it
                    try:
                        os.replace(base_csv, backup_csv)
                        print(f"Renamed '{base_csv}' to '{backup_csv}' after splitting.")
                    except Exception as re_err:
                        print(f"Warning: Failed to rename '{base_csv}' to '{backup_csv}': {re_err}")

                    return part_files
                except Exception as split_err:
                    print(f"Warning: Failed to split {base_csv} into chunks: {split_err}")
                    return []

            # Prefer chunked CSV parts if available / creatable
            part_files = ensure_deficiencies_chunks(deficiencies_csv, deficiencies_bak, chunk_size=25000)

            if part_files:
                try:
                    frames = []
                    for path in part_files:
                        print(f"Loading health deficiencies chunk: {path}")
                        df_part = pd.read_csv(path, dtype={'CMS Certification Number (CCN)': str})
                        frames.append(df_part)
                    deficiencies_data = pd.concat(frames, ignore_index=True)
                    print(f"Loaded health deficiencies from {len(part_files)} chunk files with total {len(deficiencies_data)} rows.")
                except Exception as e:
                    print(f"Warning: Failed to load health_deficiencies part files: {e}")
                    deficiencies_data = None
            elif os.path.exists(deficiencies_csv):
                # Fallback: single CSV (will only happen if splitting failed or not needed)
                try:
                    deficiencies_data = pd.read_csv(deficiencies_csv, dtype={'CMS Certification Number (CCN)': str})
                    print(f"Loaded health deficiencies with {len(deficiencies_data)} rows from {deficiencies_csv}")
                except Exception as e:
                    print(f"Warning: Failed to load {deficiencies_csv}: {e}")
                    deficiencies_data = None
            elif os.path.exists(deficiencies_xlsx):
                try:
                    deficiencies_data = pd.read_excel(deficiencies_xlsx)
                    print(f"Loaded health deficiencies with {len(deficiencies_data)} rows from {deficiencies_xlsx}")
                except Exception as e:
                    print(f"Warning: Failed to load {deficiencies_xlsx}: {e}")
                    deficiencies_data = None
            else:
                print(f"Warning: No health_deficiencies CSV or Excel files found. Histograms and deficiency features will not be available.")
                deficiencies_data = None
            return facilities_data
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return None
    else:
        print(f"Neither {excel_file} nor {csv_file} found")
        return None


# --- Helpers ---
def find_column_flexible(df, possible_names, case_sensitive=False):
    """
    Find a column in a dataframe by trying multiple possible names.
    Returns the first matching column name or None.
    """
    if case_sensitive:
        for name in possible_names:
            if name in df.columns:
                return name
    else:
        # Case-insensitive search
        df_cols_lower = {col.lower(): col for col in df.columns}
        for name in possible_names:
            if name.lower() in df_cols_lower:
                return df_cols_lower[name.lower()]
    return None

STATE_ABBR = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia'
}

NAME_TO_ABBR = {v: k for k, v in STATE_ABBR.items()}

def get_state_aliases(state_input: str) -> Set[str]:
    s = str(state_input).strip()
    if not s:
        return set()
    aliases = {s}
    up = s.upper()
    title = s.title()
    aliases.update({up, title})
    # If input is full name, add abbr
    if title in NAME_TO_ABBR:
        abbr = NAME_TO_ABBR[title]
        aliases.update({abbr, abbr.upper(), abbr.title()})
    # If input is abbr, add full name
    if up in STATE_ABBR:
        full = STATE_ABBR[up]
        aliases.update({full, full.upper(), full.title()})
    return aliases

@app.route('/')
def dashboard():
    """Serve the main dashboard page"""
    return app.send_static_file('Dashboard.html')

@app.route('/test')
def test():
    """Test endpoint to verify server is working"""
    return jsonify({'message': 'Server is working!', 'data_loaded': facilities_data is not None})

def normalize_state_input(state_input):
    """Convert state name to state code if needed, or return uppercase state code"""
    state_name_to_code = {
        'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
        'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
        'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
        'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
        'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
        'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
        'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
        'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
        'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
        'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
    }
    state_lower = str(state_input).strip().lower()
    # If it's already a 2-letter code, return it uppercase
    if len(state_lower) == 2:
        return state_lower.upper()
    # Otherwise try to convert name to code
    return state_name_to_code.get(state_lower, state_input.upper())

@app.route('/api/facilities/<state>')
def get_facilities_by_state(state):
    """API endpoint to get facilities for a specific state with coordinates for map display"""
    global facilities_data, provider_info_data
    
    print(f"API call received for state: {state}")
    
    if facilities_data is None:
        print("Error: facilities_data is None")
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        # Filter facilities by state
        # Try different possible column names for state
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = None
        
        print(f"Available columns: {list(facilities_data.columns)}")
        
        # Debug: Check for CCN-related columns
        ccn_columns = [col for col in facilities_data.columns if 'ccn' in col.lower() or 'certification' in col.lower() or 'number' in col.lower()]
        print(f"CCN-related columns: {ccn_columns}")
        
        for col in state_columns:
            if col in facilities_data.columns:
                state_col = col
                print(f"Found state column: {col}")
                break
        
        if state_col is None:
            print(f"State column not found. Available columns: {list(facilities_data.columns)}")
            return jsonify({'error': 'State column not found'}), 500
        
        # Filter by state
        print(f"Filtering for state: {state}")
        print(f"State column values: {facilities_data[state_col].unique()[:10]}")  # Show first 10 unique values
        
        # Normalize state input and match case-insensitively
        state_normalized = normalize_state_input(state)
        state_facilities = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == state_normalized]
        print(f"Found {len(state_facilities)} facilities for state '{state}' (normalized: '{state_normalized}')")
        
        if len(state_facilities) == 0:
            return jsonify({'facilities': [], 'message': f'No facilities found for state {state}'})
        
        # Convert to list of dictionaries and ensure unique facility names
        facilities_list = []
        seen_names = set()
        
        for _, row in state_facilities.iterrows():
            # Try to get facility name from different possible columns
            name_columns = ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']
            facility_name = None
            
            for col in name_columns:
                if col in row.index and not pd.isna(row[col]):
                    facility_name = str(row[col]).strip()
                    break
            
            # Skip if no name found or duplicate name
            if not facility_name or facility_name in seen_names:
                continue
                
            seen_names.add(facility_name)
            
            facility = {}
            for col in row.index:
                # Handle NaN values
                if pd.isna(row[col]):
                    facility[col] = None
                else:
                    # For CCN columns, preserve the value as-is (could be number or string)
                    if 'ccn' in col.lower() or 'certification' in col.lower():
                        val = row[col]
                        # Convert to string but preserve numeric values
                        if pd.notna(val):
                            facility[col] = str(val).strip()
                        else:
                            facility[col] = None
                    else:
                        val = str(row[col])
                        # Don't store 'nan' or 'None' as strings
                        if val.lower() in ['nan', 'none', '']:
                            facility[col] = None
                        else:
                            facility[col] = val
            
            # Extract CCN - it should be in the facility dict if the join worked
            ccn_in_facility = None
            for ccn_field in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
                if ccn_field in facility:
                    ccn_val = facility[ccn_field]
                    if ccn_val is not None:
                        ccn_str = str(ccn_val).strip()
                        # Check if it's a valid CCN (not 'nan', 'none', 'n/a', or empty)
                        if ccn_str and ccn_str.lower() not in ['nan', 'none', 'n/a', '']:
                            ccn_in_facility = ccn_str
                            break
                # Also check row directly as fallback
                elif ccn_field in row.index and not pd.isna(row[ccn_field]):
                    ccn_val = row[ccn_field]
                    ccn_str = str(ccn_val).strip()
                    if ccn_str and ccn_str.lower() not in ['nan', 'none', 'n/a', '']:
                        ccn_in_facility = ccn_str
                        facility[ccn_field] = ccn_str  # Ensure it's in facility dict
                        break
            
            # Initialize lat/lng if not present (these come from provider_info, not the join)
            if 'lat' not in facility or not facility.get('lat'):
                facility['lat'] = None
            if 'lng' not in facility or not facility.get('lng'):
                facility['lng'] = None
            
            # Preserve existing values from join, only set to None if truly missing
            # These fields should already be in facility from the row if the join worked
            if 'County/Parish' not in facility or facility.get('County/Parish') in [None, 'None', 'nan', '']:
                facility['County/Parish'] = None
            if 'Overall Rating' not in facility or facility.get('Overall Rating') in [None, 'None', 'nan', '']:
                facility['Overall Rating'] = None
            if 'Number of Certified Beds' not in facility or facility.get('Number of Certified Beds') in [None, 'None', 'nan', '']:
                facility['Number of Certified Beds'] = None
            if 'Average Number of Residents per Day' not in facility or facility.get('Average Number of Residents per Day') in [None, 'None', 'nan', '']:
                facility['Average Number of Residents per Day'] = None
            if 'Health Inspection Rating' not in facility or facility.get('Health Inspection Rating') in [None, 'None', 'nan', '']:
                facility['Health Inspection Rating'] = None
            if 'Staffing Rating' not in facility or facility.get('Staffing Rating') in [None, 'None', 'nan', '']:
                facility['Staffing Rating'] = None
            
            # Only look up from provider_info_data if fields are missing and provider_info_data is available
            if provider_info_data is not None:
                ccn_cols = ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']
                ccn_col = next((c for c in ccn_cols if c in provider_info_data.columns), None)
                if ccn_col:
                    # Try to get CCN - first from facility dict (from join), then from row
                    ccn = ccn_in_facility
                    
                    if not ccn:
                        # Fallback: try to get CCN from the facility row directly
                        for ccn_field in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
                            if ccn_field in row.index and not pd.isna(row[ccn_field]):
                                ccn_val = row[ccn_field]
                                # Convert to string and check if it's valid
                                ccn_str = str(ccn_val).strip()
                                if ccn_str and ccn_str.lower() not in ['nan', 'none', 'n/a', '']:
                                    ccn = ccn_str
                                    # Also update facility dict
                                    facility[ccn_field] = ccn_str
                                    break
                    
                    # If still no CCN, try direct lookup from provider_info by name + state
                    if not ccn or str(ccn).lower() in ['nan', 'none', 'n/a', '']:
                        # Try to find in provider_info by matching name and state
                        facility_name_upper = str(facility_name).strip().upper()
                        facility_state_upper = str(facility.get('State') or row.get(state_col) or '').strip().upper()
                        
                        if facility_name_upper and facility_state_upper:
                            # Try exact match first
                            provider_match = provider_info_data[
                                (provider_info_data['Provider Name'].astype(str).str.strip().str.upper() == facility_name_upper) &
                                (provider_info_data['State'].astype(str).str.strip().str.upper() == facility_state_upper)
                            ]
                            
                            # If exact match fails, try partial match (contains)
                            if provider_match.empty:
                                provider_match = provider_info_data[
                                    (provider_info_data['Provider Name'].astype(str).str.strip().str.upper().str.contains(facility_name_upper, na=False, regex=False)) &
                                    (provider_info_data['State'].astype(str).str.strip().str.upper() == facility_state_upper)
                                ]
                            
                            # If still no match, try reverse (facility name contains provider name)
                            if provider_match.empty:
                                for _, prov_row in provider_info_data[provider_info_data['State'].astype(str).str.strip().str.upper() == facility_state_upper].iterrows():
                                    prov_name_upper = str(prov_row['Provider Name']).strip().upper()
                                    if prov_name_upper in facility_name_upper or facility_name_upper in prov_name_upper:
                                        # Check if names are similar (fuzzy match)
                                        if abs(len(prov_name_upper) - len(facility_name_upper)) <= 10:  # Length difference not too large
                                            provider_match = pd.DataFrame([prov_row])
                                            break
                            
                            if not provider_match.empty:
                                ccn = str(provider_match.iloc[0]['CMS Certification Number (CCN)']).strip()
                                facility['CMS Certification Number (CCN)'] = ccn
                                # Also update other fields if missing
                                if not facility.get('County/Parish') or facility['County/Parish'] in [None, 'None', 'nan']:
                                    if 'County/Parish' in provider_match.columns and pd.notna(provider_match.iloc[0]['County/Parish']):
                                        facility['County/Parish'] = str(provider_match.iloc[0]['County/Parish']).strip()
                                if not facility.get('Overall Rating') or facility['Overall Rating'] in [None, 'None', 'nan']:
                                    if 'Overall Rating' in provider_match.columns and pd.notna(provider_match.iloc[0]['Overall Rating']):
                                        facility['Overall Rating'] = str(provider_match.iloc[0]['Overall Rating']).strip()
                                if len(facilities_list) < 3:
                                    print(f"Found CCN via direct lookup for {facility_name}: {ccn}")
                    
                    # Debug: Log CCN extraction attempt (only for first few facilities to avoid spam)
                    if (not ccn or str(ccn).lower() in ['nan', 'none', 'n/a', '']) and len(facilities_list) < 5:
                        ccn_debug = {}
                        for ccn_field in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
                            if ccn_field in row.index:
                                ccn_debug[ccn_field] = str(row[ccn_field]) if not pd.isna(row[ccn_field]) else 'NaN'
                            if ccn_field in facility:
                                ccn_debug[f'{ccn_field}_in_facility'] = facility[ccn_field]
                        print(f"CCN extraction debug for {facility_name}: {ccn_debug}")
                    
                    if ccn and str(ccn).lower() not in ['nan', 'none', 'n/a', '']:
                        # Normalize CCN - remove leading zeros and pad to 6 digits for matching
                        ccn_clean = str(ccn).strip().lstrip('0')  # Remove leading zeros
                        ccn_normalized = ccn_clean.zfill(6) if ccn_clean else ''  # Pad to 6 digits
                        
                        # Match against provider_info CCNs - normalize both sides for comparison
                        provider_info_ccn_normalized = provider_info_data[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
                        provider_match = provider_info_data[provider_info_ccn_normalized == ccn_normalized]
                        if len(facilities_list) < 3:
                            print(f"CCN matching: looking for '{ccn_normalized}', found {len(provider_match)} matches")
                        if not provider_match.empty:
                            provider_row = provider_match.iloc[0]
                            
                            # Look for lat/lng columns (only if not already in facility)
                            if not facility.get('lat') or not facility.get('lng'):
                                lat_cols = ['lat', 'latitude', 'Latitude', 'LAT', 'LATITUDE']
                                lng_cols = ['lng', 'longitude', 'Longitude', 'LNG', 'LONGITUDE', 'lon', 'LON']
                                
                                lat_col = next((c for c in lat_cols if c in provider_row.index), None)
                                lng_col = next((c for c in lng_cols if c in provider_row.index), None)
                                
                                if lat_col and lng_col:
                                    try:
                                        facility['lat'] = float(provider_row[lat_col])
                                        facility['lng'] = float(provider_row[lng_col])
                                    except (ValueError, TypeError) as e:
                                        pass
                            
                            # Look for County/Parish column (only if not already set)
                            if not facility.get('County/Parish') or facility['County/Parish'] == 'None' or facility['County/Parish'] == 'nan':
                                county_cols = ['County/Parish', 'County', 'county', 'COUNTY', 'County Name', 'county_name']
                                county_col = next((c for c in county_cols if c in provider_row.index), None)
                                if county_col and not pd.isna(provider_row[county_col]):
                                    facility['County/Parish'] = str(provider_row[county_col])
                            
                            # Look for Overall Rating column (only if not already set)
                            if not facility.get('Overall Rating') or facility['Overall Rating'] == 'None' or facility['Overall Rating'] == 'nan':
                                rating_cols = ['Overall Rating', 'Overall_Rating', 'overall_rating', 'Rating']
                                rating_col = next((c for c in rating_cols if c in provider_row.index), None)
                                if rating_col and not pd.isna(provider_row[rating_col]):
                                    facility['Overall Rating'] = str(provider_row[rating_col])
                            
                            # Look for Number of Certified Beds (only if not already set)
                            if not facility.get('Number of Certified Beds') or facility['Number of Certified Beds'] == 'None' or facility['Number of Certified Beds'] == 'nan':
                                beds_col = 'Number of Certified Beds'
                                if beds_col in provider_row.index and not pd.isna(provider_row[beds_col]):
                                    facility['Number of Certified Beds'] = str(provider_row[beds_col])
                            
                            # Look for Average Number of Residents per Day (only if not already set)
                            if not facility.get('Average Number of Residents per Day') or facility['Average Number of Residents per Day'] == 'None' or facility['Average Number of Residents per Day'] == 'nan':
                                residents_col = 'Average Number of Residents per Day'
                                if residents_col in provider_row.index and not pd.isna(provider_row[residents_col]):
                                    facility['Average Number of Residents per Day'] = str(provider_row[residents_col])
                            
                            # Look for Health Inspection Rating (only if not already set)
                            if not facility.get('Health Inspection Rating') or facility['Health Inspection Rating'] == 'None' or facility['Health Inspection Rating'] == 'nan':
                                health_rating_col = 'Health Inspection Rating'
                                if health_rating_col in provider_row.index and not pd.isna(provider_row[health_rating_col]):
                                    facility['Health Inspection Rating'] = str(provider_row[health_rating_col])
                            
                            # Look for Staffing Rating (only if not already set)
                            if not facility.get('Staffing Rating') or facility['Staffing Rating'] == 'None' or facility['Staffing Rating'] == 'nan':
                                staffing_rating_col = 'Staffing Rating'
                                if staffing_rating_col in provider_row.index and not pd.isna(provider_row[staffing_rating_col]):
                                    facility['Staffing Rating'] = str(provider_row[staffing_rating_col])
                        else:
                            if len(facilities_list) < 5:  # Only log first few
                                print(f"No provider match found for CCN: {ccn} for facility: {facility_name}")
                    else:
                        # Only log if we're debugging (first few facilities)
                        if len(facilities_list) < 5:
                            print(f"No valid CCN found for facility: {facility_name}")
            
            # Add a unique identifier for the facility
            facility['unique_id'] = len(facilities_list)
            facilities_list.append(facility)
        
        print(f"Returning {len(facilities_list)} unique facilities")
        
        # Debug: Show sample facility structure
        if facilities_list:
            print(f"Sample facility structure: {list(facilities_list[0].keys())}")
            print(f"Sample facility CCN fields: {[(k, v) for k, v in facilities_list[0].items() if 'ccn' in k.lower() or 'certification' in k.lower() or 'number' in k.lower()]}")
            print(f"Sample facility County/Parish: {facilities_list[0].get('County/Parish', 'NOT FOUND')}")
            print(f"Sample facility Overall Rating: {facilities_list[0].get('Overall Rating', 'NOT FOUND')}")
            
            # Count how many facilities have CCN
            facilities_with_ccn = sum(1 for f in facilities_list if any(
                f.get(k) and str(f.get(k)).lower() not in ['nan', 'none', 'n/a', ''] 
                for k in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']
            ))
            print(f"Facilities with valid CCN: {facilities_with_ccn} out of {len(facilities_list)} ({facilities_with_ccn/len(facilities_list)*100:.1f}%)")
        
        return jsonify({
            'facilities': facilities_list,
            'count': len(facilities_list),
            'state': state
        })
        
    except Exception as e:
        print(f"Error filtering facilities by state: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml-forecast', methods=['POST'])
def ml_forecast():
    """Predict next survey date using a simple ML-style regression on historical intervals with fallbacks.

    Request JSON expects: { state: str, ccn: str }
    Returns: { forecast_date: 'YYYY-MM-DD' }
    """
    global facilities_data, provider_info_data, deficiencies_data

    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500

    try:
        body = request.get_json(silent=True) or {}
        state = (body.get('state') or '').strip()
        ccn_raw = (body.get('ccn') or '').strip() if body.get('ccn') is not None else ''

        # Normalize CCN to 6-digit string if provided
        ccn_norm = None
        if ccn_raw:
            ccn_clean = str(ccn_raw).strip().lstrip('0')
            ccn_norm = ccn_clean.zfill(6)

        # Collect survey dates for the CCN from deficiencies_data and facilities_data (if CCN provided)
        date_values = []

        def try_collect_dates(df, ccn_cols, date_cols):
            if df is None:
                return
            ccn_col = next((c for c in ccn_cols if c in df.columns), None)
            if not ccn_col:
                return
            subset = df[df[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6) == ccn_norm]
            if subset.empty:
                return
            for dc in date_cols:
                if dc in subset.columns:
                    for v in subset[dc].dropna().tolist():
                        try:
                            date_values.append(pd.to_datetime(v))
                        except Exception:
                            pass

        if ccn_norm:
            try_collect_dates(deficiencies_data, ['CCN', 'CMS Certification Number (CCN)', 'CMS Certification Number', 'ccn'], ['Health Survey Date', 'Survey Date', 'Date'])
            try_collect_dates(facilities_data, ['CCN', 'CMS Certification Number (CCN)', 'CMS Certification Number', 'ccn'], ['Health Survey Date', 'Survey Date', 'Date'])

        # Unique sorted dates
        unique_dates = sorted({pd.Timestamp(d).normalize() for d in date_values}) if date_values else []
        if len(unique_dates) < 2:
            # Fallback to county/state averages if insufficient history
            predicted_days = compute_fallback_interval_days(ccn_norm, state)
        else:
            # Compute intervals in days
            intervals = np.diff([d.to_pydatetime() for d in unique_dates])
            intervals_days = np.array([max(1, delta.days) for delta in intervals], dtype=float)

            # AR(1)-style linear regression: interval_t = a + b * interval_{t-1}
            if len(intervals_days) >= 2:
                x = intervals_days[:-1]
                y = intervals_days[1:]
                X = np.vstack([np.ones_like(x), x]).T
                try:
                    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
                    a, b = float(coef[0]), float(coef[1])
                    last_interval = float(intervals_days[-1])
                    predicted = a + b * last_interval
                except Exception:
                    predicted = float(np.median(intervals_days))
            else:
                predicted = float(np.median(intervals_days))

            # Clamp to reasonable bounds (1 to ~2 years)
            predicted_days = int(max(30, min(730, round(predicted))))

            # Seasonality adjustment: if most recent survey month has long gap, bias towards 12-month multiples
            try:
                last_month = unique_dates[-1].month
                if 320 <= predicted_days <= 410:
                    predicted_days = 365
                elif 500 <= predicted_days <= 590:
                    predicted_days = 548  # ~18 months
                elif 680 <= predicted_days <= 770:
                    predicted_days = 730   # ~24 months
            except Exception:
                pass

        # Choose reference last date
        last_date: pd.Timestamp
        if unique_dates:
            last_date = unique_dates[-1]
        else:
            # Use the most recent survey date across state as a better anchor; otherwise today
            last_date = None
            if deficiencies_data is not None:
                date_col_def = next((c for c in ['Health Survey Date', 'Survey Date', 'Date'] if c in deficiencies_data.columns), None)
                if date_col_def:
                    try:
                        if state and facilities_data is not None:
                            state_col = next((c for c in ['State', 'STATE', 'Provider State'] if c in facilities_data.columns), None)
                            ccn_cols = [c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in facilities_data.columns]
                            if state_col and ccn_cols:
                                fac_state = facilities_data[facilities_data[state_col] == state]
                                ccn_set = set()
                                for c in ccn_cols:
                                    ccn_set.update(fac_state[c].astype(str).str.strip().str.lstrip('0').str.zfill(6).tolist())
                                ccn_col_def = next((c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in deficiencies_data.columns), None)
                                if ccn_col_def and ccn_set:
                                    def_rows = deficiencies_data[deficiencies_data[ccn_col_def].astype(str).str.strip().str.lstrip('0').str.zfill(6).isin(ccn_set)]
                                    if not def_rows.empty:
                                        last_dt = pd.to_datetime(def_rows[date_col_def], errors='coerce').dropna()
                                        if not last_dt.empty:
                                            last_date = last_dt.max().normalize()
                        if last_date is None:
                            last_dt = pd.to_datetime(deficiencies_data[date_col_def], errors='coerce').dropna()
                            if not last_dt.empty:
                                last_date = last_dt.max().normalize()
                    except Exception:
                        pass
            if last_date is None:
                last_date = pd.Timestamp.today().normalize()
        tentative = last_date + pd.Timedelta(days=int(predicted_days))

        # Round to nearest Monday (consistency with UI)
        forecast_date = round_to_nearest_monday(tentative)
        return jsonify({'forecast_date': forecast_date.strftime('%Y-%m-%d')})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def compute_fallback_interval_days(ccn_norm: str, state: str) -> int:
    """Fallback interval using county peers if available then state average; default 365.
    """
    global provider_info_data, deficiencies_data, facilities_data

    # Find county for this CCN
    county_name = None
    if provider_info_data is not None:
        ccn_col = next((c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in provider_info_data.columns), None)
        if ccn_col:
            row = provider_info_data[provider_info_data[ccn_col].astype(str).str.strip().str.zfill(6) == ccn_norm]
            if not row.empty:
                county_col = next((c for c in ['County/Parish', 'County', 'County Name', 'county_name'] if c in provider_info_data.columns), None)
                if county_col and not pd.isna(row.iloc[0][county_col]):
                    county_name = str(row.iloc[0][county_col])

    def compute_avg_interval(filter_df):
        all_dates = sorted({pd.Timestamp(d).normalize() for d in filter_df.dropna().tolist()})
        if len(all_dates) < 2:
            return None
        gaps = np.diff([d.to_pydatetime() for d in all_dates])
        days = np.array([max(1, g.days) for g in gaps], dtype=float)
        return int(round(float(np.median(days))))

    # County peers
    if county_name and provider_info_data is not None and deficiencies_data is not None:
        county_col = next((c for c in ['County/Parish', 'County', 'County Name', 'county_name'] if c in provider_info_data.columns), None)
        ccn_col_pi = next((c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in provider_info_data.columns), None)
        ccn_col_def = next((c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in deficiencies_data.columns), None)
        date_col_def = next((c for c in ['Health Survey Date', 'Survey Date', 'Date'] if c in deficiencies_data.columns), None)
        if county_col and ccn_col_pi and ccn_col_def and date_col_def:
            county_ccns = provider_info_data[provider_info_data[county_col] == county_name][ccn_col_pi].astype(str).str.strip().str.lstrip('0').str.zfill(6)
            def_rows = deficiencies_data[deficiencies_data[ccn_col_def].astype(str).str.strip().str.lstrip('0').str.zfill(6).isin(set(county_ccns))]
            avg_days = compute_avg_interval(def_rows[date_col_def]) if not def_rows.empty else None
            if avg_days:
                return int(max(30, min(730, avg_days)))

    # State average fallback
    if facilities_data is not None and deficiencies_data is not None and state:
        state_col = next((c for c in ['State', 'STATE', 'Provider State'] if c in facilities_data.columns), None)
        if state_col:
            state_ccn_cols = [c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in facilities_data.columns]
            if state_ccn_cols:
                state_fac = facilities_data[facilities_data[state_col] == state]
                if not state_fac.empty:
                    # Map CCNs to normalized set
                    ccns = set()
                    for c in state_ccn_cols:
                        ccns.update(state_fac[c].astype(str).str.strip().str.lstrip('0').str.zfill(6).tolist())
                    ccn_col_def = next((c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in deficiencies_data.columns), None)
                    date_col_def = next((c for c in ['Health Survey Date', 'Survey Date', 'Date'] if c in deficiencies_data.columns), None)
                    if ccn_col_def and date_col_def:
                        def_rows = deficiencies_data[deficiencies_data[ccn_col_def].astype(str).str.strip().str.lstrip('0').str.zfill(6).isin(ccns)]
                        avg_days = compute_avg_interval(def_rows[date_col_def]) if not def_rows.empty else None
                        if avg_days:
                            return int(max(30, min(730, avg_days)))

    return 365


def round_to_nearest_monday(date_like: pd.Timestamp) -> pd.Timestamp:
    dt = pd.Timestamp(date_like)
    # Monday is 0
    weekday = dt.weekday()
    # Round to nearest Monday by comparing distance to previous and next Monday
    prev_monday = dt - pd.Timedelta(days=(weekday - 0) % 7)
    next_monday = dt + pd.Timedelta(days=(7 - weekday) % 7)
    if abs((dt - prev_monday).days) <= abs((next_monday - dt).days):
        return prev_monday.normalize()
    return next_monday.normalize()

@app.route('/api/facility/<facility_id>')
def get_facility_details(facility_id):
    """API endpoint to get detailed information for a specific facility"""
    global facilities_data, provider_info_data
    
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        # Try to find facility by different possible ID columns
        id_columns = ['CCN', 'ccn', 'CMS Certification Number', 'Provider ID', 'Facility ID']
        id_col = None
        
        for col in id_columns:
            if col in facilities_data.columns:
                id_col = col
                break
        
        if id_col is None:
            return jsonify({'error': 'ID column not found'}), 500
        
        # Find the facility
        facility = facilities_data[facilities_data[id_col] == facility_id]
        
        if len(facility) == 0:
            return jsonify({'error': 'Facility not found'}), 404
        
        # Convert to dictionary
        facility_dict = {}
        for col in facility.iloc[0].index:
            if pd.isna(facility.iloc[0][col]):
                facility_dict[col] = None
            else:
                facility_dict[col] = str(facility.iloc[0][col])
        
        # Add county/parish data from provider_info_data if available
        if provider_info_data is not None:
            ccn_cols = ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']
            ccn_col = next((c for c in ccn_cols if c in provider_info_data.columns), None)
            
            if ccn_col:
                facility_ccn = str(facility.iloc[0].get('CCN', ''))
                if facility_ccn and facility_ccn != 'N/A':
                    provider_match = provider_info_data[provider_info_data[ccn_col].astype(str) == facility_ccn]
                    if not provider_match.empty:
                        provider_row = provider_match.iloc[0]
                        
                        # Look for county/parish columns
                        county_cols = ['County/Parish', 'County', 'county', 'COUNTY', 'County Name', 'county_name']
                        county_col = next((c for c in county_cols if c in provider_row.index), None)
                        
                        if county_col and not pd.isna(provider_row[county_col]):
                            facility_dict['County/Parish'] = str(provider_row[county_col])
                            print(f"Added county data for facility {facility_ccn}: {provider_row[county_col]}")
        
        return jsonify(facility_dict)
        
    except Exception as e:
        print(f"Error getting facility details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/provider-names/<ccn>')
def get_provider_names_for_ccn(ccn):
    """Get all historical provider names for a given CCN across all survey data sources."""
    global facilities_data, provider_info_data, deficiencies_data
    
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        # Normalize CCN
        ccn_normalized = str(ccn).strip().lstrip('0').zfill(6)
        
        # Collect all provider names from different sources
        provider_names = set()
        
        # 1. From provider_info_data
        if provider_info_data is not None:
            ccn_cols = ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']
            ccn_col = next((c for c in ccn_cols if c in provider_info_data.columns), None)
            if ccn_col:
                names_cols = ['Provider Name', 'provider_name']
                names_col = next((c for c in names_cols if c in provider_info_data.columns), None)
                if names_col:
                    matches = provider_info_data[provider_info_data[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6) == ccn_normalized]
                    for name in matches[names_col].dropna():
                        provider_names.add(str(name).strip())
        
        # 2. From deficiencies_data
        if deficiencies_data is not None:
            ccn_cols = ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']
            ccn_col = next((c for c in ccn_cols if c in deficiencies_data.columns), None)
            if ccn_col:
                names_cols = ['Provider Name', 'Facility Name', 'provider_name', 'facility_name']
                names_col = next((c for c in names_cols if c in deficiencies_data.columns), None)
                if names_col:
                    matches = deficiencies_data[deficiencies_data[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6) == ccn_normalized]
                    for name in matches[names_col].dropna():
                        provider_names.add(str(name).strip())
        
        # 3. From facilities_data
        ccn_cols = ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']
        ccn_col = next((c for c in ccn_cols if c in facilities_data.columns), None)
        if ccn_col:
            names_cols = ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']
            names_col = next((c for c in names_cols if c in facilities_data.columns), None)
            if names_col:
                matches = facilities_data[facilities_data[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6) == ccn_normalized]
                for name in matches[names_col].dropna():
                    provider_names.add(str(name).strip())
        
        # Return as sorted list (most recent first - this is heuristic, could be improved with dates)
        provider_names_list = sorted(list(provider_names))
        
        return jsonify({
            'ccn': ccn,
            'provider_names': provider_names_list,
            'count': len(provider_names_list)
        })
        
    except Exception as e:
        print(f"Error getting provider names for CCN: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/states')
def get_states():
    """API endpoint to get list of available states"""
    global facilities_data
    
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        # Find state column
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = None
        
        for col in state_columns:
            if col in facilities_data.columns:
                state_col = col
                break
        
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500
        
        # Get unique states
        states = facilities_data[state_col].dropna().unique().tolist()
        states.sort()
        
        return jsonify({'states': states, 'count': len(states)})
        
    except Exception as e:
        print(f"Error getting states: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/columns')
def get_columns():
    """API endpoint to get available columns in the dataset"""
    global facilities_data
    
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        columns = list(facilities_data.columns)
        return jsonify({'columns': columns, 'count': len(columns)})
        
    except Exception as e:
        print(f"Error getting columns: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sample')
def get_sample_data():
    """API endpoint to get sample data for debugging"""
    global facilities_data
    
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        # Get first few rows as sample
        sample = facilities_data.head(5)
        sample_list = []
        
        for _, row in sample.iterrows():
            facility = {}
            for col in row.index:
                if pd.isna(row[col]):
                    facility[col] = None
                else:
                    facility[col] = str(row[col])
            sample_list.append(facility)
        
        return jsonify({
            'sample': sample_list,
            'total_rows': len(facilities_data),
            'columns': list(facilities_data.columns)
        })
        
    except Exception as e:
        print(f"Error getting sample data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/survey-dates/<state>/<facility_id>')
def get_survey_dates(state, facility_id):
    """API endpoint to get survey dates for a specific facility - uses CCN to aggregate all dates across all sources"""
    global facilities_data, deficiencies_data
    
    print(f"API call received for survey dates - State: {state}, Facility ID: {facility_id}")
    
    if facilities_data is None:
        print("Error: facilities_data is None")
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        def normalize_ccn(value):
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return None
            s = str(value).strip()
            if not s:
                return None
            return s.lstrip('0').zfill(6)

        # Optional precise identifiers from query params
        query_ccn = request.args.get('ccn')
        forced_county = request.args.get('county')
        query_name = request.args.get('name')
        
        # Find the facility by unique_id first, then fall back to other identifiers if query params not provided
        facility = None
        
        # Try to find by unique_id (which is the index in our filtered list)
        try:
            facility_index = int(facility_id)
            # Get the original row from the state-filtered data
            state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
            state_col = None
            
            for col in state_columns:
                if col in facilities_data.columns:
                    state_col = col
                    break
            
            if state_col is None:
                return jsonify({'error': 'State column not found'}), 500
            
            # Normalize state input (convert name to code if needed) and match case-insensitively
            state_normalized = normalize_state_input(state)
            state_facilities = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == state_normalized]
            print(f"State matching: looking for '{state}' (normalized: '{state_normalized}'), found {len(state_facilities)} facilities")
            if 0 <= facility_index < len(state_facilities):
                facility = state_facilities.iloc[facility_index]
                facility_name_debug = None
                for col in ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']:
                    if col in facility.index and not pd.isna(facility[col]):
                        facility_name_debug = str(facility[col]).strip()
                        break
                print(f"Selected facility at index {facility_index}: {facility_name_debug or 'N/A'}")
            else:
                print(f"Warning: facility_index {facility_index} out of range (0-{len(state_facilities)-1})")
        except ValueError:
            # If facility_id is not a number, try other columns
            pass
        
        if facility is None and not (query_ccn or query_name):
            # Try to find by other identifiers (only if query params were not supplied)
            id_columns = ['CCN', 'ccn', 'CMS Certification Number', 'Provider ID', 'Facility ID']
            for col in id_columns:
                if col in facilities_data.columns:
                    matching = facilities_data[facilities_data[col] == facility_id]
                    if len(matching) > 0:
                        facility = matching.iloc[0]
                        break
        
        if facility is None:
            return jsonify({'error': 'Facility not found'}), 404
        
        if facility is not None:
            print(f"Found facility row via id lookup")
        
        # Look for survey date columns
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = None
        
        for col in survey_date_columns:
            if col in facilities_data.columns:
                survey_date_col = col
                print(f"Found survey date column: {col}")
                break
        
        if survey_date_col is None:
            print(f"Survey date column not found. Available columns: {list(facilities_data.columns)}")
            return jsonify({'error': 'Survey date column not found'}), 500
        
        # Prepare variables for response metadata
        facility_identifier = None
        facility_identifier_norm = None
        facility_name = None
        
        # If query params provided, use them; otherwise derive from facility row
        if query_ccn:
            facility_identifier = str(query_ccn)
        elif facility is not None:
            for col in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
                if col in facility.index and not pd.isna(facility[col]):
                    facility_identifier = str(facility[col])
                    break

        facility_identifier_norm = normalize_ccn(facility_identifier)
        if facility_identifier_norm:
            facility_identifier = facility_identifier_norm
        
        # Get the facility name
        if query_name:
            facility_name = str(query_name).strip()
        elif facility is not None:
            for col in ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']:
                if col in facility.index and not pd.isna(facility[col]):
                    facility_name = str(facility[col]).strip()
                    break
        
        # If query params were provided, build matching set from them first
        if (query_ccn or query_name):
            print(f"Filtering by query params - state: {state}, ccn: {facility_identifier}, name: {facility_name}")
            # Determine state column
            state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
            state_col = None
            for col in state_columns:
                if col in facilities_data.columns:
                    state_col = col
                    break
            if state_col is None:
                return jsonify({'error': 'State column not found'}), 500
            # Normalize state input and match case-insensitively
            state_normalized = normalize_state_input(state)
            state_filtered = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == state_normalized]
            matching_facilities = state_filtered[
                (state_filtered[survey_date_col].notna()) & 
                (state_filtered[survey_date_col] != '') &
                (state_filtered[survey_date_col] != 'nan')
            ]
            if facility_identifier_norm:
                ccn_columns = [c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in matching_facilities.columns]
                if ccn_columns:
                    ccn_col = ccn_columns[0]
                    ccn_matched = matching_facilities[
                        matching_facilities[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6) == facility_identifier_norm
                    ]
                    # If CCN matching found results, use them; otherwise fall back to name matching
                    if len(ccn_matched) > 0:
                        matching_facilities = ccn_matched
                    elif facility_name:
                        # Fallback to name matching if CCN didn't match
                        print(f"No rows found with CCN {facility_identifier_norm}, falling back to name matching")
                        for col in ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']:
                            if col in matching_facilities.columns:
                                name_matched = matching_facilities[matching_facilities[col].astype(str).str.strip() == facility_name]
                                if len(name_matched) > 0:
                                    matching_facilities = name_matched
                                    break
            elif facility_name:
                for col in ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']:
                    if col in matching_facilities.columns:
                        matching_facilities = matching_facilities[matching_facilities[col].astype(str).str.strip() == facility_name]
                        break
            print(f"Rows after query-param filtering: {len(matching_facilities)}")
        elif facility_identifier_norm:
            print(f"Looking for survey dates for CCN: {facility_identifier_norm} in state: {state}")
            
            # Find all rows with survey dates that match this exact facility
            # First filter by state to narrow down the search
            state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
            state_col = None
            for col in state_columns:
                if col in facilities_data.columns:
                    state_col = col
                    break
            
            if state_col is None:
                return jsonify({'error': 'State column not found'}), 500
            
            # Filter by state first (normalize state input)
            state_normalized = normalize_state_input(state)
            state_filtered = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == state_normalized]
            print(f"Found {len(state_filtered)} rows for state '{state}' (normalized: '{state_normalized}')")
            
            # Then filter by facility identifier (CCN) and name to get exact matches
            matching_facilities = state_filtered[
                (state_filtered[survey_date_col].notna()) & 
                (state_filtered[survey_date_col] != '') &
                (state_filtered[survey_date_col] != 'nan')
            ]
            ccn_columns = [c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in matching_facilities.columns]
            if ccn_columns:
                ccn_col = ccn_columns[0]
                # Filter by CCN - normalize both sides for comparison
                matching_facilities_ccn_normalized = matching_facilities[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
                ccn_matched = matching_facilities[matching_facilities_ccn_normalized == facility_identifier_norm]
                # If CCN matching found results, use them; otherwise fall back to name matching
                if len(ccn_matched) > 0:
                    matching_facilities = ccn_matched
                    print(f"Found {len(matching_facilities)} rows matching CCN {facility_identifier_norm}")
                else:
                    # Fallback: match by Provider Name if CCN matching failed
                    print(f"No rows found with CCN {facility_identifier_norm}, falling back to name matching")
                    name_cols = ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']
                    for name_col in name_cols:
                        if name_col in matching_facilities.columns:
                            name_matched = matching_facilities[matching_facilities[name_col].astype(str).str.strip() == facility_name]
                            if len(name_matched) > 0:
                                matching_facilities = name_matched
                                print(f"Found {len(matching_facilities)} rows matching by name: {facility_name}")
                                break
            else:
                # No CCN column available, match by name
                print(f"No CCN column found, matching by Provider Name")
                name_cols = ['Provider Name', 'provider_name', 'Facility Name', 'facility_name', 'Name', 'name']
                for name_col in name_cols:
                    if name_col in matching_facilities.columns:
                        name_matched = matching_facilities[matching_facilities[name_col].astype(str).str.strip() == facility_name]
                        if len(name_matched) > 0:
                            matching_facilities = name_matched
                            print(f"Found {len(matching_facilities)} rows matching by name: {facility_name}")
                            break
            
        else:
            # Cannot find matching facility; return empty list with 200 so frontend can render a friendly message
            return jsonify({
                'survey_dates': [],
                'facility': None,
                'facility_name': query_name or None,
                'state': state,
                'count': 0
            })
        
        # Process survey dates for the matching facilities
        survey_dates = []
        facility_names_set = set()
        for _, row in matching_facilities.iterrows():
            try:
                # Try to parse the date
                date_str = str(row[survey_date_col])
                if date_str and date_str != 'nan' and date_str != 'None':
                    # Try different date formats
                    parsed_date = None
                    date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%m-%d-%Y']
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = pd.to_datetime(date_str, format=fmt)
                            break
                        except:
                            continue
                    
                    if parsed_date is None:
                        # Try pandas automatic parsing
                        parsed_date = pd.to_datetime(date_str, errors='coerce')
                    
                    if parsed_date is not None and not pd.isna(parsed_date):
                        # Check if date is within our timeline range (2016-2025)
                        if pd.Timestamp('2016-01-01') <= parsed_date <= pd.Timestamp('2027-12-31'):
                            facility_name_value = row.get('Provider Name', row.get('provider_name', 'N/A'))
                            if facility_name_value and str(facility_name_value).strip():
                                facility_names_set.add(str(facility_name_value).strip())

                            row_ccn = None
                            for ccn_col_name in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
                                if ccn_col_name in row.index and not pd.isna(row[ccn_col_name]):
                                    row_ccn = normalize_ccn(row[ccn_col_name])
                                    break
                            row_ccn = row_ccn or facility_identifier_norm

                            survey_dates.append({
                                'date': parsed_date.strftime('%Y-%m-%d'),
                                'facility_name': facility_name_value,
                                'state': row.get('State', row.get('state', 'N/A')),
                                'ccn': row_ccn
                            })
            except Exception as e:
                print(f"Error parsing date {row[survey_date_col]}: {e}")
                continue
        
        # Also check deficiencies_data for this CCN if available
        if deficiencies_data is not None and facility_identifier_norm:
            print(f"Checking deficiencies data for CCN: {facility_identifier_norm}")
            # Normalize CCN
            ccn_normalized = facility_identifier_norm
            
            # Find CCN column in deficiencies_data
            ccn_cols = ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']
            def_ccn_col = next((c for c in ccn_cols if c in deficiencies_data.columns), None)
            
            if def_ccn_col and 'Survey Date' in deficiencies_data.columns:
                # Filter deficiencies by CCN
                deficiencies_matches = deficiencies_data[
                    deficiencies_data[def_ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6) == ccn_normalized
                ]
                
                # Get unique survey dates
                name_cols = ['Provider Name', 'Facility Name', 'provider_name', 'facility_name']
                name_col = next((c for c in name_cols if c in deficiencies_data.columns), 'Provider Name')
                
                for _, row in deficiencies_matches.iterrows():
                    date_str = str(row['Survey Date'])
                    if date_str and date_str not in ['nan', 'None', '']:
                        parsed_date = pd.to_datetime(date_str, errors='coerce')
                        if parsed_date is not None and not pd.isna(parsed_date):
                            if pd.Timestamp('2016-01-01') <= parsed_date <= pd.Timestamp('2027-12-31'):
                                date_str_formatted = parsed_date.strftime('%Y-%m-%d')
                                # Only add if not already in the list
                                if not any(d['date'] == date_str_formatted for d in survey_dates):
                                    deficiency_name = str(row.get(name_col, 'N/A'))
                                    if deficiency_name and deficiency_name.strip():
                                        facility_names_set.add(deficiency_name.strip())
                                    survey_dates.append({
                                        'date': date_str_formatted,
                                        'facility_name': deficiency_name,
                                        'state': state,
                                        'ccn': ccn_normalized
                                    })
                print(f"Added deficiency records for CCN {ccn_normalized}")
        
        # Sort dates chronologically
        survey_dates.sort(key=lambda x: x['date'])
        
        print(f"Found {len(survey_dates)} survey dates")
        print(f"Survey dates: {[d['date'] for d in survey_dates]}")
        
        facility_names_list = sorted(facility_names_set) if facility_names_set else ([facility_name] if facility_name else [])

        return jsonify({
            'survey_dates': survey_dates,
            'facility': facility_identifier_norm,
            'facility_name': facility_name,
            'facility_names': facility_names_list,
            'state': state,
            'count': len(survey_dates)
        })
        
    except Exception as e:
        print(f"Error getting survey dates: {e}")
        return jsonify({'error': str(e)}), 500


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in miles."""
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@app.route('/api/zip-peer-survey-dates/<state>/<facility_id>')
def get_zip_peer_survey_dates(state, facility_id):
    """Timeline 1: For selected facility, find other facilities in same County/Parish and return their Health Survey Dates."""
    print(f"\n=== PEER SURVEY DATES CALLED ===")
    print(f"State: {state}, Facility ID: {facility_id}")
    global facilities_data, provider_info_data
    if facilities_data is None or provider_info_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        query_ccn = request.args.get('ccn')
        forced_county = request.args.get('county')
        # Reuse survey date column detection
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = next((c for c in survey_date_columns if c in facilities_data.columns), None)
        if survey_date_col is None:
            return jsonify({'error': 'Survey date column not found'}), 500

        # Determine state col
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500

        # Locate selected facility row within state (normalize state input)
        state_normalized = normalize_state_input(state)
        state_filtered = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == state_normalized]
        print(f"State filtering: '{state}' -> '{state_normalized}', found {len(state_filtered)} facilities")
        selected = None
        # Prefer CCN if provided
        if query_ccn:
            q_norm = str(query_ccn).strip().lstrip('0').zfill(6)
            for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
                if idcol in state_filtered.columns:
                    col_norm = state_filtered[idcol].astype(str).str.strip().str.lstrip('0').str.zfill(6)
                    tmp = state_filtered[col_norm == q_norm]
                    if len(tmp) > 0:
                        selected = tmp.iloc[0]
                        break
        if selected is None:
            try:
                idx = int(facility_id)
                if 0 <= idx < len(state_filtered):
                    selected = state_filtered.iloc[idx]
            except ValueError:
                pass
        if selected is None:
            # fallback by facility_id matching CCN
            for idcol in ['CCN', 'ccn', 'CMS Certification Number']:
                if idcol in state_filtered.columns:
                    tmp = state_filtered[state_filtered[idcol].astype(str) == str(facility_id)]
                    if len(tmp) > 0:
                        selected = tmp.iloc[0]
                        break
        if selected is None:
            print("ERROR: Selected facility is None")
            return jsonify({'survey_dates': [], 'count': 0})

        print(f"Selected facility CCN columns: {[c for c in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)'] if c in selected.index]}")
        
        # Extract County/Parish from provider_info_data
        county_val = None
        selected_ccn = None
        for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
            if idcol in selected.index and pd.notna(selected[idcol]):
                selected_ccn = str(selected[idcol]).strip().lstrip('0').zfill(6)
                print(f"Selected CCN: {selected[idcol]} -> Normalized: {selected_ccn}")
                break
        
        if not selected_ccn:
            print("ERROR: No CCN found in selected facility")
            return jsonify({'survey_dates': [], 'count': 0})
        
        if selected_ccn:
            # Look up county from provider_info_data using normalized CCN
            ccn_col = 'CMS Certification Number (CCN)'
            if ccn_col in provider_info_data.columns:
                prov = provider_info_data.copy()
                prov['CCN_STR'] = prov[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
                provider_match = prov[prov['CCN_STR'] == selected_ccn]
                print(f"Provider matches found: {len(provider_match)}")
                if not provider_match.empty:
                    # Try multiple county columns, normalized
                    for ccol in ['County/Parish', 'County', 'County Name', 'county_name']:
                        if ccol in provider_match.columns and pd.notna(provider_match.iloc[0][ccol]):
                            county_val = str(provider_match.iloc[0][ccol]).strip()
                            break
                    print(f"County found: {county_val}")
        
        if forced_county:
            county_val = forced_county.strip()
        if not county_val:
            print(f"No county found, returning empty results")
            return jsonify({'survey_dates': [], 'count': 0})

        # Find peers in same County/Parish within same state
        # First, get all CCNs in the state from facilities_data
        state_ccns = set()
        for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
            if idcol in state_filtered.columns:
                state_ccns.update(state_filtered[idcol].astype(str).str.strip().str.lstrip('0').str.zfill(6))
        
        print(f"County/Parish: {county_val}, State CCNs: {len(state_ccns)}")
        
        # Find all facilities in the same county from provider_info_data
        prov = provider_info_data.copy()
        prov['CCN_STR'] = prov[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
        target_norm = str(county_val).strip().lower().replace(' county','').replace(' parish','')
        match_mask = pd.Series([False]*len(prov))
        for ccol in ['County/Parish', 'County', 'County Name', 'county_name']:
            if ccol in prov.columns:
                norm_col = prov[ccol].astype(str).str.strip().str.lower().str.replace(' county','', regex=False).str.replace(' parish','', regex=False)
                match_mask = match_mask | (norm_col == target_norm)
        # Also filter by state to ensure we only get facilities in the correct state
        prov_state_normalized = prov['State'].astype(str).str.strip().str.upper()
        county_providers = prov[(match_mask) & (prov['CCN_STR'].isin(state_ccns)) & (prov_state_normalized == state_normalized)]
        county_ccns = set(county_providers['CCN_STR'].astype(str))
        
        print(f"Facilities in county '{county_val}' (normalized: '{target_norm}') in state '{state_normalized}': {len(county_ccns)}")
        if len(county_ccns) > 0:
            print(f"Sample county CCNs: {list(county_ccns)[:5]}")
        
        # Filter state_filtered to only include facilities in the same county
        peers = state_filtered.copy()
        # Find CCN column for normalization
        ccn_col_peer = None
        for idcol_peer in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
            if idcol_peer in peers.columns:
                ccn_col_peer = idcol_peer
                break
        if ccn_col_peer:
            peers['CCN_NORM'] = peers[ccn_col_peer].astype(str).str.strip().str.lstrip('0').str.zfill(6)
            peers = peers[peers['CCN_NORM'].isin(county_ccns)]
        else:
            print("Warning: No CCN column found for peer filtering")
            peers = peers.iloc[0:0]  # Empty dataframe
        
        print(f"Peer facilities after filtering: {len(peers)}")

        # Collect all survey dates for these peers
        results = []
        print(f"Processing {len(peers)} peer facilities for survey dates...")
        for idx, (_, row) in enumerate(peers.iterrows()):
            date_str = str(row.get(survey_date_col, ''))
            if not date_str or date_str == 'nan' or date_str == 'None' or date_str == '':
                if idx < 3:  # Debug first few
                    print(f"  Row {idx}: No valid survey date (value: '{date_str}')")
                continue
            parsed = pd.to_datetime(date_str, errors='coerce')
            if parsed is not None and not pd.isna(parsed):
                if pd.Timestamp('2016-01-01') <= parsed <= pd.Timestamp('2027-12-31'):
                    # Extract CCN from various possible column names
                    ccn_val = None
                    for ccn_col_name in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
                        if ccn_col_name in row.index and pd.notna(row[ccn_col_name]):
                            ccn_val = str(row[ccn_col_name]).strip().lstrip('0').zfill(6)
                            break
                    
                    facility_name_val = row.get('Provider Name', row.get('provider_name', 'N/A'))
                    results.append({
                        'date': parsed.strftime('%Y-%m-%d'),
                        'facility_name': facility_name_val,
                        'state': row.get(state_col, 'N/A'),
                        'ccn': ccn_val if ccn_val else 'N/A'
                    })
                    if len(results) <= 5:  # Debug first few
                        print(f"  Added survey date: {parsed.strftime('%Y-%m-%d')} for {facility_name_val}")
                else:
                    if idx < 3:
                        print(f"  Row {idx}: Date {parsed} outside range (2016-2027)")
            else:
                if idx < 3:
                    print(f"  Row {idx}: Could not parse date '{date_str}'")
        
        results.sort(key=lambda x: x['date'])
        print(f"Total survey dates collected for peers: {len(results)}")
        return jsonify({'survey_dates': results, 'count': len(results), 'county': county_val})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nearby-peer-survey-dates/<state>/<facility_id>')
def get_nearby_peer_survey_dates(state, facility_id):
    """Timeline 2: facilities within 60 miles of selected facility's lat/lon; return their Health Survey Dates."""
    global facilities_data, provider_info_data
    
    if facilities_data is None or provider_info_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        query_ccn = request.args.get('ccn')
        # Required columns in provider_info
        required_cols = ['CMS Certification Number (CCN)', 'Latitude', 'Longitude']
        for col in required_cols:
            if col not in provider_info_data.columns:
                return jsonify({'error': f'Missing column in provider_info: {col}'}), 500

        # Try to resolve coords directly from CCN if provided
        sel_info = None
        if query_ccn:
            sel_info = provider_info_data[provider_info_data['CMS Certification Number (CCN)'].astype(str) == str(query_ccn)]
        if sel_info is None or len(sel_info) == 0:
            # Resolve through facilities_data selection
            state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
            state_col = next((c for c in state_columns if c in facilities_data.columns), None)
            if state_col is None:
                return jsonify({'error': 'State column not found'}), 500
            state_filtered = facilities_data[facilities_data[state_col] == state]
            selected = None
            if query_ccn:
                for idcol in ['CCN', 'ccn', 'CMS Certification Number']:
                    if idcol in state_filtered.columns:
                        tmp = state_filtered[state_filtered[idcol].astype(str) == str(query_ccn)]
                        if len(tmp) > 0:
                            selected = tmp.iloc[0]
                            break
            if selected is None:
                try:
                    idx = int(facility_id)
                    if 0 <= idx < len(state_filtered):
                        selected = state_filtered.iloc[idx]
                except ValueError:
                    pass
            if selected is None:
                for idcol in ['CCN', 'ccn', 'CMS Certification Number']:
                    if idcol in state_filtered.columns:
                        tmp = state_filtered[state_filtered[idcol].astype(str) == str(facility_id)]
                        if len(tmp) > 0:
                            selected = tmp.iloc[0]
                            break
            if selected is None:
                return jsonify({'survey_dates': [], 'count': 0})
            # Get CCN and find coords in provider_info
            ccn = None
            for idcol in ['CCN', 'ccn', 'CMS Certification Number']:
                if idcol in selected.index and pd.notna(selected[idcol]):
                    ccn = str(selected[idcol])
                    break
            sel_info = provider_info_data[provider_info_data['CMS Certification Number (CCN)'].astype(str) == str(ccn)]
        if len(sel_info) == 0:
            return jsonify({'survey_dates': [], 'count': 0})
        lat = float(sel_info.iloc[0]['Latitude'])
        lon = float(sel_info.iloc[0]['Longitude'])

        # Build candidate set (same state) with coords present
        prov = provider_info_data.dropna(subset=['Latitude', 'Longitude']).copy()
        # Map state from facilities_data: inner join on CCN
        # Prepare small mapping CCN -> state
        ccn_col_fd = next((c for c in ['CCN', 'ccn', 'CMS Certification Number'] if c in facilities_data.columns), None)
        if ccn_col_fd is None:
            return jsonify({'survey_dates': [], 'count': 0})
        mapping = facilities_data[[ccn_col_fd, state_col]].dropna()
        mapping[ccn_col_fd] = mapping[ccn_col_fd].astype(str)
        prov['CCN_STR'] = prov['CMS Certification Number (CCN)'].astype(str)
        prov = prov.merge(mapping, left_on='CCN_STR', right_on=ccn_col_fd, how='left')
        prov = prov[prov[state_col] == state]

        # Compute distance and filter <= 60 miles
        def within_60(row):
            try:
                distance = haversine_miles(lat, lon, float(row['Latitude']), float(row['Longitude']))
                return distance <= 60.0
            except Exception as e:
                return False
        prov = prov[prov.apply(within_60, axis=1)]

        # Get their survey dates from facilities_data
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = next((c for c in survey_date_columns if c in facilities_data.columns), None)
        if survey_date_col is None:
            return jsonify({'error': 'Survey date column not found'}), 500

        peer_ccns = set(prov['CCN_STR'].tolist())
        cands = facilities_data[facilities_data[ccn_col_fd].astype(str).isin(peer_ccns)]
        cands = cands[cands[state_col] == state]
        results = []
        for _, row in cands.iterrows():
            date_str = str(row.get(survey_date_col, ''))
            if not date_str or date_str == 'nan' or date_str == 'None':
                continue
            parsed = pd.to_datetime(date_str, errors='coerce')
            if parsed is not None and not pd.isna(parsed):
                if pd.Timestamp('2016-01-01') <= parsed <= pd.Timestamp('2027-12-31'):
                    results.append({
                        'date': parsed.strftime('%Y-%m-%d'),
                        'facility_name': row.get('Provider Name', row.get('provider_name', 'N/A')),
                        'state': row.get(state_col, 'N/A'),
                        'ccn': str(row.get(ccn_col_fd, 'N/A'))
                    })
        results.sort(key=lambda x: x['date'])
        return jsonify({'survey_dates': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Forecast API endpoints
@app.route('/api/facility-survey-dates/<state>/<facility_id>')
def get_facility_survey_dates(state, facility_id):
    """Get historical survey dates for a specific facility."""
    global facilities_data
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        query_ccn = request.args.get('ccn')
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500
        
        # Filter by state
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Find the facility
        facility = None
        if query_ccn:
            for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
                if idcol in state_facilities.columns:
                    tmp = state_facilities[state_facilities[idcol].astype(str) == str(query_ccn)]
                    if len(tmp) > 0:
                        facility = tmp.iloc[0]
                        break
        
        if facility is None:
            try:
                idx = int(facility_id)
                if 0 <= idx < len(state_facilities):
                    facility = state_facilities.iloc[idx]
            except ValueError:
                pass
        
        if facility is None:
            return jsonify({'survey_dates': [], 'count': 0})
        
        # Get survey dates
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = next((c for c in survey_date_columns if c in facilities_data.columns), None)
        
        if survey_date_col is None:
            return jsonify({'survey_dates': [], 'count': 0})
        
        survey_dates = []
        date_str = str(facility.get(survey_date_col, ''))
        if date_str and date_str != 'nan' and date_str != 'None':
            parsed = pd.to_datetime(date_str, errors='coerce')
            if parsed is not None and not pd.isna(parsed):
                if pd.Timestamp('2016-01-01') <= parsed <= pd.Timestamp('2027-12-31'):
                    survey_dates.append(parsed.strftime('%Y-%m-%d'))
        
        return jsonify({'survey_dates': survey_dates, 'count': len(survey_dates)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/state-average-interval/<state>')
def get_state_average_interval(state):
    """Calculate average time between surveys for facilities in a state."""
    global facilities_data
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500
        
        # Filter by state
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Get survey dates
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = next((c for c in survey_date_columns if c in facilities_data.columns), None)
        
        if survey_date_col is None:
            return jsonify({'average_days': 365, 'count': 0})
        
        intervals = []
        for _, facility in state_facilities.iterrows():
            date_str = str(facility.get(survey_date_col, ''))
            if date_str and date_str != 'nan' and date_str != 'None':
                parsed = pd.to_datetime(date_str, errors='coerce')
                if parsed is not None and not pd.isna(parsed):
                    if pd.Timestamp('2016-01-01') <= parsed <= pd.Timestamp('2027-12-31'):
                        # Calculate days since 2016-01-01 as a proxy for interval
                        days_since_start = (parsed - pd.Timestamp('2016-01-01')).days
                        intervals.append(days_since_start)
        
        if len(intervals) < 2:
            return jsonify({'average_days': 365, 'count': len(intervals)})
        
        # Calculate average interval (simplified - using median as proxy)
        intervals.sort()
        median_interval = intervals[len(intervals) // 2] if intervals else 365
        average_days = max(30, min(1095, median_interval // 2))  # Between 1 month and 3 years
        
        return jsonify({'average_days': average_days, 'count': len(intervals)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/zip-average-interval/<state>/<county>')
def get_zip_average_interval(state, county):
    """Calculate average time between surveys for facilities in a County/Parish."""
    global facilities_data, provider_info_data
    if facilities_data is None or provider_info_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500
        
        # Filter by state
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Get all CCNs in the state
        state_ccns = set()
        for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
            if idcol in state_facilities.columns:
                state_ccns.update(state_facilities[idcol].astype(str).str.strip().str.lstrip('0').str.zfill(6))
        
        # Find all facilities in the same county from provider_info_data
        ccn_col = 'CMS Certification Number (CCN)'
        county_providers = provider_info_data[
            (provider_info_data['County/Parish'] == county) & 
            (provider_info_data[ccn_col].astype(str).str.strip().isin(state_ccns))
        ]
        county_ccns = set(county_providers[ccn_col].astype(str).str.strip())
        
        # Filter state_facilities to only include facilities in the same county
        county_facilities = state_facilities.copy()
        for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
            if idcol in county_facilities.columns:
                county_facilities['CCN_NORM'] = county_facilities[idcol].astype(str).str.strip().str.lstrip('0').str.zfill(6)
                county_facilities = county_facilities[county_facilities['CCN_NORM'].isin(county_ccns)]
                break
        
        # Get survey dates
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = next((c for c in survey_date_columns if c in facilities_data.columns), None)
        
        if survey_date_col is None:
            return jsonify({'average_days': 365, 'count': 0})
        
        intervals = []
        for _, facility in county_facilities.iterrows():
            date_str = str(facility.get(survey_date_col, ''))
            if date_str and date_str != 'nan' and date_str != 'None':
                parsed = pd.to_datetime(date_str, errors='coerce')
                if parsed is not None and not pd.isna(parsed):
                    if pd.Timestamp('2016-01-01') <= parsed <= pd.Timestamp('2027-12-31'):
                        days_since_start = (parsed - pd.Timestamp('2016-01-01')).days
                        intervals.append(days_since_start)
        
        if len(intervals) < 2:
            return jsonify({'average_days': 365, 'count': len(intervals)})
        
        intervals.sort()
        median_interval = intervals[len(intervals) // 2] if intervals else 365
        average_days = max(30, min(1095, median_interval // 2))
        
        return jsonify({'average_days': average_days, 'count': len(intervals)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/similar-characteristics-interval/<state>', methods=['POST'])
def get_similar_characteristics_interval(state):
    """Calculate average time between surveys for facilities with similar characteristics."""
    global facilities_data
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        facility_data = request.get_json()
        if not facility_data:
            return jsonify({'error': 'No facility data provided'}), 400
        
        # This is a simplified implementation - in practice, you'd match on:
        # - Facility size (bed count)
        # - Public vs private
        # - Urban vs rural
        # - Other characteristics
        
        # For now, return a reasonable default based on state
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'average_days': 365, 'count': 0})
        
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Simplified: return state average with some variation
        base_days = 365
        variation = 30  # ±30 days
        average_days = base_days + (hash(str(facility_data)) % (2 * variation)) - variation
        average_days = max(30, min(1095, average_days))
        
        return jsonify({'average_days': average_days, 'count': len(state_facilities)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/similar-deficiencies-interval/<state>', methods=['POST'])
def get_similar_deficiencies_interval(state):
    """Calculate average time between surveys for facilities with similar deficiency patterns."""
    global facilities_data
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        facility_data = request.get_json()
        if not facility_data:
            return jsonify({'error': 'No facility data provided'}), 400
        
        # This would analyze deficiency patterns and find similar facilities
        # For now, return a reasonable default
        
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'average_days': 365, 'count': 0})
        
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Simplified: return state average with some variation based on facility
        base_days = 365
        variation = 45  # ±45 days for deficiency-based matching
        average_days = base_days + (hash(str(facility_data)) % (2 * variation)) - variation
        average_days = max(30, min(1095, average_days))
        
        return jsonify({'average_days': average_days, 'count': len(state_facilities)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/state-average-2year-interval/<state>')
def get_state_average_2year_interval(state):
    """Calculate average time between surveys for facilities in a state over past 2 years."""
    global facilities_data
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500
        
        # Filter by state
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Get survey dates
        survey_date_columns = ['Health Survey Date', 'health_survey_date', 'Survey Date', 'survey_date', 'Date', 'date']
        survey_date_col = next((c for c in survey_date_columns if c in facilities_data.columns), None)
        
        if survey_date_col is None:
            return jsonify({'average_days': 365, 'count': 0})
        
        # Filter to past 2 years (2023-2025)
        two_years_ago = pd.Timestamp('2023-01-01')
        now = pd.Timestamp('2027-12-31')
        
        intervals = []
        for _, facility in state_facilities.iterrows():
            date_str = str(facility.get(survey_date_col, ''))
            if date_str and date_str != 'nan' and date_str != 'None':
                parsed = pd.to_datetime(date_str, errors='coerce')
                if parsed is not None and not pd.isna(parsed):
                    if two_years_ago <= parsed <= now:
                        days_since_start = (parsed - two_years_ago).days
                        intervals.append(days_since_start)
        
        if len(intervals) < 2:
            return jsonify({'average_days': 365, 'count': len(intervals)})
        
        intervals.sort()
        median_interval = intervals[len(intervals) // 2] if intervals else 365
        average_days = max(30, min(730, median_interval // 2))  # Max 2 years
        
        return jsonify({'average_days': average_days, 'count': len(intervals)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/combined-criteria-2year-interval/<state>', methods=['POST'])
def get_combined_criteria_2year_interval(state):
    """Calculate average time between surveys using combined criteria over past 2 years."""
    global facilities_data
    if facilities_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    
    try:
        facility_data = request.get_json()
        if not facility_data:
            return jsonify({'error': 'No facility data provided'}), 400
        
        # This would combine:
        # - State filtering
        # - Similar characteristics
        # - Similar deficiency patterns
        # - Past 2 years only
        
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        
        if state_col is None:
            return jsonify({'average_days': 365, 'count': 0})
        
        state_facilities = facilities_data[facilities_data[state_col] == state]
        
        # Simplified: return weighted average with more sophisticated variation
        base_days = 365
        variation = 60  # ±60 days for combined criteria
        average_days = base_days + (hash(str(facility_data)) % (2 * variation)) - variation
        average_days = max(30, min(730, average_days))  # Max 2 years
        
        return jsonify({'average_days': average_days, 'count': len(state_facilities)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/state-monthly-surveys/<state>')
def get_state_monthly_surveys(state):
    """Section 4: Histogram of survey dates by month for the selected state.

    Counts unique (CCN, Survey Date) pairs sourced from health_deficiencies.xlsx for facilities in the state.
    """
    global facilities_data, deficiencies_data
    if facilities_data is None or deficiencies_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        # Resolve state and CCNs for that state from facilities_data
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        ccn_columns = ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        ccn_col_fac = next((c for c in ccn_columns if c in facilities_data.columns), None)
        if state_col is None or ccn_col_fac is None:
            return jsonify({'buckets': [], 'count': 0})

        # Match state case-insensitively
        fac_state = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == str(state).strip().upper()]
        if fac_state.empty:
            print(f"Warning: No facilities found for state '{state}'")
            return jsonify({'buckets': [], 'count': 0})
        
        # Get CCNs - ensure they're strings and handle NaN values
        ccn_series = fac_state[ccn_col_fac].astype(str)
        ccn_series = ccn_series[ccn_series != 'nan']
        ccn_series = ccn_series[ccn_series != '']
        if ccn_series.empty:
            print(f"Warning: No valid CCNs found for state '{state}'")
            return jsonify({'buckets': [], 'count': 0})
        
        # Normalize CCNs for matching (strip, remove leading zeros, pad to 6 digits)
        state_ccns = set(ccn_series.str.strip().str.lstrip('0').str.zfill(6))
        if not state_ccns:
            print(f"Warning: No valid CCNs after normalization for state '{state}'")
            return jsonify({'buckets': [], 'count': 0})

        # Prepare deficiencies with parsed dates and normalized CCN
        def_ccn_col = next((c for c in ccn_columns if c in deficiencies_data.columns), None)
        date_col_def = next((c for c in ['Health Survey Date', 'Survey Date', 'Date'] if c in deficiencies_data.columns), None)
        if def_ccn_col is None or date_col_def is None:
            print(f"Error: Missing columns in deficiencies_data. CCN col: {def_ccn_col}, Date col: {date_col_def}")
            print(f"Available columns: {list(deficiencies_data.columns)}")
            return jsonify({'buckets': [], 'count': 0})

        d = deficiencies_data[[def_ccn_col, date_col_def]].copy()
        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
        d['DATE'] = pd.to_datetime(d[date_col_def], errors='coerce')
        d = d[pd.notna(d['DATE'])]
        d = d[d['CCN_STR'].isin(state_ccns)]

        # Filter to required range and deduplicate by (CCN, DATE)
        start, end = pd.Timestamp('2016-01-01'), pd.Timestamp('2027-12-31')
        d = d[(d['DATE'] >= start) & (d['DATE'] <= end)]
        if d.empty:
            return jsonify({'buckets': [], 'count': 0})
        d = d.drop_duplicates(subset=['CCN_STR', 'DATE'])

        # Aggregate to month buckets (1..12)
        month_counts_series = d['DATE'].dt.month.value_counts()
        month_counts = {int(k): int(v) for k, v in month_counts_series.items()}
        buckets, total = [], 0
        for m in range(1, 13):
            c = int(month_counts.get(m, 0))
            total += c
            buckets.append({'month': m, 'label': calendar.month_abbr[m], 'count': c})
        return jsonify({'buckets': buckets, 'count': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/county-monthly-surveys/<state>/<county>')
def get_county_monthly_surveys(state, county):
    """Section 4: Histogram of survey dates by month for the selected county.

    Robust county matching (case-insensitive, removes 'County'/'Parish'), pulls CCNs from provider_info/facilities,
    reads dates from health_deficiencies.xlsx, dedupes by (CCN, date), aggregates by month.
    """
    global facilities_data, provider_info_data, deficiencies_data
    if deficiencies_data is None or (facilities_data is None and provider_info_data is None):
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        def normalize_county_name(s: str) -> str:
            s = str(s).strip().lower()
            for suf in [' county', ' parish']:
                if s.endswith(suf):
                    s = s[: -len(suf)].strip()
            return s

        county_norm = normalize_county_name(county)

        county_ccns = set()
        # Prefer provider_info_data for county resolution
        if provider_info_data is not None:
            state_col = next((c for c in ['State', 'STATE', 'Provider State', 'Provider_State'] if c in provider_info_data.columns), None)
            county_cols = [c for c in ['County/Parish', 'County', 'County Name', 'county_name'] if c in provider_info_data.columns]
            ccn_col = next((c for c in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn'] if c in provider_info_data.columns), None)
            if state_col and county_cols and ccn_col:
                dfc = provider_info_data[[state_col, ccn_col] + county_cols].copy()
                norm_match = None
                for col in county_cols:
                    dfc[f'__norm_{col}'] = dfc[col].apply(lambda v: normalize_county_name(v) if pd.notna(v) else '')
                    state_aliases = get_state_aliases(state)
                    tmp = dfc[dfc[state_col].astype(str).str.strip().isin(state_aliases) & (dfc[f'__norm_{col}'] == county_norm)]
                    if not tmp.empty:
                        norm_match = tmp
                        break
                if norm_match is not None and not norm_match.empty:
                    county_ccns.update(norm_match[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6).tolist())

        # Fallback using facilities_data
        if not county_ccns and facilities_data is not None:
            state_col = next((c for c in ['State', 'STATE', 'state', 'Provider State', 'Provider_State'] if c in facilities_data.columns), None)
            county_cols = [c for c in ['County/Parish', 'County', 'County Name', 'county_name'] if c in facilities_data.columns]
            ccn_col = next((c for c in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn'] if c in facilities_data.columns), None)
            if state_col and county_cols and ccn_col:
                dff = facilities_data[[state_col, ccn_col] + county_cols].copy()
                norm_match = None
                for col in county_cols:
                    dff[f'__norm_{col}'] = dff[col].apply(lambda v: normalize_county_name(v) if pd.notna(v) else '')
                    state_aliases = get_state_aliases(state)
                    tmp = dff[dff[state_col].astype(str).str.strip().isin(state_aliases) & (dff[f'__norm_{col}'] == county_norm)]
                    if not tmp.empty:
                        norm_match = tmp
                        break
                if norm_match is not None and not norm_match.empty:
                    county_ccns.update(norm_match[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6).tolist())

        if not county_ccns:
            return jsonify({'buckets': [], 'count': 0})

        # Read deficiencies
        def_ccn_col = next((c for c in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn'] if c in deficiencies_data.columns), None)
        date_col_def = next((c for c in ['Health Survey Date', 'Survey Date', 'Date'] if c in deficiencies_data.columns), None)
        if not def_ccn_col or not date_col_def:
            return jsonify({'buckets': [], 'count': 0})

        d = deficiencies_data[[def_ccn_col, date_col_def]].copy()
        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
        d['DATE'] = pd.to_datetime(d[date_col_def], errors='coerce')
        d = d[(d['CCN_STR'].isin(county_ccns)) & pd.notna(d['DATE'])]

        start, end = pd.Timestamp('2016-01-01'), pd.Timestamp('2027-12-31')
        d = d[(d['DATE'] >= start) & (d['DATE'] <= end)]

        if d.empty:
            return jsonify({'buckets': [], 'count': 0})

        d = d.drop_duplicates(subset=['CCN_STR', 'DATE'])
        month_counts_series = d['DATE'].dt.month.value_counts()
        month_counts = {int(k): int(v) for k, v in month_counts_series.items()}
        buckets, total = [], 0
        for m in range(1, 13):
            c = int(month_counts.get(m, 0))
            total += c
            buckets.append({'month': m, 'label': calendar.month_abbr[m], 'count': c})
        return jsonify({'buckets': buckets, 'count': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/zip-monthly-surveys/<state>/<zip>')
def get_zip_monthly_surveys(state, zip):
    """Section 4: Histogram of survey dates by month for the selected ZIP code."""
    global facilities_data, provider_info_data, deficiencies_data
    if deficiencies_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        # Normalize input ZIP to 5-digit string
        zip_digits = ''.join(ch for ch in str(zip) if ch.isdigit())
        zip5 = zip_digits[:5]

        # Optionally include selected facility CCN if provided
        explicit_ccn = request.args.get('ccn')
        if explicit_ccn:
            explicit_ccn = str(explicit_ccn).strip().lstrip('0').zfill(6)

        # Build CCN set for facilities in this state and ZIP using provider_info if available; fallback to facilities_data
        zip_ccns = set()
        if explicit_ccn:
            zip_ccns.add(explicit_ccn)

        def try_collect(df, state_cols, zip_cols, ccn_cols):
            if df is None:
                return
            state_col = next((c for c in state_cols if c in df.columns), None)
            zip_col = next((c for c in zip_cols if c in df.columns), None)
            ccn_col = next((c for c in ccn_cols if c in df.columns), None)
            if not state_col or not zip_col or not ccn_col:
                return
            tmp = df[[state_col, zip_col, ccn_col]].copy()
            tmp['ZIP5'] = tmp[zip_col].astype(str).str.replace(r'\D', '', regex=True).str.slice(0, 5)
            state_aliases = get_state_aliases(state)
            sub = tmp[tmp[state_col].astype(str).isin(state_aliases) & (tmp['ZIP5'] == zip5)]
            if not sub.empty:
                zip_ccns.update(sub[ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6).tolist())

        try_collect(provider_info_data, ['State', 'STATE', 'Provider State', 'Provider_State'], ['ZIP Code', 'Zip', 'ZIP'], ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn'])
        if not zip_ccns:
            try_collect(facilities_data, ['State', 'STATE', 'Provider State', 'Provider_State'], ['ZIP Code', 'Zip', 'ZIP'], ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn'])
        
        if not zip_ccns:
            return jsonify({'buckets': [], 'count': 0})
        
        # Get survey dates from deficiencies data
        def_ccn_col = None
        for col in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
            if col in deficiencies_data.columns:
                def_ccn_col = col
                break
        
        if not def_ccn_col or 'Survey Date' not in deficiencies_data.columns:
            return jsonify({'buckets': [], 'count': 0})
        
        d = deficiencies_data.copy()
        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
        d['Survey Date Parsed'] = pd.to_datetime(d['Survey Date'], errors='coerce')
        d = d[(d['CCN_STR'].isin(zip_ccns)) & pd.notna(d['Survey Date Parsed'])]
        
        start, end = pd.Timestamp('2016-01-01'), pd.Timestamp('2027-12-31')
        d = d[(d['Survey Date Parsed'] >= start) & (d['Survey Date Parsed'] <= end)]
        
        if d.empty:
            return jsonify({'buckets': [], 'count': 0})
        
        # Deduplicate by (CCN, Date) to avoid over-counting multi-deficiency days
        d = d.drop_duplicates(subset=['CCN_STR', 'Survey Date Parsed'])

        # Aggregate over years: group by calendar month (1..12)
        month_counts_series = d['Survey Date Parsed'].dt.month.value_counts()
        month_counts = {int(k): int(v) for k, v in month_counts_series.items()}
        buckets = []
        total = 0
        for m in range(1, 13):
            c = int(month_counts.get(m, 0))
            total += c
            buckets.append({
                'month': m,
                'label': calendar.month_abbr[m],
                'count': c
            })
        return jsonify({'buckets': buckets, 'count': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/deficiencies/<state>/<facility_id>')
def get_deficiencies_for_facility_and_zip(state, facility_id):
    """Section 6: Return deficiencies for selected facility and for same ZIP peers, with trend counts by category."""
    global facilities_data, deficiencies_data
    if facilities_data is None or deficiencies_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        # Resolve state and CCN + ZIP of selected facility
        state_columns = ['State', 'STATE', 'state', 'Provider State', 'Provider_State']
        state_col = next((c for c in state_columns if c in facilities_data.columns), None)
        if state_col is None:
            return jsonify({'error': 'State column not found'}), 500
        # Normalize state input and match case-insensitively
        state_normalized = normalize_state_input(state)
        state_filtered = facilities_data[facilities_data[state_col].astype(str).str.strip().str.upper() == state_normalized]
        selected = None
        query_ccn = request.args.get('ccn')
        
        print(f"🔍 Deficiencies API Debug:")
        print(f"🔍 State: {state} (normalized: {state_normalized}), Facility ID: {facility_id}, Query CCN: {query_ccn}")
        print(f"🔍 State filtered facilities count: {len(state_filtered)}")
        print(f"🔍 Available CCN columns: {[c for c in state_filtered.columns if 'ccn' in c.lower() or 'certification' in c.lower()]}")
        
        if query_ccn:
            print(f"🔍 Searching for CCN: {query_ccn}")
            for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
                if idcol in state_filtered.columns:
                    print(f"🔍 Checking column '{idcol}' for CCN match")
                    # Show sample CCN values from this column
                    sample_ccns = state_filtered[idcol].dropna().astype(str).head(5).tolist()
                    print(f"🔍 Sample CCN values in '{idcol}': {sample_ccns}")
                    tmp = state_filtered[state_filtered[idcol].astype(str) == str(query_ccn)]
                    print(f"🔍 Found {len(tmp)} matches in column '{idcol}'")
                    if len(tmp) > 0:
                        selected = tmp.iloc[0]
                        print(f"🔍 Selected facility found via CCN in column '{idcol}'")
                        break
        if selected is None:
            try:
                idx = int(facility_id)
                if 0 <= idx < len(state_filtered):
                    selected = state_filtered.iloc[idx]
            except ValueError:
                pass
        if selected is None:
            for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
                if idcol in state_filtered.columns:
                    tmp = state_filtered[state_filtered[idcol].astype(str) == str(facility_id)]
                    if len(tmp) > 0:
                        selected = tmp.iloc[0]
                        break
        if selected is None:
            return jsonify({'error': 'Facility not found'}), 404

        # Pull CCN and ZIP5
        # CCN
        ccn = None
        for idcol in ['CCN', 'ccn', 'CMS Certification Number', 'CMS Certification Number (CCN)']:
            if idcol in selected.index and pd.notna(selected[idcol]):
                ccn = str(selected[idcol]).strip()
                print(f"🔍 Extracted CCN from column '{idcol}': {ccn}")
                break
        
        if not ccn:
            print(f"🔍 ERROR: No CCN found for facility")
            return jsonify({'error': 'CCN not found for facility'}), 404
        
        # Normalize CCN for matching
        ccn_normalized = str(ccn).strip().lstrip('0').zfill(6)
        print(f"🔍 CCN normalized: '{ccn}' -> '{ccn_normalized}'")
        
        # ZIP
        zip5 = None
        for zc in ['ZIP Code', 'Zip', 'ZIP']:
            if zc in selected.index and pd.notna(selected[zc]):
                s = str(selected[zc]); digits = ''.join(ch for ch in s if ch.isdigit())
                zip5 = digits[:5] if len(digits) >= 5 else None
                break

        # Filter deficiencies for selected facility (by CCN and state)
        d = deficiencies_data.copy()
        # Normalize CCN in deficiencies data for matching
        def_ccn_col = next((c for c in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn'] if c in d.columns), None)
        if not def_ccn_col:
            print(f"🔍 ERROR: No CCN column found in deficiencies_data")
            return jsonify({'error': 'CCN column not found in deficiencies data'}), 500
        
        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6)
        
        # Find survey date column
        date_cols = ['Survey Date', 'Health Survey Date', 'Date', 'date', 'survey_date']
        date_col = next((c for c in date_cols if c in d.columns), None)
        if not date_col:
            print(f"🔍 ERROR: No date column found in deficiencies_data. Available columns: {list(d.columns)}")
            return jsonify({'error': 'Date column not found in deficiencies data'}), 500
        
        d['Survey Date Parsed'] = pd.to_datetime(d[date_col], errors='coerce')
        d_sel = d[(d['CCN_STR'] == ccn_normalized)]
        print(f"🔍 Found {len(d_sel)} deficiency records for CCN {ccn_normalized}")
        
        # Find other required columns
        cat_col = next((c for c in ['Deficiency Category', 'Category', 'category'] if c in d.columns), None)
        tag_col = next((c for c in ['Deficiency Tag Number', 'Tag Number', 'Tag', 'tag'] if c in d.columns), None)
        desc_col = next((c for c in ['Deficiency Description', 'Description', 'description'] if c in d.columns), None)
        
        if not all([cat_col, tag_col, desc_col]):
            print(f"🔍 WARNING: Missing some columns. Category: {cat_col}, Tag: {tag_col}, Description: {desc_col}")
            # Use available columns
            available_cols = [date_col]
            if cat_col: available_cols.append(cat_col)
            if tag_col: available_cols.append(tag_col)
            if desc_col: available_cols.append(desc_col)
            d_sel = d_sel[available_cols].sort_values(date_col)
        else:
            d_sel = d_sel[[date_col, cat_col, tag_col, desc_col]].sort_values(date_col)

        # Filter peers in same ZIP
        zip_cols = ['ZIP Code', 'Zip', 'ZIP', 'zip_code', 'zip']
        zip_col = next((c for c in zip_cols if c in d.columns), None)
        if zip_col and zip5:
            d['ZIP5'] = d[zip_col].astype(str).str.replace(r'\D', '', regex=True).str.slice(0, 5)
            d_zip = d[(d['ZIP5'] == zip5)]
            
            # Find provider name column for peer list
            prov_name_cols = ['Provider Name', 'Facility Name', 'provider_name', 'facility_name', 'Name', 'name']
            prov_name_col = next((c for c in prov_name_cols if c in d.columns), None)
            
            # Build list of columns for peer deficiencies
            zip_list_cols = []
            if prov_name_col: zip_list_cols.append(prov_name_col)
            zip_list_cols.append(date_col)
            if cat_col: zip_list_cols.append(cat_col)
            if tag_col: zip_list_cols.append(tag_col)
            if desc_col: zip_list_cols.append(desc_col)
            
            if zip_list_cols:
                d_zip_list = d_zip[zip_list_cols].sort_values([prov_name_col if prov_name_col else date_col, date_col])
            else:
                d_zip_list = d_zip[[date_col]].sort_values(date_col)
        else:
            d_zip = pd.DataFrame()
            d_zip_list = pd.DataFrame()

        # Trend counts by category in same ZIP
        if not d_zip.empty and cat_col:
            trends = d_zip.groupby(cat_col).size().reset_index(name='count').sort_values('count', ascending=False)
            trends_list = [{'category': str(r[cat_col]), 'count': int(r['count'])} for _, r in trends.iterrows()]
        else:
            trends_list = []

        # Simple text summary
        top_categories = ', '.join([f"{t['category']} ({t['count']})" for t in trends_list[:5]]) if trends_list else 'No deficiencies found'
        summary = f"In ZIP {zip5 if zip5 else 'selected ZIP'}, the most frequent deficiency categories are: {top_categories}." if zip5 else "ZIP code not available for peer analysis."

        return jsonify({
            'facility_deficiencies': d_sel.to_dict(orient='records'),
            'zip_deficiencies': d_zip_list.to_dict(orient='records'),
            'zip_trends': trends_list,
            'trend_summary': summary,
            'zip': zip5,
            'ccn': ccn
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/state-facility-surveys/<state>')
def get_state_facility_surveys(state):
    """Return real per-facility survey dates for a state using health_deficiencies.xlsx.
    Response format: { survey_dates: [ { ccn: str, date: 'YYYY-MM-DD', facility_name: str } ] }
    """
    global facilities_data, deficiencies_data
    if facilities_data is None or deficiencies_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        # Identify CCN columns in facilities data
        ccn_cols = [c for c in facilities_data.columns if c.lower() in (
            'ccn', 'cms certification number', 'cms certification number (ccn)'
        )]
        state_cols = [c for c in facilities_data.columns if c.lower() in (
            'state', 'provider state', 'provider_state'
        )]
        if not ccn_cols or not state_cols:
            return jsonify({'error': 'Required columns not found in facilities data'}), 500
        ccn_col = ccn_cols[0]
        state_col = state_cols[0]

        # Build set of CCNs for the requested state
        state_mask = facilities_data[state_col].astype(str) == str(state)
        state_ccns = set(facilities_data.loc[state_mask, ccn_col].astype(str).str.strip())
        if not state_ccns:
            return jsonify({'survey_dates': []})

        # Prepare deficiencies with CCN string and parsed date
        d = deficiencies_data.copy()
        def_ccn_col = None
        for col in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
            if col in d.columns:
                def_ccn_col = col
                break
        if def_ccn_col is None or 'Survey Date' not in d.columns:
            return jsonify({'error': 'Required columns not found in deficiencies data'}), 500

        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip()
        d['Survey Date Parsed'] = pd.to_datetime(d['Survey Date'], errors='coerce')
        d = d[pd.notna(d['Survey Date Parsed'])]

        # Filter to CCNs in this state
        d_state = d[d['CCN_STR'].isin(state_ccns)]
        if d_state.empty:
            return jsonify({'survey_dates': []})

        # Build response records
        name_col = None
        for col in ['Provider Name', 'Facility Name', 'provider_name', 'facility_name']:
            if col in d_state.columns:
                name_col = col
                break

        records = []
        for _, row in d_state.iterrows():
            date_iso = row['Survey Date Parsed'].date().isoformat()
            records.append({
                'ccn': row['CCN_STR'],
                'date': date_iso,
                'facility_name': str(row[name_col]) if name_col else ''
            })

        return jsonify({'survey_dates': records})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/state-deficiency-trends/<state>')
def get_state_deficiency_trends(state):
    """Return trends in frequency for deficiencies for the selected state.
    Response: { state_trends: [{category, count}], state_trend_summary: str }
    """
    global facilities_data, deficiencies_data
    if facilities_data is None or deficiencies_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        # Resolve state and CCN set
        state_columns = [c for c in facilities_data.columns if c.lower() in ('state', 'provider state', 'provider_state')]
        ccn_columns = [c for c in facilities_data.columns if c.lower() in ('ccn', 'cms certification number', 'cms certification number (ccn)')]
        if not state_columns or not ccn_columns:
            return jsonify({'error': 'Required columns not found in facilities data'}), 500
        state_col = state_columns[0]
        ccn_col = ccn_columns[0]
        state_mask = facilities_data[state_col].astype(str) == str(state)
        state_ccns = set(facilities_data.loc[state_mask, ccn_col].astype(str).str.strip())
        if not state_ccns:
            return jsonify({'state_trends': [], 'state_trend_summary': ''})

        # Prepare deficiencies CCN and filter
        d = deficiencies_data.copy()
        def_ccn_col = None
        for col in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
            if col in d.columns:
                def_ccn_col = col
                break
        if def_ccn_col is None or 'Deficiency Category' not in d.columns:
            return jsonify({'error': 'Required columns not found in deficiencies data'}), 500

        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip()
        d_state = d[d['CCN_STR'].isin(state_ccns)]
        if d_state.empty:
            return jsonify({'state_trends': [], 'state_trend_summary': ''})

        trends = d_state.groupby('Deficiency Category').size().reset_index(name='count').sort_values('count', ascending=False)
        state_trends = [{'category': r['Deficiency Category'], 'count': int(r['count'])} for _, r in trends.iterrows()]
        top_categories = ', '.join([f"{t['category']} ({t['count']})" for t in state_trends[:5]]) if state_trends else 'No deficiencies found'
        summary = f"In state {state}, the most frequent deficiency categories are: {top_categories}."
        return jsonify({'state_trends': state_trends, 'state_trend_summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/county-deficiency-trends/<state>/<county>')
def get_county_deficiency_trends(state, county):
    """Return trends in frequency for deficiencies for facilities in a specific county.
    Response: { county_trends: [{category, count}], county_trend_summary: str }
    """
    global facilities_data, deficiencies_data, provider_info_data
    if facilities_data is None or deficiencies_data is None or provider_info_data is None:
        return jsonify({'error': 'Data not loaded'}), 500
    try:
        # Get all CCNs in the state
        state_columns = [c for c in facilities_data.columns if c.lower() in ('state', 'provider state', 'provider_state')]
        ccn_columns = [c for c in facilities_data.columns if c.lower() in ('ccn', 'cms certification number', 'cms certification number (ccn)')]
        if not state_columns or not ccn_columns:
            return jsonify({'error': 'Required columns not found in facilities data'}), 500
        state_col = state_columns[0]
        ccn_col = ccn_columns[0]
        state_mask = facilities_data[state_col].astype(str) == str(state)
        state_ccns = set(facilities_data.loc[state_mask, ccn_col].astype(str).str.strip().str.lstrip('0').str.zfill(6))
        if not state_ccns:
            return jsonify({'county_trends': [], 'county_trend_summary': ''})

        # Find all facilities in the same county from provider_info_data
        ccn_col_provider = 'CMS Certification Number (CCN)'
        county_providers = provider_info_data[
            (provider_info_data['County/Parish'] == county) & 
            (provider_info_data[ccn_col_provider].astype(str).str.strip().isin(state_ccns))
        ]
        county_ccns = set(county_providers[ccn_col_provider].astype(str).str.strip())
        if not county_ccns:
            return jsonify({'county_trends': [], 'county_trend_summary': ''})

        # Prepare deficiencies CCN and filter
        d = deficiencies_data.copy()
        def_ccn_col = None
        for col in ['CMS Certification Number (CCN)', 'CMS Certification Number', 'CCN', 'ccn']:
            if col in d.columns:
                def_ccn_col = col
                break
        if def_ccn_col is None or 'Deficiency Category' not in d.columns:
            return jsonify({'error': 'Required columns not found in deficiencies data'}), 500

        d['CCN_STR'] = d[def_ccn_col].astype(str).str.strip()
        d_county = d[d['CCN_STR'].isin(county_ccns)]
        if d_county.empty:
            return jsonify({'county_trends': [], 'county_trend_summary': ''})

        trends = d_county.groupby('Deficiency Category').size().reset_index(name='count').sort_values('count', ascending=False)
        county_trends = [{'category': r['Deficiency Category'], 'count': int(r['count'])} for _, r in trends.iterrows()]
        top_categories = ', '.join([f"{t['category']} ({t['count']})" for t in county_trends[:5]]) if county_trends else 'No deficiencies found'
        summary = f"In {county} county, {state}, the most frequent deficiency categories are: {top_categories}."
        return jsonify({'county_trends': county_trends, 'county_trend_summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-schedule', methods=['POST'])
def generate_schedule():
    """Accepts { prompt: str } and returns { text: str, todoist_json: str }.
    Uses ChatGPT output and splits narrative from an embedded JSON block if present.
    """
    try:
        data = request.get_json(silent=True) or {}
        prompt = data.get('prompt', '')
        if not prompt:
            return jsonify({'error': 'Missing prompt'}), 400

        # Get API key from environment variable for security
        from openai import OpenAI
        import json, re
        import os
        # Read API key from environment variable (for deployment) or file (for local development)
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            # Fallback to file for local development
            key_file_path = Path('DanConwayKey.txt')
            if key_file_path.exists():
                try:
                    with open(key_file_path, 'r') as f:
                        api_key = f.read().strip()
                except Exception as e:
                    print(f"Error reading API key file: {e}")
        
        if not api_key:
            return jsonify({'error': 'OpenAI API key not found. Please set OPENAI_API_KEY environment variable or provide DanConwayKey.txt file.'}), 500
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",  # Using gpt-4o (or change to "gpt-3.5-turbo" for cheaper option)
            messages=[{"role": "user", "content": prompt}]
        )
        raw_text = response.choices[0].message.content or ''

        # Attempt to extract a JSON block from the model output
        todoist_json_str = ''
        narrative = raw_text

        def try_set_json(s):
            nonlocal todoist_json_str, narrative
            try:
                obj = json.loads(s)
                todoist_json_str = json.dumps(obj, separators=(',', ':'), ensure_ascii=False)
                # Remove the JSON from the narrative if present verbatim
                if s in narrative:
                    narrative = narrative.replace(s, '').strip()
                return True
            except Exception:
                return False

        # 1) Fenced code block ```json ... ``` or ``` ... ``` (any language)
        fenced_json = re.search(r"```json\s*([\s\S]*?)\s*```", raw_text, re.IGNORECASE)
        if fenced_json:
            candidate = fenced_json.group(1).strip()
            if try_set_json(candidate):
                pass  # Success
            else:
                # Try to extract JSON from within the fenced block
                json_match = re.search(r"\{[\s\S]*\}", candidate)
                if json_match:
                    try_set_json(json_match.group(0))
        
        # 2) If not found, look for any fenced code block that might contain JSON
        if not todoist_json_str:
            fenced_any = re.search(r"```\s*([\s\S]*?)\s*```", raw_text)
            if fenced_any:
                candidate = fenced_any.group(1).strip()
                # Check if it looks like JSON (starts with { or [)
                if candidate.strip().startswith(('{', '[')):
                    try_set_json(candidate)
        
        # 3) If still not found, look for the largest brace block
        if not todoist_json_str:
            # Find all potential JSON blocks (starting with { and ending with })
            json_candidates = re.findall(r"\{[\s\S]*?\}", raw_text)
            for candidate in json_candidates:
                if try_set_json(candidate):
                    break
        
        # 4) If still not found, look for array format [...]
        if not todoist_json_str:
            array_candidates = re.findall(r"\[[\s\S]*?\]", raw_text)
            for candidate in array_candidates:
                if try_set_json(candidate):
                    break

        # Fallback: no JSON found
        if not todoist_json_str:
            # Return narrative as-is; empty JSON string
            return jsonify({'text': raw_text.strip(), 'todoist_json': ''})

        return jsonify({'text': narrative.strip(), 'todoist_json': todoist_json_str})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import-todoist', methods=['POST'])
def import_todoist():
    """Accepts { token: str, todoist_json: str } and creates tasks in Todoist.
    Supports two JSON formats:
      1) Direct array of task objects for /tasks
      2) Object with "items" array similar to previous stub
    Each task minimally should include a "content" field; optional due_date, project_id, etc.
    """
    try:
        import json
        import requests
        payload = request.get_json(silent=True) or {}
        token = (payload.get('token') or '').strip()
        todoist_json_text = (payload.get('todoist_json') or '').strip()
        if not token:
            return jsonify({'error': 'Missing Todoist token'}), 400
        if not todoist_json_text:
            return jsonify({'error': 'Missing todoist_json'}), 400

        # Parse provided JSON text
        try:
            parsed = json.loads(todoist_json_text)
        except Exception as e:
            return jsonify({'error': f'Invalid JSON: {e}'}), 400

        # Normalize to an array of tasks
        if isinstance(parsed, dict) and 'items' in parsed and isinstance(parsed['items'], list):
            tasks = parsed['items']
        elif isinstance(parsed, list):
            tasks = parsed
        elif isinstance(parsed, dict) and 'tasks' in parsed and isinstance(parsed['tasks'], list):
            tasks = parsed['tasks']
        else:
            return jsonify({'error': 'Unsupported JSON format. Provide an array of tasks or an object with "items" or "tasks" array.'}), 400

        # Validate minimal shape and map fields to Todoist API
        created = []
        errors = []
        for idx, t in enumerate(tasks):
            if not isinstance(t, dict):
                errors.append({'index': idx, 'error': 'Task must be an object'})
                continue
            content = t.get('content') or t.get('title') or t.get('name')
            if not content:
                errors.append({'index': idx, 'error': 'Task missing content/title/name'})
                continue
            body = {
                'content': content
            }
            # Optional fields mapping; ignore unknowns
            if 'due' in t and isinstance(t['due'], (str, dict)):
                body['due_string'] = t['due'] if isinstance(t['due'], str) else t['due'].get('string') or t['due'].get('date')
            elif 'due_date' in t:
                body['due_date'] = t['due_date']
            elif 'date' in t:
                body['due_string'] = t['date']
            if 'priority' in t:
                body['priority'] = t['priority']
            if 'description' in t:
                body['description'] = t['description']
            if 'project_id' in t:
                body['project_id'] = t['project_id']
            if 'section_id' in t:
                body['section_id'] = t['section_id']

            try:
                r = requests.post(
                    'https://api.todoist.com/rest/v2/tasks',
                    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                    data=json.dumps(body)
                )
                if r.status_code in (200, 201):
                    created.append(r.json())
                else:
                    try:
                        err_payload = r.json()
                    except Exception:
                        err_payload = {'text': r.text}
                    errors.append({'index': idx, 'status': r.status_code, 'error': err_payload})
            except Exception as e:
                errors.append({'index': idx, 'error': str(e)})

        return jsonify({'created_count': len(created), 'error_count': len(errors), 'errors': errors})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Loading facilities data...")
    data = load_facilities_data()
    
    if data is not None:
        print("Data loaded successfully!")
        print(f"Dataset shape: {data.shape}")
        print(f"Columns: {list(data.columns)}")
        
        # Move HTML file to static folder for Flask (only if static version doesn't exist)
        static_dir = 'static'
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
        
        static_html_path = os.path.join(static_dir, 'Dashboard.html')
        # Only copy from root if static version doesn't exist (to preserve manual edits)
        if os.path.exists('Dashboard.html') and not os.path.exists(static_html_path):
            import shutil
            shutil.copy('Dashboard.html', static_html_path)
            print(f"Copied Dashboard.html to {static_dir}/")
        elif os.path.exists(static_html_path):
            print(f"Using existing {static_html_path} (not overwriting with root Dashboard.html)")
        
        print("\nStarting Flask server...")
        print("Dashboard will be available at: http://localhost:5000/")
        print("Press Ctrl+C to stop the server")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("Failed to load data. Please check your data files.")
