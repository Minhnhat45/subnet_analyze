"""
- Filter subnet with common distribution pattern.
- Avoid the winner take all subnet.
- Affofable registation fee.
"""
import json
from tqdm import tqdm


data_path = "./netuid_data_norm/"
register_fee_threshold = 0.1

def load_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data

