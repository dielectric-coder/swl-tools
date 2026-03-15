# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWL Schedule Tool (v1.0.0) is a collection of Python utilities for shortwave listeners (SWL) to check broadcast schedules and find active stations. The tools query the EiBi (Eibi) shortwave broadcast schedule database to display real-time station information.

## Core Commands

### Interactive TUI Dashboard
```bash
swl-sched
swl-sched --host 192.168.1.50 --cat-port 4532
```
Full-screen terminal dashboard with frequency search, station search, bearing/distance, and live UTC clock. Supports `--host` and `--cat-port` flags for remote radio CAT control; values are saved to config for subsequent runs.

### Check Stations on a Frequency
```bash
checksked <frequency_in_kHz>
```
Example: `checksked 1170`

Displays all broadcasts on the specified frequency, highlighting currently active stations in green with remaining airtime.

### Update Schedule Data
```bash
updatesked <schedule_period> [--insecure]
```
Example: `updatesked b25` or `updatesked a25`

Downloads the latest schedule data from EiBi for the specified season:
- Format: `a` (summer) or `b` (winter) followed by 2-digit year
- Downloads CSV schedules, frequency lists, and broadcast lists
- Converts encoding from ISO-8859-1 to UTF-8
- Updates files in `swl-schedules-data/` directory

## Packaging

### Project layout (src-layout)

```
src/eibi_swl/          # Python package installed to site-packages
  __init__.py           # __version__ = "1.0.0"
  _paths.py             # XDG path resolution (dev vs installed)
  swl.py                # TUI dashboard
  checksked.py          # CLI frequency query
  updatesked.py         # Schedule downloader
  swlconfig.conf.sample # Sample config for distribution
  countrycode.dat       # ITU country codes
  targetcode            # Target area codes
  transmittersite       # Transmitter site locations
  swl-schedules-data/   # Bundled schedule data (current files)
```

### Path resolution (`_paths.py`)

| Install method | Schedules (writable) | User config |
|---|---|---|
| `pip install -e .` (dev) | `src/eibi_swl/swl-schedules-data/` | `src/eibi_swl/swlconfig.conf` |
| `pip install` (system) | `~/.local/share/eibi-swl/` | `~/.config/eibi-swl/swlconfig.conf` |

### Entry points (pyproject.toml)

- `swl-sched` → `eibi_swl.swl:main`
- `checksked` → `eibi_swl.checksked:main`
- `updatesked` → `eibi_swl.updatesked:main`

### Build commands

- `pip install -e .` — editable install for development
- `python -m build` — build sdist + wheel
- `cd packaging/archlinux && makepkg -si` — Arch Linux package
- `.venv/bin/pyinstaller --onefile --name swl-sched ...` — standalone binary (see below)

### Standalone binary (PyInstaller)

Produces a single self-contained ELF executable (~16MB) that bundles Python, textual, rich, and all data files. No Python installation required on the target machine.

**Prerequisites**: PyInstaller must be installed in the project venv (`.venv/bin/pip install pyinstaller`).

**Build command**:
```bash
.venv/bin/pyinstaller --onefile --name swl-sched \
  --add-data "src/eibi_swl/countrycode.dat:eibi_swl" \
  --add-data "src/eibi_swl/targetcode:eibi_swl" \
  --add-data "src/eibi_swl/transmittersite:eibi_swl" \
  --add-data "src/eibi_swl/swlconfig.conf.sample:eibi_swl" \
  --add-data "src/eibi_swl/swl-schedules-data:eibi_swl/swl-schedules-data" \
  --hidden-import=textual --hidden-import=rich \
  --collect-all=textual --collect-all=rich \
  --paths=src src/eibi_swl/swl.py
```

**Output**: `dist/swl-sched`

**Important**: PyInstaller must run from the project venv that has `textual` and `rich` installed, not from a system-wide or pipx install, otherwise the dependencies won't be bundled.

### Arch Linux package

The PKGBUILD at `packaging/archlinux/PKGBUILD` builds a wheel and installs it system-wide via `python-installer`. It also installs a `.desktop` file for application menu integration.

```bash
cd packaging/archlinux && makepkg -si
```

Installs:
- Entry points (`swl-sched`, `checksked`, `updatesked`) to `/usr/bin/`
- Desktop entry to `/usr/share/applications/swl-sched.desktop`

Runtime dependencies: `python`, `python-rich`, `python-textual`

### Desktop entry

`packaging/swl-sched.desktop` provides application menu integration. It launches `swl-sched` in a terminal emulator. Installed automatically by the Arch package, or manually:

```bash
cp packaging/swl-sched.desktop ~/.local/share/applications/
```

## Architecture

### Main Scripts

**src/eibi_swl/swl.py** - Interactive TUI dashboard (Textual)
- Full-screen terminal UI with live UTC clock, frequency search, and schedule table
- Tokyo Night theme with black background
- Starship-style powerline input prompts (two-line `╭─░▒▓`/`╰─` segments with nerd font glyphs)
- Three input fields: Frequency (kHz), Station (name search), and Update (schedule period)
  - Enter in frequency input → search by freq, auto-fills Station field with first result
  - Enter in station input → case-insensitive substring search, auto-fills Frequency field with first result
  - Editing either search field clears the other (via `Input.prevent(Input.Changed)`)
  - Enter in period input → download schedules; period validated with `^[ab]\d{2}$`
- Results sorted: ON AIR first (by remaining time asc), then NEXT (by time-until asc), unparseable last
  - `compute_on_air()` returns sort_minutes as 4th value for sorting
