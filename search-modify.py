from pathlib import Path
import re
import json
from jsonpath_ng import parse

# CONFIGURATION
search_root = Path("E:/temp_projects/json_values_checker/floor/")
target_filename = "metadata.json"
unit_rules_file = Path("E:/temp_projects/json_values_checker/keyword.json")
output_file = Path("E:/temp_projects/json_values_checker/unit_check_report.txt")

def load_expected_units(file_path):
    """Load expected units from a JSON file."""
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"❌ Unit rules file not found: {file_path}")
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

        
        matching_paths = [p for p in paths if re.search(rf"\.{re.escape(keyword)}$", p, re.IGNORECASE)]
        pass_count = 0
        fail_count = 0

        for path_str in matching_paths:
            path_expr = parse(path_str)
            matches = path_expr.find(json_data)

            for match in matches:
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

def search_and_check_files(root_dir: Path, expected_units, auto_fix=False, folder_pattern="*"):
    """
    Search for metadata.json files in folders matching the specified pattern.
    
    Args:
        root_dir (Path): Root directory to start search
        expected_units (dict): Dictionary of expected units
        auto_fix (bool): Whether to automatically fix unit mismatches
        folder_pattern (str): Pattern to match folder names (default: "EM-*")
    """
    # Find all matching folders first
    matching_folders = [f for f in root_dir.glob(folder_pattern) if f.is_dir()]
    
    if not matching_folders:
        print(f"No folders matching pattern '{folder_pattern}' found in {root_dir}")
        return

    report_lines = []
    report_lines.append(f"🔍 Searching in folders matching '{folder_pattern}'")

    for folder in matching_folders:
        # Look for metadata.json in each matching folder
        metadata_files = list(folder.glob(target_filename))
        
        if not metadata_files:
            report_lines.append(f"\n⚠️ No {target_filename} found in {folder}")
            continue

        for file_path in metadata_files:
            report_lines.append(f"\n📄 Checking file: {file_path}")
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    json_data = json.loads(content)

                    file_stats, modified = check_units(json_data, expected_units, auto_fix)

                    for key, result in file_stats.items():
                        report_lines.append(f"🔍 Checking '{key}' (Expected: '{result['expected_unit']}'):")
                        report_lines.append(f"   ✅ Passed: {result['pass']}")
                        report_lines.append(f"   ❌ Failed: {result['fail']}")

                    if auto_fix and modified:
                        file_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
                        report_lines.append("   ✏️ Units auto-corrected and file updated.")
                
                except Exception as e:
                    report_lines.append(f"   ❌ Error processing file: {str(e)}")

    # Write report to file
    output_file.write_text('\n'.join(report_lines), encoding='utf-8')
    print(f"\n📝 Report saved to: {output_file}")

# Update the main section to use the pattern
if __name__ == "__main__":
    expected_units = load_expected_units(unit_rules_file)
    if expected_units:
        # Search in folders starting with "EM-"
        search_and_check_files(search_root, expected_units, auto_fix=True, folder_pattern="*")