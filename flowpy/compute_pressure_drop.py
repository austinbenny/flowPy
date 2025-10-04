import argparse
from pathlib import Path

import yaml

from .network_builder import build_network


def compute(inputs_path: str, output_path: str):
    inputs_path = Path(inputs_path).resolve()
    output_path = Path(output_path).resolve()

    with open(inputs_path, "r") as file:
        inputs = yaml.safe_load(file)

    network = build_network(inputs)
    network.write_summary(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute pressure drop summary from a network YAML and write CSV."
    )
    parser.add_argument(
        "-i",
        "--input_path",
        required=True,
        type=Path,
        help="Path to input YAML (e.g., ./data/raw/gsca_network.yaml).",
    )
    parser.add_argument(
        "-o",
        "--output_path",
        required=True,
        type=Path,
        help="Path to output CSV (e.g., ./data/final/gsca_pressure_drop.csv).",
    )
    args = parser.parse_args()

    compute(args.input_path, args.output_path)
