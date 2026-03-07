#!/usr/bin/env python3

from eibi_swl import __version__
from eibi_swl._paths import resolve_data_dir, resolve_config
from eibi_swl._schedule import compute_on_air

import argparse
import os
import sys
import csv
import json
import re
import configparser
import socket
import subprocess
from math import radians, sin, cos, sqrt, atan2, degrees
from datetime import datetime, timezone

from textual.app import App
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, DataTable, Static, RichLog
from textual.containers import Container, Horizontal, Vertical
from rich.text import Text
from textual.reactive import reactive
from textual import work


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHED_DIR = resolve_data_dir()
CONFIG_FILE = resolve_config()
SITES_JSON = os.path.join(SCHED_DIR, "transmitter-sites.json")
SKED_CSV = os.path.join(SCHED_DIR, "sked-current.csv")
COUNTRY_FILE = os.path.join(SCRIPT_DIR, "countrycode.dat")
TARGET_FILE = os.path.join(SCRIPT_DIR, "targetcode")
README_FILE = os.path.join(SCHED_DIR, "README-current.TXT")


def load_country_names():
    """Parse countrycode.dat → {code: name}."""
    names = {}
    try:
        with open(COUNTRY_FILE, "r", encoding="latin-1") as f:
            for line in f:
                line = line.rstrip("\n")
                stripped = line.lstrip()
                if not stripped:
                    continue
                parts = stripped.split(None, 1)
                if len(parts) == 2:
                    names[parts[0]] = parts[1]
    except FileNotFoundError:
        pass
    return names


def load_target_names():
    """Parse targetcode → {code: name} with compound code expansion."""
    names = {}
    prefixes = {}  # single-letter prefix → expansion (e.g. "C" → "Central")
    regions = {}   # base region codes (e.g. "Af" → "Africa")
    try:
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or " - " not in stripped:
                    continue
                code, name = stripped.split(" - ", 1)
                code = code.strip()
                name = name.strip()
                if code.endswith(".."):
                    # Directional prefix: "C.." → "Central", "N.." → "North"
                    prefixes[code[0]] = name.rstrip(" .")
                else:
                    names[code] = name
                    # Track short base regions (2-letter like Af, Am, As, Eu, Oc, In)
                    if len(code) == 2 and code[0].isupper() and code[1].islower():
                        regions[code] = name
    except FileNotFoundError:
        pass
    # Store prefixes and regions for compound resolution
    names["_prefixes"] = prefixes
    names["_regions"] = regions
    return names


def resolve_target_name(code, target_names, country_names):
    """Resolve a target code to a human-readable name."""
    if not code:
        return ""
    # Direct match
    if code in target_names and not code.startswith("_"):
        return target_names[code]
    # Compound: 1-letter prefix + base region (e.g. CAf, NAm, SEu, WOc)
    prefixes = target_names.get("_prefixes", {})
    regions = target_names.get("_regions", {})
    if len(code) >= 3 and code[0] in prefixes:
        base = code[1:]
        if base in regions:
            region_name = regions[base].split("(")[0].strip()
            return f"{prefixes[code[0]]} {region_name}"
    # Might be a country code
    if code in country_names:
        return country_names[code]
    return code


