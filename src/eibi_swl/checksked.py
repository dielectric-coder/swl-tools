#!/usr/bin/env python3

import sys
import os
import csv
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from eibi_swl._paths import resolve_data_dir
from eibi_swl._schedule import compute_on_air

def main():
    # Configuration
    SCHED_DIR = resolve_data_dir()

    try:
        term_width = max(os.get_terminal_size().columns, 110)
    except OSError:
        term_width = 110
    console = Console(width=term_width)

    # Check if frequency argument is provided
    if len(sys.argv) < 2:
        console.print("Usage: checksked <frequency_in_kHz>", style="red")
        sys.exit(1)

    frequency = sys.argv[1]

    # Get current UTC time in HHMM format
    current_utc = datetime.now(timezone.utc)
    current_time = int(current_utc.strftime("%H%M"))

    # Clear screen and display header
    console.clear()
    console.print(Panel(
        f"[bold]{frequency} kHz[/bold]  —  {current_utc.strftime('%H:%M')} UTC",
        title="SWL Schedule Check",
        style="cyan"
    ))

    # Process the CSV file
    csv_file = os.path.join(SCHED_DIR, "sked-current.csv")

    # Track if any station is currently on air
    has_active_station = False

    # Build table
    table = Table(show_header=True, header_style="bold", box=box.SIMPLE_HEAVY,
                  pad_edge=False, padding=(0, 1))
    table.add_column("kHz", justify="right", no_wrap=True)
    table.add_column("UTC", no_wrap=True)
    table.add_column("Pays", no_wrap=True)
    table.add_column("Site", no_wrap=True)
    table.add_column("Station", no_wrap=True, max_width=20)
    table.add_column("Lng", no_wrap=True)
    table.add_column("Cible", no_wrap=True)
    table.add_column("Dur.", justify="right", no_wrap=True)
    table.add_column("Status", no_wrap=True)

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader, None)  # skip header
            for row in reader:
                # Check if frequency matches exactly (compare first column)
                if len(row) > 0 and row[0].strip() == frequency:
                    # Extract fields
                    freq = row[0] if len(row) > 0 else ""
                    time_range = row[1] if len(row) > 1 else ""
                    country = row[3] if len(row) > 3 else ""
                    station = row[4] if len(row) > 4 else ""
                    language = row[5] if len(row) > 5 else ""
                    target = row[6] if len(row) > 6 else ""
                    site = row[7] if len(row) > 7 else ""

                    # Use country code with '/' prefix if site is empty
                    if not site or site.strip() == "":
                        site = f"/{country}"

                    dur_str, is_active, status, _ = compute_on_air(time_range, current_time)

                    if is_active:
                        has_active_station = True
                        row_style = "bold green"
                    else:
                        status = ""
                        row_style = None

                    table.add_row(
                        freq, time_range, country, site, station,
                        language, target, dur_str, status,
                        style=row_style
                    )

        console.print(table)

        # Display message if no stations are currently on air
        if not has_active_station:
            console.print("\nAucune station n'émet actuellement sur cette fréquence.", style="yellow")

    except FileNotFoundError:
        console.print(f"Error: File not found: {csv_file}", style="red")
        sys.exit(1)
    except Exception as e:
        console.print(f"Error processing file: {e}", style="red")
        sys.exit(1)

if __name__ == "__main__":
    main()
