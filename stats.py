import glob
import os
from collections import defaultdict
from enum import Enum

possible_file_prefixes = ("league", "player")


def get_total_stored_json_size(prefixes=possible_file_prefixes, kb=False, gb=False):
    paths = [path for path in glob.glob("*.json") if path.startswith(prefixes)]
    total = sum([os.path.getsize(path) for path in paths])
    total = total / (1024 * 1024)

    if kb:
        return round((total / (1024 * 1024)), 4) 
    if gb:
        return round((total / 1024), 2)
    
    return round(total, 3)
    

total = get_total_stored_json_size()
print(f"Stored JSON size: {total:2f} MB")