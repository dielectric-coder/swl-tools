# SWL Schedule Tool User Guide

## Getting Started

### Prerequisites

- Python 3.x
- [rich](https://github.com/Textualize/rich) — `pip install rich` or `pacman -S python-rich`
- [textual](https://github.com/Textualize/textual) — `pip install textual` or `pacman -S python-textual`
- A [Nerd Font](https://www.nerdfonts.com/) in your terminal (for powerline glyphs)

### Configuration

Create `swlconfig.conf` in the project root with your location (QTH) and optional radio connection:

```ini
[qth]
lat = 45.5017
lon = -73.5673
name = Montreal, QC

[radio]
host = localhost
port = 4532
```

The `[qth]` section is used to calculate great-circle distance and compass bearing to each transmitter site. The `[radio]` section configures the connection to the EladSpectrum CAT server for the `t` (tune) key. You can also set the radio host and port via command-line flags:

```bash
swl --host 192.168.1.50 --cat-port 4532
```

These values are saved to the config file automatically, so you only need to pass them once.

### Downloading Schedule Data

Before using the tools, download the current EiBi schedule:

```bash
./updatesked.py b25
```

- `b` = winter season, `a` = summer season
- `25` = year (2025)
- Example: `a26` for summer 2026

This downloads schedule files into `swl-schedules-data/` and extracts transmitter site coordinates.

## Interactive TUI Dashboard (swl.py)

Launch with:

```bash
./swl.py
```

### Screen Layout

- **Title bar** — App name, live UTC clock, your QTH location
- **Input prompts** — Starship-style powerline prompts for Frequency and Update
- **Schedule table** — Search results with broadcast details
- **Status bar** — Data stats and hints

### Searching for a Frequency

1. Type a frequency in kHz in the **Frequency** input (e.g. `6070`)
2. Press **Enter**
3. The table shows all broadcasts on that frequency

### Understanding the Results

| Column | Description |
|--------|-------------|
| kHz | Frequency |
| UTC | Broadcast time range (HHMM-HHMM) |
| Pays | Country code (ITU 3-letter) |
| Site | Transmitter site code |
| Station | Station name |
| Lng | Language code |
| Cible | Target area |
| Dur. | Broadcast duration |
| Dist. (km) | Distance from your QTH |
| Bearing | Compass bearing from your QTH |
| Status | ON AIR or NEXT indicator |

### Status Indicators

- **◄ ON AIR 02h15** (bold green) — Station is currently broadcasting, 2h15m remaining
- **→ NEXT 05h30** (light grey) — Station is off air, next broadcast starts in 5h30m

### Station Detail View

Press **Enter** on a table row to open a detail modal showing:
- Frequency, station name, schedule, status
- Country name, transmitter site with coordinates
- Distance and bearing from your QTH
- Language and target area (resolved to full names)

Press **Escape** to close the detail view.

### Updating Schedules

1. Type a schedule period in the **Update** input (e.g. `b25`, `a26`)
2. Press **Enter**
3. The update log appears showing download progress
4. Data reloads automatically on completion

Or press **F5** to trigger an update using the current period input value.

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Search (in frequency input) / Update (in period input) / Detail (in table) |
| F5 | Update schedules |
| Tab / Shift+Tab | Navigate between widgets |
| / (slash) | Focus frequency input |
| q / Escape | Quit |
| Arrow keys | Navigate table rows |

## CLI Schedule Check (checksked.py)

For a quick check without the TUI:

```bash
./checksked.py 6070
```

Displays a formatted table with all broadcasts on that frequency. Active stations are highlighted in bold green with `◄ ON AIR` and remaining time.

## Schedule Period Format

| Period | Season | Example |
|--------|--------|---------|
| `a25` | Summer 2025 | March–October |
| `b25` | Winter 2025 | October–March |
| `a26` | Summer 2026 | March–October |
| `b26` | Winter 2026 | October–March |

## Common Language Codes

| Code | Language |
|------|----------|
| E | English |
| F | French |
| S | Spanish |
| K | Korean |
| J | Japanese |
| R | Russian |
| M | Mandarin Chinese |
| A | Arabic |
| P | Portuguese |

## Common Target Area Codes

| Code | Area |
|------|------|
| FE | Far East |
| SEA | Southeast Asia |
| Eu | Europe |
| NAf | North Africa |
| SAf | South Africa |
| ME | Middle East |
| SAs | South Asia |
| NAm | North America |

## Data Source

All schedule data comes from [EiBi](http://eibispace.de/) (Ernst Eibert's shortwave broadcast database).
