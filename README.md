# SWL Tools

A collection of tools for shortwave listeners (SWL) to check broadcast schedules and find active stations.

## Overview

This project provides utilities to query and display shortwave radio broadcast schedules from the EiBi (Eibi) database. The main tool allows you to check which stations are currently broadcasting on a specific frequency.

## Features

- **Real-time Schedule Checking**: Query current broadcasts on any frequency
- **UTC Time Display**: All times shown in UTC for international coordination
- **Active Station Highlighting**: Currently broadcasting stations are highlighted in green
- **Remaining Time Display**: Shows how much time is left for active broadcasts
- **Midnight Crossing Support**: Correctly handles broadcasts that span across midnight
- **Multi-language Support**: Displays station language and target area information
- **Transmitter Site Extraction**: Extracts transmitter sites with GPS coordinates to JSON

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd swl-tools
```

2. Ensure Python 3 is installed:
```bash
python3 --version
```

3. Make the script executable:
```bash
chmod +x checksked.py
```

## Usage

### Check Stations on a Frequency

```bash
./checksked.py <frequency_in_kHz>
```

**Example:**
```bash
./checksked.py 1170
```

**Output:**
```
Stations en onde à la fréquence 1170 kHz en ce moment -> 14:46 UTC

1170 kHz 0000-0350 UTC Pays: KOR Site: k      Station: KBS Hanminjok            Langue: K   Cible:   FE 0350
1170 kHz 0950-1000 UTC Pays: KOR Site: k      Station: KBS Hanminjok            Langue: K   Cible:   FE 0050
1170 kHz 1400-2400 UTC Pays: KOR Site: k      Station: KBS Hanminjok            Langue: K   Cible:   FE 1000 ◄ ON AIR (reste: 09h14)
1170 kHz 1000-1100 UTC Pays: KOR Site: k      Station: KBS World Radio          Langue: K   Cible:   FE 0100
...
```

### Update Schedule Data

```bash
./updatesked.py <schedule_period>
```

**Example:**
```bash
./updatesked.py b25
```

Downloads the latest EiBi schedule data for the specified season (`a` = summer, `b` = winter, followed by 2-digit year). Also extracts transmitter site locations and coordinates into `transmitter-sites.json`:

```json
[
  {
    "country": "AFG",
    "site_code": "k",
    "name": "Kabul / Pol-e-Charkhi",
    "lat": 34.5333,
    "lon": 69.3333
  }
]
```

## Data Format

The tool reads schedule data from CSV files in the `swl-schedules-data/` directory. The CSV format includes:

- **kHz**: Frequency in kilohertz
- **Time(UTC)**: Broadcast time range in UTC (HHMM-HHMM format)
- **Days**: Days of operation (if applicable)
- **ITU**: Country code
- **Station**: Station name
- **Lng**: Language code
- **Target**: Target area
- **Remarks**: Additional information
- **P**: Priority/Power indicator
- **Start/Stop**: Start and stop dates

## Schedule Files

- `sked-current.csv`: Current season's broadcast schedule
- `transmitter-sites.json`: Transmitter sites with decimal lat/lon coordinates
- `sked-a25.csv`: A25 season schedule (example)

## Output Fields

- **Pays**: Country code (3 letters)
- **Site**: Transmitter site location code
- **Station**: Broadcasting station name
- **Langue**: Language code (e.g., K=Korean, J=Japanese, E=English)
- **Cible**: Target area (e.g., FE=Far East, SAf=South Africa)
- **Duration**: Broadcast duration in HHMM format
- **◄ ON AIR**: Indicator for currently active broadcasts
- **reste**: Remaining time for active broadcasts

## Language Codes

Common language codes used:
- `E`: English
- `F`: French
- `S`: Spanish
- `K`: Korean
- `J`: Japanese
- `R`: Russian
- `M`: Mandarin Chinese
- `A`: Arabic
- `P`: Portuguese

## Target Area Codes

Common target area codes:
- `FE`: Far East
- `SEA`: Southeast Asia
- `Eu`: Europe
- `NAf`: North Africa
- `SAf`: South Africa
- `ME`: Middle East
- `SAs`: South Asia
- `NAm`: North America

## Requirements

- Python 3.x
- Standard library modules: `sys`, `os`, `csv`, `datetime`, `json`, `re`

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## Data Source

Schedule data is based on the EiBi (Eibi) shortwave broadcast schedule database.
http://eibispace.de/

## License

GPLv3

## Author

Michel Lachaine, mike@mikelachaine.ca

## Acknowledgments

- EiBi for providing comprehensive shortwave broadcast schedules
- The shortwave listening 