def load_language_names():
    """Parse README Section I language codes → {code: name}."""
    names = {}
    try:
        with open(README_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return names

    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("I) Language codes") or stripped.startswith("I)   Language codes"):
            in_section = True
            continue
        if stripped.startswith("II) Country codes"):
            break
        if not in_section:
            continue
        if not stripped or stripped.startswith("Numbers") or stripped.startswith("On the right") or stripped.startswith("For more"):
            continue
        # Format: CODE  Name (details)  [iso]
        # or: CODE  Name: details  [iso]
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            continue
        code = parts[0]
        rest = parts[1]
        # Extract name: take text before first parenthesis, colon-with-space, or bracket
        match = re.match(r'([^(:\[]+)', rest)
        if match:
            name = match.group(1).strip().rstrip("/").strip()
            if name:
                names[code] = name
    return names


def haversine(lat1, lon1, lat2, lon2):
    """Return distance in km between two points."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def bearing(lat1, lon1, lat2, lon2):
    """Return initial bearing in degrees from point 1 to point 2."""
    dlon = radians(lon2 - lon1)
    x = sin(dlon) * cos(radians(lat2))
    y = cos(radians(lat1)) * sin(radians(lat2)) - sin(radians(lat1)) * cos(radians(lat2)) * cos(dlon)
    return (degrees(atan2(x, y)) + 360) % 360


def compass_label(deg):
    """Convert bearing degrees to 8-point compass label."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(deg / 45) % 8
    return dirs[idx]


def load_config():
    """Load QTH config from swlconfig.conf (first [qth*] section)."""
    all_qth = load_all_qth()
    return all_qth[0] if all_qth else {"lat": 0.0, "lon": 0.0, "name": "Unknown QTH"}


def load_all_qth():
    """Load all QTH entries from swlconfig.conf.

    Supports [qth] and [qth:label] sections.
    Returns list of dicts with lat, lon, name keys.
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    qth_list = []
    for section in config.sections():
        if section == "qth" or section.startswith("qth:"):
            try:
                qth_list.append({
                    "lat": float(config[section]["lat"]),
                    "lon": float(config[section]["lon"]),
                    "name": config[section]["name"],
                })
            except (KeyError, ValueError):
                continue
    if not qth_list:
        qth_list.append({"lat": 0.0, "lon": 0.0, "name": "Unknown QTH"})
    return qth_list


def load_sites():
    """Load transmitter sites JSON into a dict keyed by (country, site_code)."""
    sites = {}
    try:
        with open(SITES_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            key = (entry["country"], entry["site_code"])
            sites[key] = entry
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return sites


def load_schedule():
    """Load the schedule CSV into a list of row dicts."""
    rows = []
    try:
        with open(SKED_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            next(reader, None)  # skip header
            for row in reader:
                if len(row) < 7:
                    continue
                rows.append({
                    "freq": row[0].strip(),
                    "time": row[1].strip(),
                    "days": row[2].strip(),
                    "itu": row[3].strip(),
                    "station": row[4].strip(),
                    "lng": row[5].strip(),
                    "target": row[6].strip(),
                    "site_code": row[7].strip() if len(row) > 7 else "",
                })
    except FileNotFoundError:
        pass
    return rows


def resolve_site_info(row, sites_index):
    """Resolve transmitter site details. Returns dict with name, country, lat, lon or None."""
    country = row["itu"]
    site_code = row["site_code"]

    if site_code.startswith("/"):
        part = site_code[1:]
        if "-" in part:
            country, site_code = part.split("-", 1)
        else:
            country = part
            site_code = ""

    key = (country, site_code)
    if key in sites_index:
        s = sites_index[key]
        return {"name": s.get("name", ""), "country": country, "lat": s["lat"], "lon": s["lon"]}

    key_default = (country, "")
    if key_default in sites_index:
        s = sites_index[key_default]
        return {"name": s.get("name", ""), "country": country, "lat": s["lat"], "lon": s["lon"]}

    # Last resort: pick the first site for this country
    for (c, _sc), s in sites_index.items():
        if c == country:
            return {"name": s.get("name", ""), "country": country, "lat": s["lat"], "lon": s["lon"]}

    return None


class SWLDataTable(DataTable):
    """DataTable with enter binding visible in footer."""
    BINDINGS = [
        ("enter", "select_cursor", "Detail"),
    ]


DETAIL_CSS = """
#detail-container {
    align: center middle;
    width: 100%;
    height: 100%;
    background: black 50%;
}

#detail-card {
    width: 64;
    height: auto;
    max-height: 90%;
    border: round #769ff0;
    background: black;
    color: #a9b1d6;
    padding: 1 2;
}

#detail-title {
    text-style: bold;
    text-align: center;
    width: 100%;
    margin-bottom: 1;
}

#detail-body {
    width: 100%;
}

