from pathlib import Path
import re
import os
import json
from jsonpath_ng import parse
import pandas as pd

# CONFIGURATION
search_root = Path("E:/temp_projects/json_values_checker/devices/")
target_filename = "metadata.json"
#unit_rules_file = Path("E:/temp_projects/json_values_checker/keyword.json")
output_file = Path("E:/temp_projects/json_values_checker/changes_check_report.txt")

input_file_path = 'input.xlsx'  # or the full path if needed


def read_input_convert(file_path):
    """Load expected units from a JSON file."""
    if os.path.exists(file_path):
        df_input = pd.read_excel(file_path)
        return {row['Devices'].strip(): json.loads(row['Value']) for index, row in df_input.iterrows()}
        
    else:
        print(f"❌ Input  file not found: {file_path}")
        return {}

def get_paths(d):
    """Recursively yield JSONPath-like paths from JSON data."""
    if isinstance(d, dict):
        for key, value in d.items():
            yield f'.{key}'
            yield from (f'.{key}{p}' for p in get_paths(value))
    elif isinstance(d, list):
        for i, value in enumerate(d):
            yield f'[{i}]'
            yield from (f'[{i}]{p}' for p in get_paths(value))


def check_units(json_data, expected_units, auto_fix=False):
    """Check and optionally fix units for each key based on expected values."""
    stats = {}
    paths = ['$' + s for s in get_paths(json_data)]
    modified = False  # Flag to track if we modified the JSON

    for keyword, expected_unit in expected_units.items():

        
        matching_paths = [p for p in paths if re.search(keyword, p, re.IGNORECASE)]
        pass_count = 0
        fail_count = 0
        

        for path_str in matching_paths:
            path_expr = parse(path_str)
            matches = path_expr.find(json_data)
            #print(matches)

            for match in matches:
                print(f"Match found: {match.value}")
                if isinstance(match.value, dict):
                    unit = match.value.get('units', None)
                    if unit == expected_unit:
                        pass_count += 1
                    else:
                        fail_count += 1
                        if auto_fix:
                            match.value['units'] = expected_unit
                            modified = True

        stats[keyword] = {
            'expected_unit': expected_unit,
            'pass': pass_count,
            'fail': fail_count
        }

    return stats, modified


def generic_changes(root_dir, target_filename, value): 
    """Process JSON files in the specified directory and apply changes based on input values."""
    matched_files = list(root_dir.rglob(target_filename))
    if not matched_files:
        print("No matching files found.")
        return
    expected_units = value  # Assuming value is a dictionary with expected units
    auto_fix = True  # Set to True if you want to auto-fix the units



    report_lines = []

    for file_path in matched_files:
        report_lines.append(f"\n📄 Checking file: {file_path}")
        if file_path.is_file():
            content = file_path.read_text(encoding='utf-8')
            json_data = json.loads(content)

            file_stats, modified = check_units(json_data, expected_units, auto_fix)

            for key, result in file_stats.items():
                report_lines.append(f"🔍 Checking '{key}' (Expected: '{result['expected_unit']}'):")
                report_lines.append(f"   ✅ Passed: {result['pass']}")
                report_lines.append(f"   ❌ Failed: {result['fail']}")

            # Save changes if modified
            if auto_fix and modified:
                file_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
                report_lines.append("   ✏️ Units auto-corrected and file updated.")

    
    output_file.write_text('\n'.join(report_lines), encoding='utf-8')
    print(f"\n📝 Report saved to: {output_file}")

if __name__ == "__main__":
    input_data = read_input_convert(input_file_path)
    for device, value in input_data.items():
        root_dir = Path(str(search_root) + "\\" + device + "\\")
        generic_changes(root_dir, target_filename, value)

    
    print(f"\n📝 Report saved to: {output_file}")
        

