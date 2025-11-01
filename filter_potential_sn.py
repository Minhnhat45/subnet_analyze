import json
import subprocess
from multiprocessing.dummy import Pool       # lightweight thread pool
from pathlib import Path
import os
# Directory where the individual JSON files will live
OUTPUT_DIR = Path("netuid_data")
OUTPUT_DIR.mkdir(exist_ok=True)               # create once at start

def norm_data(data):
    return data.replace("\n", "")

def fetch_and_save(n: int) -> bool:
    """
    Run `btcli s show --json-out --netuid <n>`, dump the result to
    netuid_data/<n>.json, and return True on success.
    """
    cmd = ["btcli", "s", "show", "--json-out", "--netuid", str(n)]
    try:
        raw = subprocess.check_output(cmd, text=True)
        data = norm_data(raw)
        data_out = json.loads(data)

        # Write pretty-printed JSON to   netuid_data/<n>.json
        (OUTPUT_DIR / f"{n}.json").write_text(
            json.dumps(data_out, indent=2, ensure_ascii=False)
        )
        print(f"[✓] netuid {n} saved")
        return True

    except subprocess.CalledProcessError as e:
        print(f"[✗] netuid {n}: btcli failed → {e.stderr or e}")
    except json.JSONDecodeError as e:
        print(f"[✗] netuid {n}: bad JSON → {e}")
    return False

def filter_existed_uids():
    remain_sn = []
    list_file = os.listdir(OUTPUT_DIR)
    for i in range(1, 129):
        if f"str{i}.json" not in list_file:
            remain_sn.append(i)
    return remain_sn

# range(1, 33), range(33, 65), range(65, 97), range(97, 129)
def main() -> None:
    range_list = [range(65, 97), range(97, 129)]
    for netuids in range_list:
        print(netuids)
        # netuids = range(1*i, 129)                   # 1-128 inclusive
        with Pool(processes=10) as pool:          # 10 worker threads
            successes = sum(pool.map(fetch_and_save, netuids))
        print(f"\nDone. {successes}/{len(netuids)} files written to {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