#detail-hint {
    text-align: center;
    width: 100%;
    margin-top: 1;
    color: $text-muted;
}
"""


class DetailScreen(ModalScreen):
    CSS = DETAIL_CSS
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("enter", "dismiss", "Close"),
    ]

    def __init__(self, detail_text: str):
        super().__init__()
        self.detail_text = detail_text

    def compose(self):
        with Container(id="detail-container"):
            with Container(id="detail-card"):
                yield Static("Station Detail", id="detail-title")
                yield Static(self.detail_text, id="detail-body")
                yield Static("Press Escape to close", id="detail-hint")


CSS = """
Screen {
    layout: vertical;
    background: black;
}

#title-bar {
    dock: top;
    height: 1;
    background: black;
    color: #a3aed2;
    text-style: bold;
    padding: 0 1;
}

#input-bar {
    dock: top;
    height: 2;
    background: black;
    padding: 0 1;
    align: center top;
}

#freq-prompt {
    width: 28;
    height: 2;
}

#station-prompt {
    width: 36;
    height: 2;
    margin-left: 1;
}

#update-prompt {
    width: 22;
    height: 2;
    margin-left: 1;
}

#qth-prompt {
    width: 28;
    height: 2;
    margin-left: 1;
}

.prompt-char {
    width: 4;
    height: 1;
}

#input-bar Input {
    height: 1;
    background: black;
    color: #769ff0;
    border: none;
}

#input-bar Input.-placeholder {
    color: #a3aed2 50%;
}

#input-bar Input:focus {
    border: none;
}

#schedule-table {
    height: 1fr;
    background: black;
    border-top: solid #394260;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: black;
    color: #a3aed2;
    padding: 0 1;
}

#update-log {
    display: none;
    height: 10;
    border-top: solid $primary;
    overflow-y: auto;
}

