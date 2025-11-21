"""
- Filter subnet with common distribution pattern.
- Avoid the winner take all subnet.
- Affofable registation fee.
"""
import json
from pathlib import Path
from typing import List

from tqdm import tqdm

black_list = [102, 83]

data_path = Path("./netuid_data_norm")
register_fee_threshold = 0.2
min_incentivized_ids = 3
distribution_tolerance = 0.15  # max allowed spread between incentive shares


def load_json(file_path: Path) -> dict:
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


def iter_json_files(data_dir: Path) -> List[Path]:
    return sorted(path for path in data_dir.glob("*.json") if path.is_file())


def extract_incentives(uids: List[dict]) -> List[float]:
    return [uid.get("incentive", 0.0) for uid in uids if uid.get("incentive", 0.0) > 0]


def has_even_distribution(
    incentives: List[float],
    min_ids: int,
    tolerance: float,
) -> bool:
    if len(incentives) < min_ids:
        return False

    total_incentive = sum(incentives)
    if total_incentive == 0:
        return False

    shares = [value / total_incentive for value in incentives]
    return max(shares) - min(shares) <= tolerance


def filter_subnets(
    data_dir: Path,
    fee_threshold: float,
    min_ids: int,
    tolerance: float,
) -> List[dict]:
    results = []

    for file_path in tqdm(iter_json_files(data_dir), desc="Scanning subnets"):
        subnet = load_json(file_path)

        registration_cost = subnet.get("registration_cost")
        if registration_cost is None or registration_cost > fee_threshold:
            continue

        incentives = extract_incentives(subnet.get("uids", []))
        if not has_even_distribution(incentives, min_ids=min_ids, tolerance=tolerance):
            continue
        if subnet.get("netuid") in black_list:
            continue
        results.append(
            {
                "netuid": subnet.get("netuid"),
                "name": subnet.get("name"),
                "registration_cost": registration_cost,
                "incentivized_count": len(incentives),
            }
        )

    return results


def main() -> None:
    if not data_path.exists():
        raise FileNotFoundError(f"Data path not found: {data_path}")

    matching_subnets = filter_subnets(
        data_dir=data_path,
        fee_threshold=register_fee_threshold,
        min_ids=min_incentivized_ids,
        tolerance=distribution_tolerance,
    )

    if not matching_subnets:
        print(
            "No subnets satisfied the registration cost threshold "
            f"and minimum incentivized IDs (>= {min_incentivized_ids})."
        )
        return

    print(
        f"Found {len(matching_subnets)} subnets with registration cost <= {register_fee_threshold} "
        f"and at least {min_incentivized_ids} incentivized IDs with an even distribution."
    )
    for subnet in matching_subnets:
        print(
            f"- netuid {subnet['netuid']}: {subnet.get('name')} \t\t\t | "
            f"registration_cost={subnet['registration_cost']} \t\t\t | "
            f"incentivized IDs={subnet['incentivized_count']}"
        )


if __name__ == "__main__":
    main()
