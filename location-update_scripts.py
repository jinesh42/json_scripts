from pathlib import Path
import re
import json
from jsonpath_ng import parse
import pandas as pd
import argparse

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
    """Finds the JSON path with the highest number of matching leading segments."""
    best_match = None
    best_score = 0
    for path in all_paths:
        path_segments = [p for p in path.strip('.').split('.') if p]
        score = 0
        for seg in keyword_segments[:-1]:
            if seg in path_segments:
                score += 1
        if score > best_score:
            best_score = score
            best_match = path
    return best_match, best_score

def set_value_in_path(json_obj, path_list, value):
    """Create intermediate keys if missing and set value at final key."""
    for key in path_list[:-1]:
        if key not in json_obj or not isinstance(json_obj[key], dict):
            json_obj[key] = {}
        json_obj = json_obj[key]
    json_obj[path_list[-1]] = value

def create_nested_structure(json_data, path_parts, value):
    """Creates nested dictionary structure for a given path if it doesn't exist"""
    current = json_data
    for part in path_parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[path_parts[-1]] = value
    return json_data

def _is_blank_cell(cell_value):
    """Return True if the excel cell is empty/NaN/blank after stripping."""
    if pd.isna(cell_value):
        return True
    s = str(cell_value).strip()
    return s == "" or s.lower() == "nan"

