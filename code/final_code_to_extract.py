import os
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString
import matplotlib.pyplot as plt

# =====================================================
# CONFIG
# =====================================================

CITY_CONFIG = {

    "Charlotte": {
        "node_id": "ITPIPE_ASSETID",
        "method": "existing",
        "from_field": "US_ASSETID",
        "to_field": "DS_ASSETID"
    },

    "WinstonSalem": {
        "node_id": "StructID",
        "method": "existing",
        "from_field": "US_StructID",
        "to_field": "DS_StructID"
    },

    "Raleigh": {
        "node_id": "FACILITYID",
        "method": "kdtree"
    },

    "Greensboro": {
        "node_id": "AssetID",
        "method": "kdtree"
    },

    "Apex": {
        "node_id": "FACILITYID",
        "method": "kdtree"
    },

    "Asheville": {
        "node_id": "assetid",
        "method": "kdtree"
    },
    "Fayetteville": {
        "node_id": "FACILITYID",
        "method": "kdtree"
    },
    "Wilmington": {
        "node_id": "EAMTAG",
        "method": "hybrid",
        "from_field": "UPEndStID",
        "to_field": "DNEndStID"
    },
}

BASE_FOLDER = "geopackage"

# =====================================================
# BUILT ACTIVE FILE PRE-PROCESSING SET
# =====================================================

active_cities = {
    city: cfg
    for city, cfg in CITY_CONFIG.items()
    if os.path.exists(os.path.join(BASE_FOLDER, city, "Inlets.gpkg"))
    and os.path.exists(os.path.join(BASE_FOLDER, city, "Pipes.gpkg"))
}

for city in CITY_CONFIG:
    if city in active_cities:
        print(f"  FOUND    : {city}")
    else:
        print(f"  MISSING  : {city}")

print(f"\n{len(active_cities)} of {len(CITY_CONFIG)} cities ready to process\n")

# =====================================================
# QA CONFIG
# =====================================================

PROJECTED_CRS = "EPSG:2264"

qa_summary = []

# =====================================================
# MULTILINE SUPPORT
# =====================================================

def get_start_end(geom):

    if geom is None:
        return None, None

    if geom.geom_type == "LineString":

        coords = list(geom.coords)

        if len(coords) < 2:
            return None, None

        return coords[0], coords[-1]

    elif geom.geom_type == "MultiLineString":

        parts = list(geom.geoms)

        if len(parts) == 0:
            return None, None

        first_line = parts[0]
        last_line = parts[-1]

        start_pt = list(first_line.coords)[0]
        end_pt = list(last_line.coords)[-1]

        return start_pt, end_pt

    return None, None


# =====================================================
# PROCESS CITIES
# =====================================================

