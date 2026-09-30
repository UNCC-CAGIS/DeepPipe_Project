import requests
import geopandas as gpd
from shapely.geometry import (
    Point,
    LineString,
    Polygon,
    MultiLineString,
    MultiPolygon
)
import pandas as pd
import time
import os
from city_configs import CITY_CONFIG

# =====================================================
# CONFIG
# =====================================================

CITY_NAME = "Fayetteville"

BASE_URL = CITY_CONFIG[CITY_NAME]["url"]

LAYER_IDS = CITY_CONFIG[CITY_NAME]["layers"]

CITY_OUTPUT_DIR = os.path.join("outputs", CITY_NAME)

os.makedirs(CITY_OUTPUT_DIR, exist_ok=True)


# =====================================================
# GET ALL LAYERS
# =====================================================

def get_all_layers():

    url = f"{BASE_URL}?f=json"

    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    return data.get("layers", [])


# =====================================================
# GET LAYER METADATA
# =====================================================

def get_layer_metadata(layer_id):

    url = f"{BASE_URL}/{layer_id}?f=json"

    response = requests.get(url)
    response.raise_for_status()

    return response.json()

def get_layer_count(layer_id):

    query_url = f"{BASE_URL}/{layer_id}/query"

    params = {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json"
    }

    response = requests.get(query_url, params=params)
    response.raise_for_status()

    return response.json()["count"]


# =====================================================
# FETCH ALL FEATURES
# =====================================================

def fetch_all_features(layer_id, batch_size=1000):

    query_url = f"{BASE_URL}/{layer_id}/query"

    all_features = []
    offset = 0

    while True:

        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "2264",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": batch_size
        }

        response = requests.get(query_url, params=params)
        response.raise_for_status()

        data = response.json()

        if "error" in data:
            print("ERROR:", data["error"])
            break

        features = data.get("features", [])

        if not data.get("exceededTransferLimit", False):
            break

        all_features.extend(features)

        print(f"Layer {layer_id}: downloaded {len(all_features)} features")

        offset += len(features)

        time.sleep(0.2)

    return all_features


# =====================================================
# CONVERT ESRI GEOMETRY TO SHAPELY
# =====================================================

def esri_geometry_to_shapely(geometry, geometry_type):

    try:

        # ---------------- POINT ----------------
        if geometry_type == "esriGeometryPoint":

            return Point(
                geometry["x"],
                geometry["y"]
            )

        # ---------------- POLYLINE ----------------
        elif geometry_type == "esriGeometryPolyline":

            paths = geometry.get("paths", [])

            if len(paths) == 1:
                return LineString(paths[0])

            else:
                return MultiLineString(paths)

        # ---------------- POLYGON ----------------
        elif geometry_type == "esriGeometryPolygon":

            rings = geometry.get("rings", [])

            if len(rings) == 1:
                return Polygon(rings[0])

            else:
                polygons = []

                for ring in rings:
                    polygons.append(Polygon(ring))

                return MultiPolygon(polygons)

    except Exception as e:
        print("Geometry conversion failed:", e)

    return None


# =====================================================
# DOWNLOAD SINGLE LAYER
# =====================================================

def download_layer(layer_id):

    metadata = get_layer_metadata(layer_id)

    expected_count = get_layer_count(layer_id)

    layer_name = metadata.get("name", f"layer_{layer_id}")

    geometry_type = metadata.get("geometryType")

    print("\n================================================")
    print(f"Downloading Layer {layer_id}")
    print(f"Layer Name: {layer_name}")
    print(f"Geometry Type: {geometry_type}")
    print("================================================")

    features = fetch_all_features(layer_id)

    records = []
    geometries = []

    for feature in features:

        attrs = feature.get("attributes", {})

        geom = feature.get("geometry")

        if not geom:
            print("Missing geometry")
            print(attrs)
            continue

        shapely_geom = esri_geometry_to_shapely(
            geom,
            geometry_type
        )

        if shapely_geom is not None:

            records.append(attrs)

            geometries.append(shapely_geom)

        else:

            print("Invalid geometry found")
            print(attrs)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(
        records,
        geometry=geometries,
        crs="EPSG:2264"
    )

    # Safe filenames
    safe_name = layer_name.replace(" ", "_")

    geojson_path = os.path.join(
        CITY_OUTPUT_DIR,
        f"{safe_name}.geojson"
    )

    gpkg_path = os.path.join(
        CITY_OUTPUT_DIR,
        f"{safe_name}.gpkg"
    )

    fields_csv_path = os.path.join(
        CITY_OUTPUT_DIR,
        f"{safe_name}_fields.csv"
    )

    # =================================================
    # SAVE GEOJSON
    # =================================================

    gdf.to_file(
        geojson_path,
        driver="GeoJSON"
    )

    # =================================================
    # SAVE GEOPACKAGE
    # =================================================

    gdf.to_file(
        gpkg_path,
        layer=safe_name,
        driver="GPKG"
    )

    # =================================================
    # SAVE FIELD DOCUMENTATION
    # =================================================

    fields = metadata.get("fields", [])

    field_rows = []

    for field in fields:

        field_rows.append({
            "field_name": field.get("name"),
            "field_alias": field.get("alias"),
            "field_type": field.get("type")
        })

    pd.DataFrame(field_rows).to_csv(
        fields_csv_path,
        index=False
    )

    # =================================================
    # PRINT SUMMARY
    # =================================================

    downloaded_count = len(gdf)

    print("\n================ QA SUMMARY ================")
    print(f"ArcGIS Count     : {expected_count:,}")
    print(f"Downloaded Count : {downloaded_count:,}")

    if expected_count == downloaded_count:
        print("Status           : PASS")
    else:
        print(f"Status           : FAIL ({expected_count-downloaded_count:,} features missing)")

    print(f"Valid features: {len(gdf)}")

    print(f"Saved GeoJSON: {geojson_path}")

    print(f"Saved GeoPackage: {gpkg_path}")

    print(f"Saved Fields CSV: {fields_csv_path}")


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print(f"\nStarting {CITY_NAME} Download...\n")

    for layer_id in LAYER_IDS:

        try:

            download_layer(layer_id)

        except Exception as e:

            print("\nFAILED")
            print(f"Layer ID: {layer_id}")
            print(f"Error: {e}")

    print("\nDOWNLOAD COMPLETED")