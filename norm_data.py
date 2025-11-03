import json
import tqdm
import pdb
import ast
import os
norm_path = "./netuid_data_norm/"
if not os.path.exists(norm_path):
    os.makedirs(norm_path)

for i in range(1, 128):
    with open(f"./netuid_data/{i}.json", "r") as f:
        out_data = f.read().splitlines()
        if out_data:
            out_string = "".join(out_data)
            out_string = out_string.replace("\n", "")
            output = ast.literal_eval(out_string)
            print(f"✅ Done process {i}")
            f.close()
            with open(f"{norm_path}{i}.json", "w") as f_out:
                json.dump(output, f_out, indent=4)
        else:
            print(f"🛑 Fail process {i}")
            pass
    
