# Copyright 2026 University of North Carolina at Charlotte.
# v 1.0.0
# Scott Do (Reshlynt)
# The function of this script is to merge inlet and junction data into a single gpkg file for a given city. It presumes that the data for the city has already been fetched and stored in a directory named after the city in outputs. This should be run after the fetchdatabycities.py.

import argparse
import os
import geopandas as gpd
import pandas as pd
from city_configs import CITY_CONFIG

# =====================================================
# ARGUMENTS
# =====================================================

parser = argparse.ArgumentParser(
    description="Assemble downloaded stormwater layers into Inlets.gpkg and Pipes.gpkg."
)

parser.add_argument(
    "cities",
    nargs="+",
    help="One or more city names to process, e.g. Raleigh Fayetteville"
)

args = parser.parse_args()

# Validate all names before touching any files
for city in args.cities:
    if city not in CITY_CONFIG:
        raise ValueError(
            f"'{city}' not found in CITY_CONFIG. "
            f"Valid entries: {list(CITY_CONFIG.keys())}"
        )
    if "layer_roles" not in CITY_CONFIG[city]:
        raise ValueError(
            f"'{city}' has no layer_roles defined in CITY_CONFIG."
        )

# =====================================================
# ASSEMBLY
# =====================================================

for city in args.cities:

    print("\n" + "=" * 60)
    print(f"Assembling: {city}")
    print("=" * 60)

    cfg = CITY_CONFIG[city]

    node_layers = []
    pipe_layers = []

    for layer_id, role in cfg["layer_roles"].items():

        raw_path = os.path.join("outputs", city, f"{layer_id}.gpkg")

        if not os.path.exists(raw_path):
            print(f"  WARNING: Layer {layer_id} ({role}) not found at {raw_path} — skipping")
            continue

        gdf = gpd.read_file(raw_path)

        print(f"  Layer {layer_id:>3} | {role:<10} | {len(gdf):,} features")

        if role in ("inlet", "junction", "structure"):
            gdf["feature_type"] = role
            node_layers.append(gdf)

        elif role == "pipe":
            pipe_layers.append(gdf)

        else:
            print(f"  WARNING: Unknown role '{role}' for layer {layer_id} — skipping")

    # -------------------------------------------------
    # NODES
    # -------------------------------------------------

    if not node_layers:
        print(f"\n  ERROR: No node layers assembled for {city} — skipping output")
        continue

    combined_nodes = gpd.GeoDataFrame(
        pd.concat(node_layers, ignore_index=True),
        crs=node_layers[0].crs
    )

    output_dir = os.path.join("geopackage", city)
    os.makedirs(output_dir, exist_ok=True)

    nodes_out = os.path.join(output_dir, "Inlets.gpkg")
    combined_nodes.to_file(nodes_out, driver="GPKG")

    print(f"\n  Inlets written : {len(combined_nodes):,} → {nodes_out}")

    # -------------------------------------------------
    # PIPES
    # -------------------------------------------------

    if not pipe_layers:
        print(f"  WARNING: No pipe layers assembled for {city}")
        continue

    combined_pipes = gpd.GeoDataFrame(
        pd.concat(pipe_layers, ignore_index=True),
        crs=pipe_layers[0].crs
    )

    pipes_out = os.path.join(output_dir, "Pipes.gpkg")
    combined_pipes.to_file(pipes_out, driver="GPKG")

    print(f"  Pipes written  : {len(combined_pipes):,} → {pipes_out}")

print("\nASSEMBLY COMPLETE")