from pathlib import Path
import re
import json
from jsonpath_ng import parse
import pandas as pd 

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

search_root = Path("E:/temp_projects/json_values_checker/devices/")
target_filename = "metadata.json"
#unit_rules_file = Path("E:/temp_projects/json_values_checker/keyword.json")
output_file = Path("E:/temp_projects/json_values_checker/unit_check_report.txt")

input_file_path = 'input.xlsx'  # or the full path if needed
df = pd.read_excel(input_file_path,sheet_name='Main', engine='openpyxl')

df = df.fillna("")

df.to_dict()

#print(type(df))

all_col = list(df.columns)
exclude_col = 'Devices'
columns = [col for col in all_col if col != exclude_col]
req_df = df[columns]
#print(f"Columns in DataFrame: {columns}")

# Accessing columns
i=0
for index, row in df.iterrows():
    device = row['Devices'].strip()
    #path = row['Path']
    root_dir = Path(str(search_root) + "\\" + device + "\\")
    #print(f"Root Directory: {root_dir}")

    matched_files = list(root_dir.rglob(target_filename))
    if not matched_files:
        print("No matching files found.")
    else:
        for file in matched_files:
            print(f"Found file: {file}")
            with file.open("r", encoding="utf-8") as f:
                json_data = json.load(f)
                #stats = {}
                paths = ['$' + s for s in get_paths(json_data)]
                #print(f"Paths in JSON: {paths}")
                
                for keyword, value in req_df.items():

                    matching_paths = [p for p in paths if re.search(rf"\.{re.escape(keyword)}$", p, re.IGNORECASE)]
                    print(f"Matching paths for keyword '{keyword}': {matching_paths}")
                    pass_count = 0
                    fail_count = 0

                    for path_str in matching_paths:
                        path_expr = parse(path_str)
                        matches = path_expr.find(json_data)
                        #print(f"Matches found for path '{path_str}': {matches}")

                        for match in matches:
                            #print(f"Match found: {match.value}")
                            #if isinstance(match.value, dict):
                            keys = match.value
                            print(keys , "Print keys")
                            print("Keyword: ", keyword)
                            print(i)
                            print("Value: ", req_df.loc[i,keyword])
                            print("Check",keys == str(req_df.loc[i,keyword]))
                            if keys == str(req_df.loc[i,keyword]):
                                pass_count += 1
                                print(f"Pass count for {keyword}: {pass_count}")
                            else:
                                fail_count += 1
                                path_expr.update(json_data,str(req_df.loc[i,keyword]))
                               
                            
        
    i= i + 1
          
with file.open("w", encoding="utf-8") as f_write:
    json.dump(json_data, f_write, indent=2)  

    # print(f"Device: {device}, Value: {value}")