- Displays bearing and great-circle distance from user's QTH to each transmitter site
- Uses `swlconfig.conf` for QTH coordinates (INI format with `[qth]` section: lat, lon, name)
- Loads `transmitter-sites.json` for site lookups keyed by `(country, site_code)`
- Haversine formula for distance, initial bearing with 8-point compass labels
- ON AIR rows highlighted in bold green with remaining time
- NEXT indicator in light grey showing time until broadcast starts for inactive stations
- Station detail modal (Enter on row) with round blue border
- DataTable with sortable columns, zebra stripes, row cursor
- Key bindings: Enter to search/update, F5 to update schedules, t to tune radio, m to show azMap, z to zoom, l to log entry, Escape to unfocus input, q to quit
- **Radio tuning** (`t` key): sends a CAT command to tune the radio to the selected row's frequency. If azMap is already running (FIFO at `/tmp/azmap-target.fifo` has an active reader), also updates the map target automatically. If azMap is not running, only tunes without launching a new map instance.
- **Frequency zoom** (`z` key): scans the entire schedule for on-air stations and inserts the nearest on-air station below and above the selected row's frequency directly into the current results table, highlighted in bold blue (`#769ff0`). Pressing `z` again removes previous zoom rows before inserting fresh ones. Uses `_build_result()` and `_rebuild_table_rows()` helpers shared with `_do_search()`. Cursor stays on the original row after insertion.
- **azMap IPC** (`m` key): sends target coordinates and station details to a running azMap instance via a named pipe (FIFO) at `/tmp/azmap-target.fifo`. If no azMap is running (FIFO open fails with ENXIO), launches a new instance via `subprocess.Popen` passing 4 positional args: QTH lat/lon as center, transmitter site lat/lon as target, plus `-c` (QTH name), `-t` (station name), and `-d` (station detail string) flags. The `-d` flag passes `station|freq|country|site|lang|target` so azMap has full station info on first launch. FIFO wire format: `lat,lon,name|station|freq kHz|country|site|lang|target\n`. Subsequent `m` presses send updates via FIFO to the running instance.

**src/eibi_swl/checksked.py** - Query tool for checking active broadcasts
- Reads `swl-schedules-data/sked-current.csv` (semicolon-delimited CSV)
- Parses broadcast time ranges and handles midnight-crossing broadcasts
- Compares current UTC time against schedule entries
- Uses `rich` library for output: `Panel` header with frequency/UTC time, `Table` for schedule rows
- Active broadcasts highlighted in bold green with `◄ ON AIR` indicator and remaining time
- Uses UTF-8 encoding to read CSV files (converted from ISO-8859-1 by updatesked)

**src/eibi_swl/updatesked.py** - Schedule update tool
- Downloads schedule files from `https://eibispace.de/dx` with verified SSL (requires `--insecure` flag to bypass on cert failure)
- Downloads capped at 10 MB per file
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

### Data Files (all under `src/eibi_swl/`)

**swl-schedules-data/** - Schedule data directory
- `sked-current.csv` - Active schedule data (CSV format, semicolon-delimited)
- `freq-current.dat` - Frequency-sorted broadcast list
- `bc-current.dat` - Time-sorted broadcast list
- `README-current.TXT` - EiBi documentation about data format and usage
- `transmitter-sites.json` - Extracted transmitter sites with decimal lat/lon coordinates
- Archived seasonal files kept in repo root `swl-schedules-data/`

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
- Midnight-crossing broadcasts: HHMM values are converted to total minutes before subtracting
- Active broadcast detection handles both normal and midnight-crossing cases

### Display Formatting

**swl.py TUI:**
- Tokyo Night theme with black backgrounds throughout
- Starship-style powerline prompts using Nerd Font glyphs (`\ue0b0`, `\uf10c`)
- Input prompts centered horizontally with separator line above table
- Active rows: bold green `◄ ON AIR HHhMM`; inactive rows: `#aaaaaa` grey `→ NEXT HHhMM`
- Unparseable time ranges display `"—"` in status column
- Detail modal: round `#769ff0` border, `#a9b1d6` text on black
- Data reload after update is thread-safe via `_apply_reload()` callback

**checksked.py CLI:**
- `Panel` header showing frequency and current UTC time
- `Table` with columns: kHz, UTC, Pays, Site, Station, Lng, Cible, Dur., Status
- Active broadcasts styled `bold green` with "◄ ON AIR" indicator
- Warning messages styled `yellow`
- Console width set to minimum 110 columns for proper table rendering

### Configuration

**swlconfig.conf** - User QTH location and radio connection (INI format)
```ini
[qth]
lat = 45.5017
lon = -73.5673
name = Montreal, QC

[radio]
host = localhost
port = 4532
```

Read by `swl.py` using `configparser` (stdlib). The `[qth]` section is used for bearing/distance calculations. The `[radio]` section configures the CAT server connection for the `t` (tune) key. Radio settings can also be set via `--host` and `--cat-port` CLI flags, which are saved to the config automatically.

## Dependencies

Python >=3.10. External packages (auto-installed via `pip install eibi-swl-dashboard`):
- `rich>=13.0` - Terminal formatting (checksked.py, swl.py)
- `textual>=0.40` - TUI framework (swl.py)

Optional external commands:
- `cowsay` and `lolcat` - Used by updatesked.py for completion message (graceful fallback if unavailable)

## Data Source

Schedule data sourced from EiBi: http://eibispace.de/

License: GPLv3
