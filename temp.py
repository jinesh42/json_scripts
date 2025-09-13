from pathlib import Path
import re
import json
from jsonpath_ng import parse
import pandas as pd

def get_paths(d, prefix=""):
    """Recursively yield JSONPath-like paths from JSON data."""
    if isinstance(d, dict):
        for key, value in d.items():
            new_prefix = f"{prefix}.{key}" if prefix else f".{key}"
            yield new_prefix
            yield from get_paths(value, new_prefix)
    elif isinstance(d, list):
        for i, value in enumerate(d):
            new_prefix = f"{prefix}[{i}]"
            yield new_prefix
            yield from get_paths(value, new_prefix)

def find_best_match_segments(keyword_segments, all_paths):
    """
    Finds the JSON path with the highest number of matching leading segments
    compared to the keyword's segments.
    """
    best_match = None
    best_score = 0
    for path in all_paths:
        path_segments = [p for p in path.strip('.').split('.') if p]
        # Compare from the end/back: because 'position.x' should match 'system.location.position.y'
        score = 0
        # Match from the beginning of keyword segments
        for seg in keyword_segments[:-1]:  # ignore last for parent search
            if seg in path_segments:
                score += 1
        if score > best_score:
            best_score = score
            best_match = path
    return best_match, best_score

def set_value_in_path(json_obj, path_list, value):
    """
    Create intermediate keys if missing and set value at final key.
    path_list is ['system', 'location', 'position', 'x']
    """
    for key in path_list[:-1]:
        print(f"Setting up path: {key}")
        if key not in json_obj or not isinstance(json_obj[key], dict):
            json_obj[key] = {}
        json_obj = json_obj[key]
        print(f"Current JSON object: {json_obj}")
    json_obj[path_list[-1]] = value

search_root = Path("E:/temp_projects/json_values_checker/devices/")
target_filename = "metadata.json"
input_file_path = 'input.xlsx'

df = pd.read_excel(input_file_path, sheet_name='Main', engine='openpyxl').fillna("")
columns = [col for col in df.columns if col != 'Devices']

for idx, row in df.iterrows():
    device = str(row['Devices']).strip()
    print(f"Processing device: {device}")
    if not device:
        print("❌ Device name is empty, skipping.")
        continue
    root_dir = search_root / device
    matched_files = list(root_dir.rglob(target_filename))

    if not matched_files:
        print(f"No matching files found for device: {device}")
        continue

    for file in matched_files:
        with file.open("r", encoding="utf-8") as f:
            json_data = json.load(f)

        paths = list(get_paths(json_data))

        for keyword in columns:
            excel_value = str(row[keyword])
            keyword_segments = keyword.split('.')

            # Try full path match first
            exact_matches = [p for p in paths if p.lower().endswith("." + keyword.lower())]
            if exact_matches:
                path_expr = parse("$" + exact_matches[0])
                path_expr.update(json_data, excel_value)
                print(f"Updated existing: {keyword} → {excel_value}")
                continue

            # Find best parent match
            best_parent, score = find_best_match_segments(keyword_segments, paths)
            if best_parent and score > 0:
                # Convert path string to list of keys
                parent_segments = best_parent.strip('.').split('.')
                path_list = parent_segments + [keyword_segments[-1]]
                set_value_in_path(json_data, path_list, excel_value)
                print(f"Added missing key via parent match: {'.'.join(path_list)} → {excel_value}")
            else:
                print(f"No suitable match found for '{keyword}', skipped.")

        # Save updates
        with file.open("w", encoding="utf-8") as fw:
            json.dump(json_data, fw, indent=2)
