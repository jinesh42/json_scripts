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

def process_file(file_path, row, columns, folder_pattern="*"):
    """Process a single JSON file with Excel data."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            json_data = json.load(f)

        paths = list(get_paths(json_data))
        changes_made = False

        for keyword in columns:
            excel_value = str(row[keyword])
            if '&' in excel_value: 
                excel_value = excel_value.strip(' ').replace(' ','').replace('&','-')  #changes done as per requirement
            
            elif '/' in excel_value:
                excel_value = excel_value.strip(' ').replace(' ','').replace('/','-')
            elif ' ' in excel_value:
                excel_value = excel_value.strip(' ').replace(' ','-')

            keyword_segments = keyword.split('.')
            print(excel_value)
            try:
                # Try exact path match first
                exact_matches = [p for p in paths if p.lower().endswith("." + keyword.lower())]
                if exact_matches:
                    path_expr = parse("$" + exact_matches[0])
                
                    path_expr.update(json_data, excel_value)
                    print(f"✅ Updated existing: {keyword} → {excel_value}")
                    changes_made = True
                    continue

                # Try creating new nested structure if no exact match
                if '.' in keyword:
                    create_nested_structure(json_data, keyword_segments, excel_value)
                    print(f"✅ Created new nested path: {keyword} → {excel_value}")
                    changes_made = True
                else:
                    # Use existing parent match logic as fallback
                    best_parent, score = find_best_match_segments(keyword_segments, paths)
                    if best_parent and score > 0:
                        parent_segments = best_parent.strip('.').split('.')
                        path_list = parent_segments + [keyword_segments[-1]]
                        set_value_in_path(json_data, path_list, excel_value)
                        print(f"✅ Added via parent match: {'.'.join(path_list)} → {excel_value}")
                        changes_made = True
                    else:
                        print(f"❌ No suitable match found for '{keyword}', skipped.")

            except Exception as e:
                print(f"❌ Error processing {keyword}: {str(e)}")
                continue

        if changes_made:
            with file_path.open("w", encoding="utf-8") as fw:
                json.dump(json_data, fw, indent=2)
            print(f"✅ Saved changes to {file_path}")

    except Exception as e:
        print(f"❌ Error processing file {file_path}: {str(e)}")

def process_single_update(key, value, search_root, target_filename, folder_pattern="*"):
    """Process single key-value update across all matching files."""
    matched_files = list(search_root.rglob(target_filename))
    for file in matched_files:
        if folder_pattern != "*" and not file.parent.match(folder_pattern):
            continue
            
        try:
            with file.open("r", encoding="utf-8") as f:
                json_data = json.load(f)

            paths = list(get_paths(json_data))
            keyword_segments = key.split('.')
            changes_made = False

            # Try exact path match first
            exact_matches = [p for p in paths if p.lower().endswith("." + key.lower())]
            if exact_matches:
                path_expr = parse("$" + exact_matches[0])
                path_expr.update(json_data, value)
                changes_made = True
            elif '.' in key:
                create_nested_structure(json_data, keyword_segments, value)
                changes_made = True

            if changes_made:
                with file.open("w", encoding="utf-8") as fw:
                    json.dump(json_data, fw, indent=2)
                print(f"✅ Updated {key} → {value} in {file}")

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
            
        #df = pd.read_excel(args.input, sheet_name='Main', engine='openpyxl').fillna("")
        df = pd.read_excel(args.input, sheet_name='4-All Devices', engine='openpyxl',skiprows=3).fillna("")
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
        if '&' in value: 
            value = value.strip(' ').replace(' ','').replace('&','-')  #changes done as per requirement
            
        elif '/' in value:
            value = value.strip(' ').replace(' ','').replace('/','-')
        elif ' ' in value:
            value = value.strip(' ').replace(' ','-')

        process_single_update(key, value, search_root, args.filename, args.pattern)

if __name__ == "__main__":
    main()