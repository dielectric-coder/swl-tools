# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWL Tools is a collection of Python utilities for shortwave listeners (SWL) to check broadcast schedules and find active stations. The tools query the EiBi (Eibi) shortwave broadcast schedule database to display real-time station information.

## Core Commands

### Check Stations on a Frequency
```bash
./checksked.py <frequency_in_kHz>
```
Example: `./checksked.py 1170`

Displays all broadcasts on the specified frequency, highlighting currently active stations in green with remaining airtime.

### Update Schedule Data
```bash
./updatesked.py <schedule_period>
```
Example: `./updatesked.py b25` or `./updatesked.py a25`

Downloads the latest schedule data from EiBi for the specified season:
- Format: `a` (summer) or `b` (winter) followed by 2-digit year
- Downloads CSV schedules, frequency lists, and broadcast lists
- Converts encoding from ISO-8859-1 to UTF-8
- Updates files in `swl-schedules-data/` directory

## Architecture

### Main Scripts

**checksked.py** - Query tool for checking active broadcasts
- Reads `swl-schedules-data/sked-current.csv` (semicolon-delimited CSV)
- Parses broadcast time ranges and handles midnight-crossing broadcasts
- Compares current UTC time against schedule entries
- Uses `rich` library for output: `Panel` header with frequency/UTC time, `Table` for schedule rows
- Active broadcasts highlighted in bold green with `◄ ON AIR` indicator and remaining time
- Uses latin-1 encoding to read CSV files

**updatesked.py** - Schedule update tool
- Downloads schedule files from `http://eibispace.de/dx`
- Processes three file types:
  - `sked-{period}.csv` → `sked-current.csv` (main schedule)
  - `freq-{period}.txt` → `freq-current.dat` (frequency-sorted)
  - `bc-{period}.txt` → `bc-current.dat` (time-sorted)
- Converts all downloaded files from ISO-8859-1 to UTF-8 encoding
- Validates schedule period format with regex: `^[ab]\d{2}$`
- Extracts transmitter sites and coordinates from README Section IV into `transmitter-sites.json`
  - `parse_dms_coord()` converts EiBi DMS coordinates (e.g., `34N32`, `26S07'40"`) to decimal degrees
  - `extract_transmitter_sites()` parses country codes, site codes, names, and coordinates
  - Handles multi-site entries, `except:` markers, and entries without coordinates

### Data Files

**swl-schedules-data/** - Schedule data directory
- `sked-current.csv` - Active schedule data (CSV format, semicolon-delimited)
- `freq-current.dat` - Frequency-sorted broadcast list
- `bc-current.dat` - Time-sorted broadcast list
- `README-current.TXT` - EiBi documentation about data format and usage
- `transmitter-sites.json` - Extracted transmitter sites with decimal lat/lon coordinates
- Archived seasonal files: `sked-{a|b}##.csv`, `freq-{a|b}##.txt`, `bc-{a|b}##.txt`

**countrycode.dat** - ITU country codes (binary format)

**targetcode** - Target area code definitions (text format)
- Defines geographic target areas: Af (Africa), FE (Far East), Eu (Europe), etc.
- Includes directional codes: NE, SE, NW, SW, ENE, ESE, etc.

**transmittersite** - Transmitter site locations (text format)
- Format: Country code, site code, location name, coordinates
- Example: `AFG: k-Kabul / Pol-e-Charkhi 34N32-69E20`

### CSV Schedule Format

The `sked-current.csv` file uses semicolon delimiters with these columns:
1. kHz - Frequency in kilohertz
2. Time(UTC) - Broadcast time range (HHMM-HHMM format)
3. Days - Days of operation (optional)
4. ITU - Country code (3 letters)
5. Station - Station name
6. Lng - Language code (single letter or short code)
7. Target - Target area code
8. Remarks - Additional information
9. P - Priority/Power indicator
10. Start - Start date
11. Stop - Stop date

### Time Handling

Both scripts work exclusively in UTC:
- `checksked.py` uses `datetime.now(timezone.utc)` for current time
- Time format: HHMM (24-hour format as integer)
- Midnight-crossing broadcasts: When end_time < start_time, duration calculation adds 2400
- Active broadcast detection handles both normal and midnight-crossing cases

### Display Formatting

Output uses the `rich` library:
- `Panel` header showing frequency and current UTC time
- `Table` with columns: kHz, UTC, Pays, Site, Station, Lng, Cible, Dur., Status
- Active broadcasts styled `bold green` with "◄ ON AIR" indicator
- Warning messages styled `yellow`
- Console width set to minimum 110 columns for proper table rendering

## Dependencies

Python 3.x:
- `sys`, `os`, `csv`, `datetime`, `rich` (checksked.py)
- `sys`, `os`, `subprocess`, `urllib.request`, `shutil`, `re`, `json` (updatesked.py)

Optional external commands:
- `cowsay` and `lolcat` - Used by updatesked.py for completion message (graceful fallback if unavailable)

## Data Source

Schedule data sourced from EiBi: http://eibispace.de/

License: GPLv3
