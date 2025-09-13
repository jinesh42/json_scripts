from pathlib import Path
import re
import json
from jsonpath_ng import parse

# CONFIGURATION
search_root = Path("E:/temp_projects/json_values_checker/floor/")
target_filename = "metadata.json"
unit_rules_file = Path("E:/temp_projects/json_values_checker/keyword.json")  # Path to expected units JSON

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

def check_units(json_data, expected_units):
    """Check if units for each key match the expected ones."""
    stats = {}
    paths = ['$' + s for s in get_paths(json_data)]

    for keyword, expected_unit in expected_units.items():
        matching_paths = [p for p in paths if re.search(keyword, p, re.IGNORECASE)]
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

        stats[keyword] = {
            'expected_unit': expected_unit,
            'pass': pass_count,
            'fail': fail_count
        }

    return stats

def search_and_check_files(root_dir: Path, expected_units):
    matched_files = list(root_dir.rglob(target_filename))
    if not matched_files:
        print("No matching files found.")
        return

    for file_path in matched_files:
        print(f"\n📄 Checking file: {file_path}")
        if file_path.is_file():
            content = file_path.read_text(encoding='utf-8')
            json_data = json.loads(content)

            file_stats = check_units(json_data, expected_units)

            for key, result in file_stats.items():
                print(f"🔍 Checking '{key}' (Expected: '{result['expected_unit']}'):")
                print(f"   ✅ Passed: {result['pass']}")
                print(f"   ❌ Failed: {result['fail']}")

if __name__ == "__main__":
    expected_units = load_expected_units(unit_rules_file)
    if expected_units:
        search_and_check_files(search_root, expected_units)
