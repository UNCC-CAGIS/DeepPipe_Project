# Copyright 2026 University of North Carolina at Charlotte.
# v 1.0.1
# Scott Do (Reshlynt)
# The function of this script is to merge a city's downloaded stormwater layers into two gpkg files:
#   Inlets.gpkg - every node layer (inlet, junction, structure, IO), tagged by feature_type
#   Pipes.gpkg  - every pipe layer
# It presumes that the data for the city has already been fetched and stored in a directory named
# after the city in outputs. This should be run after the fetchdatabycities.py.
# A city is written only if every required role loaded; the script exits with code 1 if any city failed.

import argparse
import os
import sys
import shutil
import geopandas as gpd
import pandas as pd
from city_configs import CITY_CONFIG

# =====================================================
# PATHS AND ROLES
# =====================================================

# Anchor paths to the repo root (this script lives in ROOT-REPO/code), so the script behaves the
# same from any working directory and rmtree can never delete a geopackage/ folder somewhere else.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "outputs")
OUT_DIR = os.path.join(BASE_DIR, "geopackage")

NODE_ROLES = ("inlet", "junction", "structure", "IO")
PIPE_ROLES = ("pipe",)
IGNORED_ROLES = ("channel",)                      # fetched, deliberately not assembled
DEFAULT_REQUIRED_ROLES = ("inlet", "pipe")        # used when a city has no required_roles key

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

# Validate all names and roles before touching any files
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

    roles = CITY_CONFIG[city]["layer_roles"]
    known = NODE_ROLES + PIPE_ROLES + IGNORED_ROLES
    unknown = {layer_id: role for layer_id, role in roles.items() if role not in known}
    if unknown:
        raise ValueError(
            f"'{city}' has unknown roles {unknown}. Valid roles: {list(known)}"
        )

    required = CITY_CONFIG[city].get("required_roles", DEFAULT_REQUIRED_ROLES)
    unassigned = [role for role in required if role not in roles.values()]
    if unassigned:
        raise ValueError(
            f"'{city}' requires roles {unassigned} but no layer in layer_roles has them."
        )

    # type_fields may only refine node layers that are actually in layer_roles
    for layer_id in CITY_CONFIG[city].get("type_fields", {}):
        if roles.get(layer_id) not in NODE_ROLES:
            raise ValueError(
                f"'{city}' type_fields entry for layer {layer_id} does not match a node layer in layer_roles."
            )

# ====================================================
# PREPARE OUTPUT DIRECTORY
# ====================================================

for city in args.cities:
    output_dir = os.path.join(OUT_DIR, city)
    if os.path.exists(output_dir):
        print(f"Removing existing output directory for {city}: {output_dir}")
        shutil.rmtree(output_dir)

# =====================================================
# ASSEMBLY
# =====================================================

failed = []

for city in args.cities:

    print("\n" + "=" * 60)
    print(f"Assembling: {city}")
    print("=" * 60)

    cfg = CITY_CONFIG[city]
    required = set(cfg.get("required_roles", DEFAULT_REQUIRED_ROLES))

    node_layers = []
    pipe_layers = []
    loaded_roles = set()
    layer_error = None

    for layer_id, role in cfg["layer_roles"].items():

        # Merge layers based on their role, set in city_configs.py

        if role in IGNORED_ROLES:
            print(f"  Layer {layer_id:>3} | {role:<10} | ignored by design")
            continue

        raw_path = os.path.join(RAW_DIR, city, f"{layer_id}.gpkg")

        if not os.path.exists(raw_path):
            print(f"  WARNING: Layer {layer_id} ({role}) not found at {raw_path} — skipping")
            continue

        gdf = gpd.read_file(raw_path)

        print(f"  Layer {layer_id:>3} | {role:<10} | {len(gdf):,} features")

        if role in NODE_ROLES:
            type_field = cfg.get("type_fields", {}).get(layer_id)

            if type_field:
                field, mapping = type_field
                if field not in gdf.columns:
                    layer_error = f"Layer {layer_id} ({role}) has no '{field}' field for type_fields"
                    break
                values = gdf[field].astype("string").str.strip()
                gdf["feature_type"] = values.map(mapping).fillna(f"{role}_unknown")
                print(f"      {field} -> feature_type: {gdf['feature_type'].value_counts().to_dict()}")
            else:
                gdf["feature_type"] = role

            node_layers.append(gdf)

        else:  # role in PIPE_ROLES (anything else was rejected during validation)
            pipe_layers.append(gdf)

        loaded_roles.add(role)

    # -------------------------------------------------
    # COMPLETENESS CHECK (before anything is written)
    # -------------------------------------------------

    if layer_error:
        print(f"\n  ERROR: {layer_error} — no output written")
        failed.append(city)
        continue

    missing = required - loaded_roles

    if missing:
        print(f"\n  ERROR: Required roles missing for {city}: {sorted(missing)} — no output written")
        failed.append(city)
        continue

    if not node_layers or not pipe_layers:
        print(f"\n  ERROR: {city} needs at least one node layer and one pipe layer — no output written")
        failed.append(city)
        continue

    # -------------------------------------------------
    # BUILD BOTH TABLES
    # -------------------------------------------------

    combined_nodes = gpd.GeoDataFrame(
        pd.concat(node_layers, ignore_index=True),
        crs=node_layers[0].crs
    )

    combined_pipes = gpd.GeoDataFrame(
        pd.concat(pipe_layers, ignore_index=True),
        crs=pipe_layers[0].crs
    )

    # -------------------------------------------------
    # WRITE BOTH FILES
    # -------------------------------------------------

    output_dir = os.path.join(OUT_DIR, city)
    os.makedirs(output_dir, exist_ok=True)

    nodes_out = os.path.join(output_dir, "Inlets.gpkg")
    pipes_out = os.path.join(output_dir, "Pipes.gpkg")

    combined_nodes.to_file(nodes_out, driver="GPKG")
    combined_pipes.to_file(pipes_out, driver="GPKG")

    print(f"\n  Inlets written : {len(combined_nodes):,} → {nodes_out}")
    print(f"  Pipes written  : {len(combined_pipes):,} → {pipes_out}")

# =====================================================
# RESULT
# =====================================================

if failed:
    print(f"\nASSEMBLY FAILED FOR: {failed}")
    sys.exit(1)

print("\nASSEMBLY COMPLETE")