for city, cfg in active_cities.items():

    print("\n" + "=" * 60)
    print(f"Processing {city}")
    print("=" * 60)

    inlet_file = os.path.join(BASE_FOLDER, city, "Inlets.gpkg")
    pipe_file = os.path.join(BASE_FOLDER, city, "Pipes.gpkg")

    nodes = gpd.read_file(inlet_file)
    edges = gpd.read_file(pipe_file)

    input_inlets = len(nodes)
    input_pipes = len(edges)

    print(f"Input Inlets : {len(nodes):,}")
    print(f"Input Pipes  : {len(edges):,}")

    # -------------------------------------------------
    # CRS CHECK
    # -------------------------------------------------

    if nodes.crs != edges.crs:
        edges = edges.to_crs(nodes.crs)

    # -------------------------------------------------
    # FORCE EVERYTHING TO EPSG:2264
    # -------------------------------------------------
    nodes["lon"] = nodes.geometry.x
    nodes["lat"] = nodes.geometry.y
    
    nodes = nodes.to_crs(PROJECTED_CRS)
    edges = edges.to_crs(PROJECTED_CRS)

    # -------------------------------------------------
    # STANDARDIZE INLETS
    # -------------------------------------------------

    nodes["ID"] = nodes[cfg["node_id"]].astype(str)

    nodes = nodes.dropna(subset=["ID"])

    nodes["X_ft"] = nodes.geometry.x
    nodes["Y_ft"] = nodes.geometry.y

    nodes = nodes.drop_duplicates(
        subset=["ID"]
    ).reset_index(drop=True)

    # -------------------------------------------------
    # CONNECTIVITY
    # -------------------------------------------------

    if cfg["method"] == "existing":

        print("Using existing connectivity")

        edges["From_ID"] = edges[cfg["from_field"]]
        edges["To_ID"] = edges[cfg["to_field"]]

        null_count = (
            edges["From_ID"].isna() |
            edges["To_ID"].isna()
        ).sum()

        print(f"Pipes with NULL From_ID/To_ID: {null_count:,}")

        edges["From_ID"] = edges["From_ID"].astype(str)
        edges["To_ID"] = edges["To_ID"].astype(str)

        nodes["ID"] = nodes["ID"].astype(str)

        edges = edges.dropna(
            subset=["From_ID", "To_ID"]
        )

        edges = edges[
            edges["From_ID"] != "-999"
        ]

        edges = edges[
            edges["To_ID"] != "-999"
        ]

    elif cfg["method"] == "hybrid":

        print("Using Hybrid Connectivity")

        # Existing IDs
        edges["From_ID"] = edges[cfg["from_field"]]
        edges["To_ID"] = edges[cfg["to_field"]]

        null_count = (
            edges["From_ID"].isna() |
            edges["To_ID"].isna()
        ).sum()

        print(f"Pipes with NULL From_ID/To_ID: {null_count:,}")

        nodes["ID"] = nodes["ID"].astype(str)

        # Build KDTree
        node_coords = np.array(
            [[pt.x, pt.y] for pt in nodes.geometry]
        )

        tree = cKDTree(node_coords)

        node_ids = nodes["ID"].values

        # Fill only missing IDs
        for idx, row in edges.iterrows():

            if pd.notna(row["From_ID"]) and pd.notna(row["To_ID"]):
                continue

            start_pt, end_pt = get_start_end(row.geometry)

            if start_pt is None or end_pt is None:
                continue

            _, start_idx = tree.query(start_pt)
            _, end_idx = tree.query(end_pt)

            if pd.isna(row["From_ID"]):
                edges.at[idx, "From_ID"] = node_ids[start_idx]

            if pd.isna(row["To_ID"]):
                edges.at[idx, "To_ID"] = node_ids[end_idx]

    else:
        
        print("Using KDTree connectivity")

        # ----------------------------------------
        # PROJECT TO NC STATE PLANE
        # ----------------------------------------

        nodes_proj = nodes
        edges_proj = edges

        node_coords = np.array([
            [pt.x, pt.y]
            for pt in nodes_proj.geometry
        ])

        tree = cKDTree(node_coords)

        node_ids = nodes["ID"].values

        start_coords = []
        end_coords = []
        valid_rows = []

        for idx, geom in enumerate(edges_proj.geometry):

            start_pt, end_pt = get_start_end(geom)

            if start_pt is not None and end_pt is not None:

                start_coords.append(start_pt)
                end_coords.append(end_pt)
                valid_rows.append(idx)

        edges = edges.iloc[valid_rows].copy()

        start_coords = np.array(start_coords)
        end_coords = np.array(end_coords)

        start_dist, start_idx = tree.query(start_coords)
        end_dist, end_idx = tree.query(end_coords)

        edges["From_ID"] = node_ids[start_idx]
        edges["To_ID"] = node_ids[end_idx]

        edges["From_Distance_ft"] = start_dist
        edges["To_Distance_ft"] = end_dist

        edges["Max_Distance_ft"] = edges[
            ["From_Distance_ft", "To_Distance_ft"]
        ].max(axis=1)

        # -------------------------------------------------
        # PIPE COUNTS BY DISTANCE
        # -------------------------------------------------

        print("\nPIPE COUNT BY MAX DISTANCE")

        count_0 = (edges["Max_Distance_ft"] == 0).sum()
        count_1 = ((edges["Max_Distance_ft"] > 0) & (edges["Max_Distance_ft"] <= 1)).sum()
        count_2 = ((edges["Max_Distance_ft"] > 1) & (edges["Max_Distance_ft"] <= 2)).sum()
        count_3 = ((edges["Max_Distance_ft"] > 2) & (edges["Max_Distance_ft"] <= 3)).sum()

        print(f"0 ft           : {count_0:,}")
        print(f">0 - 1 ft      : {count_1:,}")
        print(f">1 - 2 ft      : {count_2:,}")
        print(f">2 - 3 ft      : {count_3:,}")

        # -------------------------------------------------
        # KEEP ONLY PERFECT MATCHES (0 ft)
        # -------------------------------------------------

        before = len(edges)

        edges = edges[
            (edges["From_Distance_ft"] <= 3) &
            (edges["To_Distance_ft"] <= 3)
        ].copy()

        removed = before - len(edges)

        removed_percent = round(
            removed * 100 / before,
            2
        )

        print("\nKEEPING ONLY 3 ft MATCHES")
        print(f"Removed Pipes : {removed:,}")
        print(f"Remaining Pipes : {len(edges):,}")

    # -------------------------------------------------
    # REMOVE SELF LOOPS
    # -------------------------------------------------

    edges = edges[
        edges["From_ID"] != edges["To_ID"]
    ]

    # -------------------------------------------------
    # VALIDATE IDS
    # -------------------------------------------------

    valid_ids = set(nodes["ID"])

    edges = edges[
        edges["From_ID"].isin(valid_ids)
    ]

    edges = edges[
        edges["To_ID"].isin(valid_ids)
    ]

    # -------------------------------------------------
    # REMOVE DUPLICATE EDGES
    # -------------------------------------------------

    edges["edge_key"] = edges.apply(
        lambda row: tuple(
            sorted([
                str(row["From_ID"]),
                str(row["To_ID"])
            ])
        ),
        axis=1
    )

    edges = edges.drop_duplicates(
        subset=["edge_key"]
    )

    if "Max_Distance_ft" in edges.columns:

        print("\n========== QA SUMMARY ==========")

        print(f"Average Offset      : {edges['Max_Distance_ft'].mean():.2f} ft")
        print(f"Median Offset       : {edges['Max_Distance_ft'].median():.2f} ft")
        print(f"95th Percentile     : {edges['Max_Distance_ft'].quantile(0.95):.2f} ft")
        print(f"Maximum Offset      : {edges['Max_Distance_ft'].max():.2f} ft")

        avg_distance = edges["Max_Distance_ft"].mean()

        std_distance = edges["Max_Distance_ft"].std()

        median_distance = edges["Max_Distance_ft"].median()

        p95 = edges["Max_Distance_ft"].quantile(0.95)

        max_distance = edges["Max_Distance_ft"].max()

        print()

        print(f"Removed Percentage : {(removed / before) * 100:.2f}%")
        

    # -------------------------------------------------
    # KEEP CONNECTED NODES
    # -------------------------------------------------

    connected_ids = (
        set(edges["From_ID"])
        |
        set(edges["To_ID"])
    )

    print("\nCONNECTIVITY STATISTICS")

    print(
        f"Unique From_IDs           : {edges['From_ID'].nunique():,}"
    )

    print(
        f"Unique To_IDs             : {edges['To_ID'].nunique():,}"
    )

    print(
        f"Unique Connected Inlets   : {len(connected_ids):,}"
    )

    print(
        f"Average Pipes per Inlet   : {len(edges)/len(connected_ids):.2f}"
    )

    nodes = nodes[
        nodes["ID"].isin(connected_ids)
    ]

        
    # -------------------------------------------------
    # FINAL OUTPUT
    # -------------------------------------------------

    inlet_final = nodes[
    [
        "ID",
        "lat",
        "lon",
        "X_ft",
        "Y_ft",
        "geometry"
    ]
    ].copy()

    if "Max_Distance_ft" in edges.columns:

        pipe_final = edges[
        [
            "From_ID",
            "To_ID",
            "From_Distance_ft",
            "To_Distance_ft",
            "Max_Distance_ft",
            "geometry"
        ]
        ].copy()

    else:

        pipe_final = edges[
        [
            "From_ID",
            "To_ID",
            "geometry"
        ]
        ].copy()

    # -------------------------------------------------
    # STORE CITY QA SUMMARY
    # -------------------------------------------------

    if "Max_Distance_ft" in edges.columns:

        qa_summary.append({

        "City": city,
        "Method": "KDTree",

        "Input_Inlets": input_inlets,
        "Final_Inlets": len(inlet_final),

        "Input_Pipes": input_pipes,
        "Final_Pipes": len(pipe_final),

        "Average_Offset_ft": round(avg_distance,2),
        "Std_Dev_ft": round(std_distance,2),
        "Median_ft": round(median_distance,2),
        "95th_Percentile_ft": round(p95,2),
        "Maximum_Offset_ft": round(max_distance,2),

        "Removed_Pipes": removed,
        "Removed_Percent": removed_percent,
    })

    if cfg["method"] == "existing":

        qa_summary.append({

            "City": city,
            "Method": "Existing Connectivity",

            "Input_Inlets": input_inlets,
            "Final_Inlets": len(inlet_final),

            "Input_Pipes": input_pipes,
            "Final_Pipes": len(pipe_final),

            "Average_Offset_ft": "N/A",
            "Std_Dev_ft": "N/A",
            "Median_ft": "N/A",
            "95th_Percentile_ft": "N/A",
            "Adaptive_Threshold_ft": "N/A",
            "Maximum_Offset_ft": "N/A",

            "Removed_Pipes": "N/A",
            "Removed_Percent": "N/A",

            "GOOD": "N/A",
            "REVIEW": "N/A",
            "BAD": "N/A"
        })

    if cfg["method"] == "hybrid":

        existing_connections = (
            edges[cfg["from_field"]].notna() &
            edges[cfg["to_field"]].notna()
        ).sum()

        filled_connections = len(edges) - existing_connections

        qa_summary.append({

            "City": city,
            "Method": "Hybrid Connectivity",

            "Input_Inlets": input_inlets,
            "Final_Inlets": len(inlet_final),

            "Input_Pipes": input_pipes,
            "Final_Pipes": len(pipe_final),

            "Average_Offset_ft": "N/A",
            "Std_Dev_ft": "N/A",
            "Median_ft": "N/A",
            "95th_Percentile_ft": "N/A",
            "Adaptive_Threshold_ft": "N/A",
            "Maximum_Offset_ft": "N/A",

            "Removed_Pipes": "N/A",
            "Removed_Percent": "N/A",

            "GOOD": "N/A",
            "REVIEW": "N/A",
            "BAD": "N/A",

            "Existing_Connections": existing_connections,
            "KDTree_Filled": filled_connections
        })

    # -------------------------------------------------
    # SAVE AS GEOPACKAGE
    # -------------------------------------------------

    output_folder = os.path.join(
        BASE_FOLDER,
        city,
        "Final"
    )

    os.makedirs(output_folder, exist_ok=True)

    output_gpkg = os.path.join(
        output_folder,
        f"{city}.gpkg"
    )

    if os.path.exists(output_gpkg):
        os.remove(output_gpkg)

    # Save inlet layer

    inlet_final.to_file(
        output_gpkg,
        layer="Inlets",
        driver="GPKG"
    )

    # Save pipe layer

    pipe_final.to_file(
        output_gpkg,
        layer="Pipes",
        driver="GPKG"
    )

    print(f"\nFinal Inlets : {len(inlet_final):,}")
    print(f"Final Pipes  : {len(pipe_final):,}")

    print(f"\nGeoPackage Layers:")
    print(f"  Inlets : {len(inlet_final):,}")
    print(f"  Pipes  : {len(pipe_final):,}")

    print(f"\nSaved: {output_gpkg}")

# -------------------------------------------------
# SAVE QA REPORT
# -------------------------------------------------

if len(qa_summary) > 0:

    qa_df = pd.DataFrame(qa_summary)

    qa_report_path = os.path.join(
        BASE_FOLDER,
        "All_Cities_QA_Report.csv"
    )

    qa_df.to_csv(
        qa_report_path,
        index=False
    )

    print("\nQA REPORT SAVED")
    print(qa_report_path)


print("\nDONE - ALL CITIES PROCESSED")