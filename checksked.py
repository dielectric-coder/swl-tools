#!/usr/bin/env python3

import sys
import os
import csv
from datetime import datetime, timezone

def main():
    # Configuration
    script_dir = os.path.dirname(os.path.abspath(__file__))
    SCHED_DIR = os.path.join(script_dir, "swl-schedules-data")
    
    # Check if frequency argument is provided
    if len(sys.argv) < 2:
        print("Usage: checksked.py <frequency_in_kHz>")
        sys.exit(1)
    
    frequency = sys.argv[1]
    
    # Get current UTC time in HHMM format
    current_utc = datetime.now(timezone.utc)
    current_time = int(current_utc.strftime("%H%M"))
    
    # Clear screen
    os.system('clear')
    
    # Display header
    print(f"Stations en onde à la fréquence {frequency} kHz en ce moment {current_utc.strftime('%H:%M')} UTC")
    #print(f"Pour l'heure UTC actuelle: {current_utc.strftime('%H:%M')}")
    print()
    
    # Process the CSV file
    csv_file = os.path.join(SCHED_DIR, "sked-current.csv")
    
    # ANSI color codes for highlighting
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    
    # Track if any station is currently on air
    has_active_station = False
    
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
                    
                    # Format output line
                    output_line = (f"{freq} kHz {time_range} UTC "
                                  f"Pays: {country:>3} "
                                  f"Site: {site:<6} "
                                  f"Station: {station:<24} "
                                  f"Langue: {language:<3} "
                                  f"Cible: {target:>4} "
                                  f"{duration:04d}")
                    
                    # Highlight if currently active with remaining time
                    if is_active:
                        has_active_station = True
                        # Convert remaining time to hours and minutes
                        hours = remaining_time // 100
                        minutes = remaining_time % 100
                        time_str = f"{hours:02d}h{minutes:02d}"
                        print(f"{GREEN}{output_line} ◄ ON AIR (reste: {time_str}){RESET}")
                    else:
                        print(output_line)
        
        # Display message if no stations are currently on air
        if not has_active_station:
            print()
            print(f"{YELLOW}Aucune station n'émet actuellement sur cette fréquence.{RESET}")
    
    except FileNotFoundError:
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()