#update-log.visible {
    display: block;
}
"""


class SWLApp(App):
    TITLE = f"SWL Schedule Tool v{__version__}"
    CSS = CSS
    theme = "tokyo-night"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("m", "show_map", "Map"),
        ("t", "tune_radio", "Tune"),
        ("slash", "focus_search", "Search"),
        ("tab", "focus_next", "Next"),
        ("shift+tab", "focus_previous", "Prev"),
        ("f5", "update_schedules", "Update Sked"),
    ]

    utc_display = reactive("--:-- UTC")

    def __init__(self, radio_host="localhost", radio_port=4532):
        super().__init__()
        self.qth_list = load_all_qth()
        self.qth_index = 0
        self.qth = self.qth_list[0]
        self.sites_index = load_sites()
        self.schedule = load_schedule()
        self.country_names = load_country_names()
        self.target_names = load_target_names()
        self.language_names = load_language_names()
        self.displayed_rows = []
        self.radio_host = radio_host
        self.radio_port = radio_port

    FREQ_LABEL = (
        "[#769ff0 on #394260]╭─[/]"
        "[#a3aed2]░▒▓[/]"
        "[#090c0c on #a3aed2]  Frequency [/]"
        "[#a3aed2 on black]\ue0b0[/]"
    )
    STATION_LABEL = (
        "[#769ff0 on #394260]╭─[/]"
        "[#a3aed2]░▒▓[/]"
        "[#090c0c on #a3aed2]  Station [/]"
        "[#a3aed2 on black]\ue0b0[/]"
    )
    UPDATE_LABEL = (
        "[#769ff0 on #394260]╭─[/]"
        "[#a3aed2]░▒▓[/]"
        "[#090c0c on #a3aed2]  Update [/]"
        "[#a3aed2 on black]\ue0b0[/]"
    )
    QTH_LABEL = (
        "[#769ff0 on #394260]╭─[/]"
        "[#a3aed2]░▒▓[/]"
        "[#090c0c on #a3aed2] 󰍎 QTH [/]"
        "[#a3aed2 on black]\ue0b0[/]"
    )

    def compose(self):
        yield Static(id="title-bar")
        with Horizontal(id="input-bar"):
            with Vertical(id="freq-prompt"):
                yield Static(self.FREQ_LABEL)
                with Horizontal():
                    yield Static("[#769ff0 on #394260]╰─\uf10c[/]", classes="prompt-char")
                    yield Input(placeholder="kHz", id="freq-input")
            with Vertical(id="station-prompt"):
                yield Static(self.STATION_LABEL)
                with Horizontal():
                    yield Static("[#769ff0 on #394260]╰─\uf10c[/]", classes="prompt-char")
                    yield Input(placeholder="Station name", id="station-input")
            with Vertical(id="update-prompt"):
                yield Static(self.UPDATE_LABEL)
                with Horizontal():
                    yield Static("[#769ff0 on #394260]╰─\uf10c[/]", classes="prompt-char")
                    yield Input(placeholder="b25", id="period-input")
            with Vertical(id="qth-prompt"):
                yield Static(self.QTH_LABEL)
                with Horizontal():
                    yield Static("[#769ff0 on #394260]╰─\uf10c[/]", classes="prompt-char")
                    yield Input(placeholder=self.qth["name"], id="qth-input")
        yield SWLDataTable(id="schedule-table")
        yield RichLog(id="update-log", highlight=True, markup=True)
        yield Static(id="status-bar", markup=True)
        yield Footer()

    def on_mount(self):
        try:
            fd = os.open("/dev/tty", os.O_WRONLY)
            os.write(fd, f"\033]0;SWL Schedule Tool v{__version__}\007".encode())
            os.close(fd)
        except OSError:
            pass
        self._setup_table()
        self._update_title()
        self._update_status()
        self.set_interval(1, self._tick)

    def _setup_table(self):
        table = self.query_one("#schedule-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "kHz", "UTC", "Pays", "Site", "Station", "Lng", "Cible",
            "Dur.", "Dist. (km)", "Bearing", "Status"
        )

    def _tick(self):
        now = datetime.now(timezone.utc)
        self.utc_display = now.strftime("%H:%M:%S UTC")
        self._update_title()

    def _update_title(self):
        bar = self.query_one("#title-bar", Static)
        bar.update(
            f"  SWL Schedule Tool v{__version__}     ⏰ {self.utc_display}    📍 {self.qth['name']}"
        )

    def _update_status(self):
        bar = self.query_one("#status-bar", Static)
        bar.update(
            f"  {len(self.sites_index)} sites loaded  |  {len(self.schedule)} schedules  |  [#aaaaaa]→ NEXT time[/#aaaaaa]"
        )

    def check_action(self, action, parameters):
        """Prevent quit/search bindings from firing while typing in the input."""
        if action in ("quit", "focus_search", "tune_radio") and isinstance(self.focused, Input):
            return None
        return True

    def action_focus_search(self):
        """Focus the frequency input field."""
        self.query_one("#freq-input", Input).focus()

    def on_input_changed(self, event):
        if event.input.id == "freq-input":
            station = self.query_one("#station-input", Input)
            with station.prevent(Input.Changed):
                station.value = ""
        elif event.input.id == "station-input":
            freq = self.query_one("#freq-input", Input)
            with freq.prevent(Input.Changed):
                freq.value = ""

    def on_input_submitted(self, event):
        if event.input.id in ("freq-input", "station-input"):
            self._do_search()
        elif event.input.id == "period-input":
            self._run_update()
        elif event.input.id == "qth-input":
            self._select_qth()

    def _do_search(self):
        freq_input = self.query_one("#freq-input", Input)
        station_input = self.query_one("#station-input", Input)
        freq = freq_input.value.strip()
        station_query = station_input.value.strip().lower()

        if not freq and not station_query:
            return

        table = self.query_one("#schedule-table", DataTable)
        table.clear()
        self.displayed_rows = []

        now = datetime.now(timezone.utc)
        current_time = int(now.strftime("%H%M"))
        qth_lat, qth_lon = self.qth["lat"], self.qth["lon"]

        results = []

        for row in self.schedule:
            if freq and row["freq"] != freq:
                continue
            if station_query and station_query not in row["station"].lower():
                continue

            dur_str, is_active, status, sort_minutes = compute_on_air(row["time"], current_time)

            # Resolve transmitter site
            site_info = resolve_site_info(row, self.sites_index)
            if site_info:
                dist = haversine(qth_lat, qth_lon, site_info["lat"], site_info["lon"])
                brg = bearing(qth_lat, qth_lon, site_info["lat"], site_info["lon"])
                dist_str = f"{dist:.0f}"
                brg_str = f"{brg:03.0f}° {compass_label(brg)}"
            else:
                dist_str = "—"
                brg_str = "—"

            # Site display
            site_display = row["site_code"] if row["site_code"] else f"/{row['itu']}"

            results.append((row, dur_str, is_active, status, site_info,
                            dist_str, brg_str, site_display, sort_minutes))

        # Sort: on-air first (by remaining asc), then next (by until asc), unparseable last
        results.sort(key=lambda r: (0 if r[2] else (2 if r[8] == 9999 else 1), r[8]))

        for row, dur_str, is_active, status, site_info, dist_str, brg_str, site_display, _ in results:
            row_data = {
                **row,
                "dur_str": dur_str,
                "is_active": is_active,
                "status": status,
                "site_info": site_info,
                "dist_str": dist_str,
                "brg_str": brg_str,
            }
            row_index = len(self.displayed_rows)
            self.displayed_rows.append(row_data)

            cells = [
                row["freq"], row["time"], row["itu"], site_display,
                row["station"], row["lng"], row["target"],
                dur_str, dist_str, brg_str, status,
            ]

            if is_active:
                cells = [Text(str(c), style="bold green") for c in cells]
            else:
                cells = [Text(str(c), style="#aaaaaa") for c in cells]

            table.add_row(*cells, key=str(row_index))

        # Auto-fill the other search field with first result
        if results:
            first = results[0][0]
            if freq and not station_query:
                with station_input.prevent(Input.Changed):
                    station_input.value = first["station"]
            elif station_query and not freq:
                with freq_input.prevent(Input.Changed):
                    freq_input.value = first["freq"]

        # Move focus to table so arrow keys navigate rows immediately
        if table.row_count > 0:
            table.focus()

    def _select_qth(self):
        """Select a QTH from the config. Empty input cycles to next; text filters by name."""
        qth_input = self.query_one("#qth-input", Input)
        query = qth_input.value.strip().lower()

        if not query:
            # Cycle to next QTH
            self.qth_index = (self.qth_index + 1) % len(self.qth_list)
        else:
            # Find matching QTH by substring
            for i, q in enumerate(self.qth_list):
                if query in q["name"].lower():
                    self.qth_index = i
                    break
            else:
                self.bell()
                return

        self.qth = self.qth_list[self.qth_index]
        qth_input.placeholder = self.qth["name"]
        qth_input.value = ""
        self._update_title()

        # Re-run search if results are displayed to update distances/bearings
        if self.displayed_rows:
            self._do_search()

    def on_data_table_row_selected(self, event):
        try:
            idx = int(str(event.row_key.value))
        except (ValueError, TypeError):
            return
        if idx < 0 or idx >= len(self.displayed_rows):
            return
        rd = self.displayed_rows[idx]

        # Build detail text
        LABEL_W = 15  # width of "  Label:     " prefix
        MAX_W = 56    # usable width inside card (64 - 4 padding - 4 border)
        VAL_W = MAX_W - LABEL_W

        def field(label, value):
            """Format a label: value line, wrapping long values onto continuation lines."""
            prefix = f"  {label + ':':<{LABEL_W - 2}}"
            if len(value) <= VAL_W:
                return prefix + value
            # Word-wrap the value, aligning continuation lines under the value column
            words = value.split()
            result_lines = []
            current = ""
            for word in words:
                if current and len(current) + 1 + len(word) > VAL_W:
                    result_lines.append(current)
                    current = word
                else:
                    current = f"{current} {word}" if current else word
            if current:
                result_lines.append(current)
            indent = " " * LABEL_W
            return prefix + result_lines[0] + "".join(
                f"\n{indent}{ln}" for ln in result_lines[1:]
            )

        lines = []
        lines.append(field("Frequency", f"{rd['freq']} kHz"))
        lines.append(field("Station", rd['station']))
        lines.append(field("Schedule", f"{rd['time']} UTC  (Dur. {rd['dur_str']})"))
        if rd['days']:
            lines.append(field("Days", rd['days']))
        lines.append(field("Status", rd['status'] if rd['status'] else "—"))
        lines.append("")

        # Country
        country_name = self.country_names.get(rd['itu'], rd['itu'])
        lines.append(field("Country", f"{country_name} ({rd['itu']})"))

        # Transmitter site
        si = rd['site_info']
        if si:
            tx_country_name = self.country_names.get(si['country'], si['country'])
            site_name = si['name'] if si['name'] else "Unknown"
            lat, lon = si['lat'], si['lon']
            lat_str = f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}"
            lon_str = f"{abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"
            if si['country'] != rd['itu']:
                tx_val = f"{site_name}, {tx_country_name} ({lat_str}, {lon_str})"
            else:
                tx_val = f"{site_name} ({lat_str}, {lon_str})"
            lines.append(field("Tx Site", tx_val))
        else:
            lines.append(field("Tx Site", "—"))

        lines.append(field("Distance", f"{rd['dist_str']} km" if rd['dist_str'] != "—" else "—"))
        lines.append(field("Bearing", rd['brg_str']))
        lines.append("")

        # Language
        lng_name = self.language_names.get(rd['lng'], rd['lng'])
        lines.append(field("Language", f"{lng_name} ({rd['lng']})" if rd['lng'] else "—"))

        # Target
        target_name = resolve_target_name(rd['target'], self.target_names, self.country_names)
        lines.append(field("Target", f"{target_name} ({rd['target']})" if rd['target'] else "—"))

        self.push_screen(DetailScreen("\n".join(lines)))

    FIFO_PATH = "/tmp/azmap-target.fifo"

    def action_show_map(self):
        """Send target to running azMap via FIFO, or launch a new instance."""
        table = self.query_one(DataTable)
        if not table.row_count or table.cursor_row is None:
            self.bell()
            return
        try:
            row_key = table.coordinate_to_cell_key(
                (table.cursor_row, 0)).row_key
            idx = int(str(row_key.value))
        except (ValueError, TypeError):
            self.bell()
            return
        if idx < 0 or idx >= len(self.displayed_rows):
            self.bell()
            return
        rd = self.displayed_rows[idx]
        si = rd.get("site_info")
        if not si or si.get("lat") is None or si.get("lon") is None:
            self.bell()
            return
        target_name = f"{rd['station']} ({rd['freq']} kHz)"
        site_name = si.get("name", "") if si else ""
        detail = f"{rd['station']}|{rd['freq']} kHz|{rd['itu']}|{site_name}|{rd['lng']}|{rd['target']}"
        fifo_line = f"{si['lat']},{si['lon']},{target_name}|{detail}\n"

        # Try sending to existing azMap via FIFO
        try:
            fd = os.open(self.FIFO_PATH, os.O_WRONLY | os.O_NONBLOCK)
            try:
                data = fifo_line.encode("utf-8")
                written = os.write(fd, data)
                if written == len(data):
                    return  # azMap received the update
            finally:
                os.close(fd)
        except OSError:
            pass  # FIFO doesn't exist or no reader — launch new instance

        try:
            subprocess.Popen(
                ["azmap",
                 str(self.qth["lat"]), str(self.qth["lon"]),
                 str(si["lat"]), str(si["lon"]),
                 "-c", self.qth["name"], "-t", target_name,
                 "-d", detail],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self.bell()

    def action_tune_radio(self):
        """Send FA command to EladSpectrum CAT server to tune the radio."""
        table = self.query_one(DataTable)
        if not table.row_count or table.cursor_row is None:
            self.bell()
            return
        try:
            row_key = table.coordinate_to_cell_key(
                (table.cursor_row, 0)).row_key
            idx = int(str(row_key.value))
        except (ValueError, TypeError):
            self.bell()
            return
        if idx < 0 or idx >= len(self.displayed_rows):
            self.bell()
            return
        rd = self.displayed_rows[idx]
        try:
            freq_hz = int(rd["freq"]) * 1000
        except (ValueError, TypeError):
            self.bell()
            return
        cmd = f"FA{freq_hz:011d};MD5;"
        try:
            with socket.create_connection(
                (self.radio_host, self.radio_port), timeout=2
            ) as sock:
                sock.sendall(cmd.encode("ascii"))
        except OSError:
            self.bell()
            return

        # If azMap is already running, update the map target
        try:
            fd = os.open(self.FIFO_PATH, os.O_WRONLY | os.O_NONBLOCK)
            os.close(fd)
        except OSError:
            return  # azMap not running, just tune
        self.action_show_map()

    @work(thread=True)
    def _run_update(self):
        log = self.query_one("#update-log", RichLog)
        period = self.query_one("#period-input", Input).value.strip()

        if not re.match(r'^[ab]\d{2}$', period):
            self.call_from_thread(log.add_class, "visible")
            self.call_from_thread(log.clear)
            self.call_from_thread(log.write, f"[bold red]Invalid period '{period}'. Use format: a25, b25, a26, etc.[/bold red]")
            return

        self.call_from_thread(log.add_class, "visible")
        self.call_from_thread(log.clear)
        self.call_from_thread(log.write, f"[bold]Starting schedule update ({period})...[/bold]")

        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "eibi_swl.updatesked", period],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in iter(proc.stdout.readline, ""):
                self.call_from_thread(log.write, line.rstrip())
            proc.wait()

            if proc.returncode == 0:
                self.call_from_thread(log.write, "[bold green]Update complete. Reloading data...[/bold green]")
                sites = load_sites()
                schedule = load_schedule()
                self.call_from_thread(self._apply_reload, sites, schedule)
                self.call_from_thread(log.write, "[bold green]Data reloaded.[/bold green]")
            else:
                self.call_from_thread(log.write, f"[bold red]Update failed (exit code {proc.returncode})[/bold red]")
        except Exception as e:
            self.call_from_thread(log.write, f"[bold red]Error: {e}[/bold red]")

    def _apply_reload(self, sites, schedule):
        self.sites_index = sites
        self.schedule = schedule
        self._update_status()

    def action_update_schedules(self):
        self._run_update()


def _save_radio_config(host, port):
    """Save radio host/port to config file, preserving comments."""
    lines = []
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            lines = f.readlines()

    # Check if [radio] section already exists
    radio_idx = None
    next_section_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "[radio]":
            radio_idx = i
        elif radio_idx is not None and stripped.startswith("[") and stripped.endswith("]"):
            next_section_idx = i
            break

    radio_lines = [
        "[radio]\n",
        f"host = {host}\n",
        f"port = {port}\n",
    ]

    if radio_idx is not None:
        # Replace existing [radio] section
        end = next_section_idx if next_section_idx is not None else len(lines)
        lines[radio_idx:end] = radio_lines + ["\n"]
    else:
        # Append new section
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append("\n")
        lines.extend(radio_lines)

    with open(CONFIG_FILE, "w") as f:
        f.writelines(lines)


def main():
    parser = argparse.ArgumentParser(description="SWL - Shortwave Listener Dashboard")
    parser.add_argument("--host", default=None, help="Radio CAT server host (default: from config)")
    parser.add_argument("--cat-port", type=int, default=None, help="Radio CAT server port (default: from config)")
    parser.add_argument("--version", action="version", version=f"eibi-swl {__version__}")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    host = args.host or config.get("radio", "host", fallback="localhost")
    port = args.cat_port or config.getint("radio", "port", fallback=4532)

    if args.host or args.cat_port:
        _save_radio_config(host, port)

    app = SWLApp(radio_host=host, radio_port=port)
    app.run()


if __name__ == "__main__":
    main()
