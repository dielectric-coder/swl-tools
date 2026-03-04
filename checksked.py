#!/usr/bin/env python3

import sys
import os
import csv
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

def main():
    # Configuration
    script_dir = os.path.dirname(os.path.abspath(__file__))
    SCHED_DIR = os.path.join(script_dir, "swl-schedules-data")

    try:
        term_width = max(os.get_terminal_size().columns, 110)
    except OSError:
        term_width = 110
    console = Console(width=term_width)

    # Check if frequency argument is provided
    if len(sys.argv) < 2:
        console.print("Usage: checksked.py <frequency_in_kHz>", style="red")
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
        with open(csv_file, 'r', encoding='latin-1') as f:
            reader = csv.reader(f, delimiter=';')
            for row in reader:
                # Check if frequency matches exactly (compare first column)
                if len(row) > 0 and row[0].strip() == frequency:
                    # Extract fields (adjust indices based on CSV structure)
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

                    # Calculate duration and check if currently broadcasting
                    duration = 0
                    is_active = False
                    remaining_time = 0

                    if '-' in time_range:
                        try:
                            start, end = time_range.split('-')
                            start_time = int(start)
                            end_time = int(end)
                            duration = end_time - start_time

                            # Handle broadcasts that cross midnight
                            if duration < 0:
                                duration += 2400
                                # For broadcasts crossing midnight, check if current time is after start OR before end
                                is_active = (current_time >= start_time) or (current_time < end_time)

                                # Calculate remaining time for midnight-crossing broadcasts
                                if is_active:
                                    if current_time >= start_time:
                                        # We're in the part after midnight crossing
                                        remaining_time = (2400 - current_time) + end_time
                                    else:
                                        # We're in the part before midnight (early morning)
                                        remaining_time = end_time - current_time
                            else:
                                # Normal broadcast within same day
                                is_active = (start_time <= current_time < end_time)

                                # Calculate remaining time for normal broadcasts
                                if is_active:
                                    # Convert times to total minutes for accurate calculation
                                    current_hours = current_time // 100
                                    current_mins = current_time % 100
                                    end_hours = end_time // 100
                                    end_mins = end_time % 100

                                    current_total_mins = current_hours * 60 + current_mins
                                    end_total_mins = end_hours * 60 + end_mins

                                    remaining_mins = end_total_mins - current_total_mins

                                    # Convert back to HHMM format
                                    remaining_time = (remaining_mins // 60) * 100 + (remaining_mins % 60)

                        except (ValueError, IndexError):
                            duration = 0

                    # Build status and row style
                    if is_active:
                        has_active_station = True
                        hours = remaining_time // 100
                        minutes = remaining_time % 100
                        status = f"◄ ON AIR {hours:02d}h{minutes:02d}"
                        row_style = "bold green"
                    else:
                        status = ""
                        row_style = None

                    table.add_row(
                        freq, time_range, country, site, station,
                        language, target, f"{duration:04d}", status,
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
