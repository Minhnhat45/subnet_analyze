import json
import matplotlib as plt
import os
netuids_dir = "./netuid_data"

def filter_incentive(uids_data):
    uids = [uid["incentive"] for uid in uids_data if uid["incentive"] != 0.0]

    # for uid in uids:
    #     print(uid)
    return sorted(uids)

if __name__ == "__main__":
    for sn_file in os.listdir(netuids_dir):
        file = open("/".join([netuids_dir, sn_file]))
        data = json.load(file)

        print(data["registration_cost"])