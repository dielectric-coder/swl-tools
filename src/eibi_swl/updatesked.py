#!/usr/bin/env python3

import sys
import os
import subprocess
import urllib.request
import re
import json

from eibi_swl._paths import resolve_data_dir

def parse_dms_coord(coord_str):
    """Parse a single coordinate component like '34N32' or '26S07\\'40\"' to decimal degrees."""
    match = re.match(r"(\d+)([NSEW])(\d+)(?:'(\d+)(?:\")?)?", coord_str)
    if not match:
        return None
    degrees = int(match.group(1))
    direction = match.group(2)
    minutes = int(match.group(3))
    seconds = int(match.group(4)) if match.group(4) else 0
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if direction in ('S', 'W'):
        decimal = -decimal
    return round(decimal, 4)


# Regex to find coordinate pairs at end of line
# Matches patterns like: 34N32-69E20  or  26S07'40"-28E12'20"
COORD_PAIR_RE = re.compile(
    r'(\d+[NS]\d+(?:\'\d+\"?)?)\s*-\s*(\d+[EW]\d+(?:\'\d+\"?)?)'
)


def extract_transmitter_sites(readme_path, output_path):
    """Extract transmitter sites and coordinates from EiBi README and write JSON."""
    with open(readme_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find section IV start
    section_start = None
    for i, line in enumerate(lines):
        if 'IV)' in line and 'ransmitter' in line:
            section_start = i
            break

    if section_start is None:
        print("Warning: Could not find transmitter site section in README")
        return

    sites = []
    current_country = None

    # Skip preamble lines until first country entry
    for line in lines[section_start:]:
        stripped = line.rstrip()

        # Country header line: "   XXX: ..."
        country_match = re.match(r'^   ([A-Z][A-Za-z0-9 ]{0,4}):\s*(.*)', stripped)
        if country_match:
            current_country = country_match.group(1).strip()
            rest = country_match.group(2).strip()
            if rest:
                _parse_site_entry(sites, current_country, rest)
            continue

        # Continuation line: "        code-Name coords"
        cont_match = re.match(r'^        \s*(.*)', stripped)
        if cont_match and current_country:
            rest = cont_match.group(1).strip()
            if rest:
                _parse_site_entry(sites, current_country, rest)

    # Write JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sites, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(sites)} transmitter sites to {os.path.basename(output_path)}")


def _parse_site_entry(sites, country, text):
    """Parse a single site entry and append to sites list."""
    # Strip trailing "except:" marker
    text = re.sub(r'\s+except:\s*$', '', text)

    # Skip entries with no coordinates
    if not COORD_PAIR_RE.search(text):
        return

    # Try to extract site code prefix (e.g., "k-Kabul...", "ct-Cape Town...")
    site_code_match = re.match(r'^([a-zA-Z0-9]+)-(.*)$', text)
    if site_code_match:
        site_code = site_code_match.group(1)
        rest = site_code_match.group(2)
    else:
        site_code = ""
        rest = text

    # Find all coordinate pairs
    coord_matches = list(COORD_PAIR_RE.finditer(rest))
    if not coord_matches:
        return

    # For multi-coordinate lines (e.g., "Aero sites: A coords and B coords")
    if len(coord_matches) > 1 and ' and ' in rest:
        _parse_multi_site(sites, country, site_code, rest, coord_matches)
    else:
        name_part = rest[:coord_matches[0].start()].strip()
        lat = parse_dms_coord(coord_matches[0].group(1))
        lon = parse_dms_coord(coord_matches[0].group(2))
        if lat is not None and lon is not None:
            sites.append({
                "country": country,
                "site_code": site_code,
                "name": name_part,
                "lat": lat,
                "lon": lon
            })


def _parse_multi_site(sites, country, site_code, rest, coord_matches):
    """Parse lines with multiple sites separated by 'and'."""
    # Split on ' and ' and pair with coordinates
    parts = re.split(r'\s+and\s+', rest)
    for part in parts:
        cm = COORD_PAIR_RE.search(part)
        if cm:
            name_part = part[:cm.start()].strip()
            lat = parse_dms_coord(cm.group(1))
            lon = parse_dms_coord(cm.group(2))
            if lat is not None and lon is not None:
                sites.append({
                    "country": country,
                    "site_code": site_code,
                    "name": name_part,
                    "lat": lat,
                    "lon": lon
                })


def main():
    # Configuration
    SCHED_DIR = resolve_data_dir()
    BASE_URL = "https://eibispace.de/dx"
    
    # Create schedule directory if it doesn't exist
    os.makedirs(SCHED_DIR, exist_ok=True)
    
    # Check if schedule period argument is provided
    if len(sys.argv) < 2:
        print("Usage: updatesked <schedule_period>")
        print("Example: updatesked.py a25 or b25")
        print("Format: lowercase 'a' or 'b' followed by 2 digits")
        sys.exit(1)
    
    period = sys.argv[1]
    
    # Validate period format: must be 'a' or 'b' followed by exactly 2 digits
    if not re.match(r'^[ab]\d{2}$', period):
        print("Error: Invalid schedule period format!")
        print("Period must be lowercase 'a' or 'b' followed by 2 digits")
        print("Examples: a25, b25, a24, b24")
        sys.exit(1)
    
    print()
    print(f"updating schedule {period}")
    print(f"Data directory: {SCHED_DIR}")
    print()
    
    # List of files to download and convert
    files_to_process = [
        (f"sked-{period}.csv", "sked-current.csv"),
        (f"freq-{period}.txt", "freq-current.dat"),
        (f"bc-{period}.txt", "bc-current.dat"),
    ]
    
    # Download and convert each file
    for source_file, target_file in files_to_process:
        source_path = os.path.join(SCHED_DIR, source_file)
        target_path = os.path.join(SCHED_DIR, target_file)
        url = f"{BASE_URL}/{source_file}"
        
        # Remove old file if exists
        if os.path.exists(source_path):
            os.remove(source_path)
        
        # Download file
        try:
            print(f"Downloading {source_file}...")
            urllib.request.urlretrieve(url, source_path)
            
            # Convert encoding from ISO-8859-1 to UTF-8
            print(f"Converting {source_file} to UTF-8...")
            with open(source_path, 'r', encoding='iso-8859-1') as f_in:
                content = f_in.read()
            with open(target_path, 'w', encoding='utf-8') as f_out:
                f_out.write(content)
                
        except Exception as e:
            print(f"Error processing {source_file}: {e}")
    
    # Download and convert README
    readme_source_name = "README.TXT"
    readme_source_path = os.path.join(SCHED_DIR, readme_source_name)
    readme_target_path = os.path.join(SCHED_DIR, "README-current.TXT")
    readme_url = f"{BASE_URL}/{readme_source_name}"

    try:
        print(f"Downloading {readme_source_name}...")
        urllib.request.urlretrieve(readme_url, readme_source_path)

        print(f"Converting {readme_source_name} to UTF-8...")
        with open(readme_source_path, 'r', encoding='iso-8859-1') as f_in:
            content = f_in.read()
        with open(readme_target_path, 'w', encoding='utf-8') as f_out:
            f_out.write(content)

    except Exception as e:
        print(f"Error processing {readme_source_name}: {e}")

    # Extract transmitter sites to JSON
    sites_json = os.path.join(SCHED_DIR, "transmitter-sites.json")
    try:
        extract_transmitter_sites(readme_target_path, sites_json)
    except Exception as e:
        print(f"Error extracting transmitter sites: {e}")

    # Display completion message
    try:
        # Try to use cowsay and lolcat if available
        cowsay_process = subprocess.Popen(['cowsay', 'All done!'], 
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)
        subprocess.run(['lolcat'], 
                      stdin=cowsay_process.stdout,
                      stderr=subprocess.DEVNULL)
        cowsay_process.wait()
    except FileNotFoundError:
        # Fallback if cowsay/lolcat not available
        print("\n✓ All done!")
    
if __name__ == "__main__":
    main()