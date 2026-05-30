import json
from pathlib import Path


source_dir = Path("./netuid_data")
norm_dir = Path("./netuid_data_norm")
norm_dir.mkdir(parents=True, exist_ok=True)


def numeric_sort_key(path: Path) -> int:
    try:
        return int(path.stem)
    except ValueError:
        return 10**9


for src_path in sorted(source_dir.glob("*.json"), key=numeric_sort_key):
    raw_text = src_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        print(f"🛑 Empty file: {src_path.name}")
        continue

    # Input files contain literal line breaks inside quoted values.
    # Joining lines normalizes them into valid JSON before parsing.
    normalized_text = "".join(raw_text.splitlines())

    try:
        output = json.loads(normalized_text)
    except json.JSONDecodeError as exc:
        print(f"🛑 Parse failed for {src_path.name}: {exc}")
        continue

    out_path = norm_dir / src_path.name
    out_path.write_text(json.dumps(output, indent=4), encoding="utf-8")
    print(f"✅ Done process {src_path.name}")
