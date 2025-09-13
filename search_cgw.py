from pathlib import Path
import re
import json
from jsonpath_ng import parse

# CONFIGURATION
base_path = Path("E:/temp_projects/json_values_checker/floor/")
target_filename = "metadata.json"
unit_rules_file = Path("E:/temp_projects/json_values_checker/keyword.json")  # Path to expected units JSON
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

def apply_corrections(json_data, corrections):
    """Update the JSON data with the correct unit values based on collected paths."""
    print(corrections)
    for path_str, correct_unit in corrections:
        path_expr = parse(path_str)
        matches = path_expr.find(json_data)
        for match in matches:
            if isinstance(match.value, dict):
                match.value['units'] = correct_unit


def check_units(json_data, expected_units):
    """Check if units for each key match the expected ones, and collect paths needing correction."""
    stats = {}
    paths = ['$' + s for s in get_paths(json_data)]
    corrections = []

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
                        corrections.append((path_str, expected_unit))

        stats[keyword] = {
            'expected_unit': expected_unit,
            'pass': pass_count,
            'fail': fail_count
        }

    return stats, corrections

def run_cgw_folder_scan(base_path, expected_units):
    report_lines = []

    # for i in range(50201, 1090208):  # inclusive of CGW-1090207
    #     folder_name = f"CGW-{i}"
    #     folder_path = base_path / folder_name

    if not base_path.exists():
        report_lines.append(f"\n🚫 Missing folder: {base_path}")
        

    matched_files = list(base_path.rglob(target_filename))
    if not matched_files:
        report_lines.append(f"\n📁 Folder exists but no '{target_filename}' in: {base_path}")
        

    for file_path in matched_files:
        report_lines.append(f"\n📄 Checking file: {file_path}")
        try:
            content = file_path.read_text(encoding='utf-8')
            json_data = json.loads(content)

            file_stats, corrections = check_units(json_data, expected_units)

            for key, result in file_stats.items():
                report_lines.append(f"🔍 Checking '{key}' (Expected: '{result['expected_unit']}'):")
                report_lines.append(f"   ✅ Passed: {result['pass']}")
                report_lines.append(f"   ❌ Failed: {result['fail']}")

            if corrections:
                report_lines.append(f"🔧 Applying {len(corrections)} corrections.")
                apply_corrections(json_data, corrections)
                file_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
                report_lines.append("💾 File updated with corrected units.")
        except Exception as e:
            report_lines.append(f"❗ Error reading or parsing file {file_path}: {e}")

    output_file.write_text('\n'.join(report_lines), encoding='utf-8')
    print(f"\n📝 CGW Report saved to: {output_file}")

if __name__ == "__main__":
    expected_units = load_expected_units(unit_rules_file)
    if expected_units:
        run_cgw_folder_scan(base_path, expected_units)
