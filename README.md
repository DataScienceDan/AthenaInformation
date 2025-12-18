# Athena Information Dashboard

A comprehensive web-based dashboard for analyzing healthcare facility survey data, deficiencies, and generating preparation schedules for CMS health surveys.

## Features

### Section 1: Facility Selection
- **State Selection**: Dropdown to select from all 50 US states
- **Facility Selection**: Dynamic dropdown showing facilities within the selected state
- **Facility Information Display**: Shows CMS Certification Number (CCN), Provider Name, Address, County, Ratings, and other details
- **Interactive Map**: Visual representation of facilities and survey dates

### Section 2: Health Survey Dates
- **Timeline Visualization**: Interactive timeline showing all historical survey dates (2016-2027)
- **Deduplication**: Automatically removes duplicate survey dates
- **Facility Name History**: Shows facility names at the time of each survey
- **CCN Matching**: Filters surveys by CMS Certification Number

### Section 3: Peer Survey Timelines
- **County-Level Peers**: Shows survey dates for facilities in the same county
- **Dynamic Timeline**: Timeline extends 15 months from current date
- **Color-Coded Markers**: Different colors for different facilities
- **Interactive Legend**: Click to highlight specific facilities

### Section 4: Monthly Health Survey Dates
- **State Histogram**: Monthly distribution of surveys for the selected state
- **County Histogram**: Monthly distribution for the facility's county
- **ZIP Code Histogram**: Monthly distribution for the facility's ZIP code

### Section 5: Deficiency Trends
- **State Trends**: Deficiency frequency by category at state level
- **County Trends**: Deficiency frequency by category at county level
- **ZIP Trends**: Deficiency frequency by category at ZIP code level

### Section 6: Forecasts
- **Six Forecast Models**: Multiple prediction methods for next survey date
- **Date Selection**: Calendar input for expected survey date (validates future dates only)
- **Additional Information**: Text area for facility-specific context (mission, considerations)
- **Dynamic Prompt Generation**: Adjusts schedule blocks based on time available

### Section 7: Health Deficiencies Prompt Builder
- **Facility Deficiencies**: Historical deficiencies for selected facility
- **Peer Deficiencies**: Deficiencies from facilities in same ZIP code
- **Trend Analysis**: Category-based deficiency trends
- **Prompt Integration**: Ready for schedule generation

### Section 8: Schedule Generation Prompt
- **Comprehensive Prompt**: Includes all context, trends, and facility information
- **Dynamic Scheduling**: Adjusts preparation timeline based on available time
- **Additional Context**: Incorporates user-provided facility information

### Section 9: Generated Schedule
- **ToDoist Integration**: JSON format ready for import
- **Task Breakdown**: Detailed preparation tasks with due dates
- **Priority Assignment**: Tasks prioritized by importance

## Setup Instructions

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DataScienceDan/AthenaInformation.git
   cd AthenaInformation
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Prepare data files:**
   - Place `SurveySummaryAll.csv` in the project root (must have CCN as first column)
   - Place `provider_info.csv` in the project root (must have CCN as first column)
   - Place `health_deficiencies.csv` in the project root (must have CCN column)

### Running the Dashboard

1. **Start the server:**
   ```bash
   python Dashboard.py
   ```

2. **Access the dashboard:**
   - Open your web browser
   - Navigate to: `http://localhost:5000/`

3. **Stop the server:**
   - Press `Ctrl+C` in the terminal

## Data Structure

### Required Files

1. **SurveySummaryAll.csv**
   - First column must be: `CMS Certification Number (CCN)`
   - Must include: `Provider Name`, `State`, `Health Survey Date`
   - CCN values are treated as strings (leading zeros preserved)

2. **provider_info.csv**
   - First column must be: `CMS Certification Number (CCN)`
   - Must include: `Provider Name`, `State`, `County/Parish`, `Overall Rating`, etc.
   - Used for enriching facility data with ratings and location info

3. **health_deficiencies.csv**
   - Must include: `CMS Certification Number (CCN)`, `Survey Date`, `Deficiency Category`, etc.
   - Used for deficiency analysis and trends
   - If this file is large, the application will **automatically split it into 25,000-row chunk files** (`health_deficiencies_part1.csv`, `health_deficiencies_part2.csv`, ...) on first run and rename the original to `health_deficiencies_bak.csv` (which is ignored by Git). All parts are then concatenated in memory into a single DataFrame for analysis.

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/states` - Get list of available states
- `GET /api/facilities/<state>` - Get facilities for a specific state
- `GET /api/survey-dates/<state>/<facility_id>` - Get survey dates for a facility
- `GET /api/zip-peer-survey-dates/<state>/<facility_id>` - Get peer survey dates
- `GET /api/deficiencies/<state>/<facility_id>` - Get deficiencies for facility
- `GET /api/state-monthly-surveys/<state>` - Get monthly survey histogram for state
- `GET /api/county-monthly-surveys/<state>/<county>` - Get monthly survey histogram for county
- `GET /api/zip-monthly-surveys/<state>/<zip>` - Get monthly survey histogram for ZIP
- `GET /api/provider-names/<ccn>` - Get all historical provider names for a CCN
- `POST /api/generate-schedule` - Generate schedule from prompt

## File Structure

```
AthenaInformation/
├── Dashboard.py              # Flask server application
├── static/
│   └── Dashboard.html       # Main dashboard interface
├── requirements.txt          # Python dependencies
├── Procfile                  # Deployment configuration
├── README.md                # This file
├── SurveySummaryAll.csv     # Survey data (CCN as first column)
├── provider_info.csv        # Provider information (CCN as first column)
└── health_deficiencies.csv  # Deficiency data
```

## Key Features

- **CCN as Primary Key**: All data files use CCN as the primary identifier
- **String Handling**: CCNs are treated as strings to preserve leading zeros
- **State Normalization**: Handles both state names and codes
- **Flexible Column Names**: Adapts to varying column name formats
- **Collapsible Sections**: All sections can be collapsed/expanded independently
- **Date Validation**: Prevents selection of past dates in forecasts
- **Dynamic Prompts**: Adjusts content based on available time and context

## Deployment

The application can be deployed to:
- **Heroku**: Uses `Procfile` for configuration
- **Render**: Uses `render.yaml` for configuration
- **Other Platforms**: Standard Flask application

## Troubleshooting

### Common Issues

1. **"Data not loaded" error:**
   - Ensure all CSV files are in the project directory
   - Verify CCN is the first column in each file
   - Check file permissions

2. **"Not available" in Section 1:**
   - Verify `provider_info.csv` is present and has correct columns
   - Check that CCN values match between files

3. **Empty timelines:**
   - Verify `health_deficiencies.csv` has survey dates
   - Check date format in CSV files

4. **Port already in use:**
   - Change the port in `Dashboard.py`
   - Or stop other services using port 5000

## License

[Add your license here]

## Author

DataScienceDan