def process_file(file_path, row, columns, folder_pattern="*"):
    """Process a single JSON file with Excel data. Create/update when Excel has value.
       Remove key if Excel cell is blank."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            json_data = json.load(f)

        paths = list(get_paths(json_data))
        changes_made = False

        for keyword in columns:
            # skip invalid column names
            if not keyword:
                continue

            raw_cell = row.get(keyword, "")
            if _is_blank_cell(raw_cell):
                # remove key from JSON if present
                # find any exact matches that end with .<keyword>
                exact_matches = [p for p in paths if p.lower().endswith("." + keyword.lower())]
                if not exact_matches:
                    # nothing to remove
                    continue

                for p in exact_matches:
                    # parent path (without the trailing .keyword)
                    if "." in p:
                        parent_path = p.rsplit(".", 1)[0]  # keeps leading dot(s)
                    else:
                        parent_path = ""
                    try:
                        if parent_path == "" or parent_path == ".":
                            parent_expr = parse("$")
                        else:
                            parent_expr = parse("$" + parent_path)
                        parent_matches = parent_expr.find(json_data)
                        for pm in parent_matches:
                            if isinstance(pm.value, dict):
                                # remove the key if present (case-sensitive as stored)
                                # find actual key name in parent dict (match case-insensitive)
                                keys_map = {k.lower(): k for k in pm.value.keys()}
                                key_lower = keyword.lower()
                                if key_lower in keys_map:
                                    real_key = keys_map[key_lower]
                                    del pm.value[real_key]
                                    changes_made = True
                                    print(f"🗑 Removed '{real_key}' from {parent_path or '$'} in {file_path}")
                    except Exception as e:
                        print(f"❌ Error removing {keyword} in {file_path}: {e}")
                continue  # proceed next column

            # non-blank cell -> sanitize and set/create/update
            excel_value = str(raw_cell).strip()
            if '&' in excel_value:
                excel_value = excel_value.replace(' ', '').replace('&', '-')
            elif '/' in excel_value:
                excel_value = excel_value.replace(' ', '').replace('/', '-')
            elif ' ' in excel_value:
                excel_value = excel_value.replace(' ', '-')

            keyword_segments = [seg for seg in keyword.split('.') if seg]

            try:
                # Try exact path match first
                exact_matches = [p for p in paths if p.lower().endswith("." + keyword.lower())]
                if exact_matches:
                    path_expr = parse("$" + exact_matches[0])
                    path_expr.update(json_data, excel_value)
                    changes_made = True
                    print(f"✅ Updated existing: {keyword} → {excel_value}  ({file_path})")
                    continue

                # If full dotted path provided, create nested structure
                if '.' in keyword and len(keyword_segments) > 0:
                    create_nested_structure(json_data, keyword_segments, excel_value)
                    changes_made = True
                    print(f"✅ Created new nested path: {keyword} → {excel_value}  ({file_path})")
                    continue

                # Fallback: find best parent match and insert under it
                best_parent, score = find_best_match_segments(keyword_segments, paths)
                if best_parent and score > 0:
                    parent_segments = [s for s in best_parent.strip('.').split('.') if s]
                    path_list = parent_segments + [keyword_segments[-1]]
                    set_value_in_path(json_data, path_list, excel_value)
                    changes_made = True
                    print(f"✅ Added via parent match: {'.'.join(path_list)} → {excel_value}  ({file_path})")
                else:
                    print(f"❌ No suitable match found for '{keyword}', skipped. ({file_path})")

            except Exception as e:
                print(f"❌ Error processing {keyword} in {file_path}: {str(e)}")
                continue

        if changes_made:
            with file_path.open("w", encoding="utf-8") as fw:
                json.dump(json_data, fw, indent=2)
            print(f"✅ Saved changes to {file_path}")

    except Exception as e:
        print(f"❌ Error processing file {file_path}: {str(e)}")

def process_single_update(key, value, search_root, target_filename, folder_pattern="*"):
    """Process single key-value update across all matching files. If value is blank, remove key(s)."""
    matched_files = list(search_root.rglob(target_filename))
    for file in matched_files:
        if folder_pattern != "*" and not file.parent.match(folder_pattern):
            continue

        try:
            with file.open("r", encoding="utf-8") as f:
                json_data = json.load(f)

            paths = list(get_paths(json_data))
            keyword_segments = [seg for seg in key.split('.') if seg]
            changes_made = False

            if _is_blank_cell(value):
                # remove any matching keys
                exact_matches = [p for p in paths if p.lower().endswith("." + key.lower())]
                for p in exact_matches:
                    parent_path = p.rsplit(".", 1)[0] if "." in p else ""
                    try:
                        parent_expr = parse("$" + parent_path) if parent_path and parent_path != "." else parse("$")
                        parent_matches = parent_expr.find(json_data)
                        for pm in parent_matches:
                            if isinstance(pm.value, dict):
                                keys_map = {k.lower(): k for k in pm.value.keys()}
                                kl = key.lower().split('.')[-1]
                                if kl in keys_map:
                                    del pm.value[keys_map[kl]]
                                    changes_made = True
                                    print(f"🗑 Removed '{keys_map[kl]}' from {parent_path or '$'} in {file}")
                    except Exception as e:
                        print(f"❌ Error removing {key} in {file}: {e}")
            else:
                # sanitize provided value
                val = str(value).strip()
                if '&' in val:
                    val = val.replace(' ', '').replace('&', '-')
                elif '/' in val:
                    val = val.replace(' ', '').replace('/', '-')
                elif ' ' in val:
                    val = val.replace(' ', '-')

                # Try exact path match first
                exact_matches = [p for p in paths if p.lower().endswith("." + key.lower())]
                if exact_matches:
                    path_expr = parse("$" + exact_matches[0])
                    path_expr.update(json_data, val)
                    changes_made = True
                elif '.' in key and len(keyword_segments) > 0:
                    create_nested_structure(json_data, keyword_segments, val)
                    changes_made = True
                else:
                    best_parent, score = find_best_match_segments(keyword_segments, paths)
                    if best_parent and score > 0:
                        parent_segments = [s for s in best_parent.strip('.').split('.') if s]
                        path_list = parent_segments + [keyword_segments[-1]]
                        set_value_in_path(json_data, path_list, val)
                        changes_made = True

            if changes_made:
                with file.open("w", encoding="utf-8") as fw:
                    json.dump(json_data, fw, indent=2)
                print(f"✅ Updated {key} in {file}")

        except Exception as e:
            print(f"❌ Error processing {file}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(
        description='Process JSON files with Excel input or specific parameter updates'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input',
                       default="Appendix 6 - _IN-BLR-ANANTA_ Digital Building Device Register v2.0 Chubb [go_bos-app6].xlsx",
                       help='Input Excel file path')
    group.add_argument('-p', '--param',
                       nargs=2,
                       metavar=('KEY', 'VALUE'),
                       help='Key and value to update (e.g., "system.location.x" "10")')

    parser.add_argument('--root',
                        default="E:/temp_projects/json_values_checker/devices/",
                        help='Root directory for searching metadata files')
    parser.add_argument('--filename',
                        default="metadata.json",
                        help='Target filename to process (default: metadata.json)')
    parser.add_argument('--pattern',
                        default="*",
                        help='Folder name pattern to match (e.g., "EM-*")')

    args = parser.parse_args()

    search_root = Path(args.root)
    if not search_root.exists():
        print(f"❌ Root directory not found: {search_root}")
        return

    if args.input:
        if not Path(args.input).exists():
            print(f"❌ Input file not found: {args.input}")
            return

        df = pd.read_excel(args.input, sheet_name='4-All Devices', engine='openpyxl', skiprows=3).fillna("")
        df = df[['Device/Asset role name (asset.name)', 'Floor','Location','Panel Reference']]
        df.rename(columns={'Device/Asset role name (asset.name)': 'Devices',
                   'Floor': 'system.location.floor' ,
                   'Location': 'system.location.section',
                   'Panel Reference': 'system.location.panel'}, inplace=True)
        columns = [col for col in df.columns if col != 'Devices']

        for idx, row in df.iterrows():
            device = str(row['Devices']).strip()
            if not device:
                continue

            root_dir = search_root / device
            matched_files = list(root_dir.rglob(args.filename))

            if matched_files:
                for file in matched_files:
                    if args.pattern != "*" and not file.parent.match(args.pattern):
                        continue
                    process_file(file, row, columns)

    elif args.param:
        key, value = args.param
        process_single_update(key, value, search_root, args.filename, args.pattern)

if __name__ == "__main__":
    main()