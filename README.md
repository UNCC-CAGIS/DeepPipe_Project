# Stormwater Infrastructure Data Collection and Preprocessing

## 1. Project Overview

This project collects stormwater infrastructure data from municipal
ArcGIS REST services and preprocesses the data into standardized pipe
and inlet datasets.

The workflow was developed for eight North Carolina municipalities:

-   Charlotte
-   Winston-Salem
-   Raleigh
-   Greensboro
-   Apex
-   Asheville
-   Fayetteville
-   Wilmington

The final data are intended to support downstream stormwater analysis
and future prediction work.

------------------------------------------------------------------------

## 2. Project Workflow

``` text
Municipal ArcGIS REST Services
            |
            v
     Data Collection
            |
            v
     GeoJSON / GeoPackage
            |
            v
     Data Preprocessing
            |
            +--> Existing Connectivity
            |
            +--> KDTree Connectivity
            |
            +--> Hybrid Connectivity
            |
            v
       Data Cleaning
            |
            v
       QA / Validation
            |
            v
     Final GeoPackage
```

------------------------------------------------------------------------

## 3. Data Collection

### Source

Stormwater data were collected from publicly available ArcGIS REST
MapServer services.

The source configuration is stored in:

`city_configs.py`

### Source Services

  -----------------------------------------------------------------------------------------------------------------------------------
  City                                ArcGIS REST Service
  ----------------------------------- -----------------------------------------------------------------------------------------------
  Raleigh                             https://maps.raleighnc.gov/arcgis/rest/services/PublicWorks/Stormwater/MapServer

  Greensboro                          https://gis.greensboro-nc.gov/arcgis/rest/services/WaterResources/StormwaterRAIN_MS/MapServer

  Fayetteville                        https://gismaps.ci.fayetteville.nc.us/cwmain/rest/services/Stormwater/MapServer

  Wilmington                          https://gis.wilmingtonnc.gov/arcgis/rest/services/PubSvc/Stormwater_Inventory/MapServer/

  Winston-Salem                       https://maps.co.forsyth.nc.us/arcgis/rest/services/Stormwater/SW_Reference/MapServer

  Apex                                https://gis.apexnc.org/server/rest/services/Operational/Apex_Stormwater/MapServer

  Charlotte Pipes                     https://gis.charlottenc.gov/arcgis/rest/services/STM/StormPipes/MapServer

  Charlotte Structures                https://gis.charlottenc.gov/arcgis/rest/services/STM/StormStructures/MapServer

  Asheville Pipes                     https://gis.ashevillenc.gov/server/rest/services/Stormwater/StormwaterLines/MapServer

  Asheville Inlets                    https://gis.ashevillenc.gov/server/rest/services/Stormwater/StormwaterStructure/MapServer
  -----------------------------------------------------------------------------------------------------------------------------------

The configured layer IDs are maintained in `city_configs.py`.

------------------------------------------------------------------------

## 4. Data Download

### Script

`fecthdatabycities.py`

The downloader:

1.  Connects to the municipal ArcGIS REST service.
2.  Retrieves layer metadata.
3.  Retrieves the expected feature count.
4.  Downloads features in batches.
5.  Requests geometry in EPSG:2264.
6.  Converts Esri geometry to Shapely geometry.
7.  Creates a GeoDataFrame.
8.  Saves the downloaded layer as GeoJSON and GeoPackage.
9.  Exports field metadata to CSV.
10. Compares the downloaded count against the ArcGIS feature count.

The downloader uses ArcGIS REST `/query` requests with `resultOffset`
and `resultRecordCount` to retrieve large layers in batches.

### Download QA

For each layer, the script reports:

-   ArcGIS feature count
-   Downloaded feature count
-   Valid feature count
-   PASS/FAIL status
-   Output file locations

A PASS is reported when the ArcGIS feature count and downloaded feature
count are equal.

------------------------------------------------------------------------

## 5. Data Preprocessing

### Script

`final_code_to_extract.py`

The preprocessing script reads:

``` text
geopackage/
    City/
        Inlets.gpkg
        Pipes.gpkg
```

for each configured city.

The processing standardizes the datasets and generates final pipe and
inlet layers.

------------------------------------------------------------------------

## 6. Coordinate Reference System

The preprocessing workflow uses:

**EPSG:2264 --- North Carolina State Plane, US Survey Feet**

Both inlet and pipe layers are converted to this projected coordinate
system before spatial connectivity calculations.

This allows distances between pipe endpoints and inlet locations to be
calculated in feet.

The inlet output also contains:

-   `X_ft`
-   `Y_ft`

These are the projected X/Y coordinates in feet.

------------------------------------------------------------------------

## 7. Inlet Standardization

Each city can use a different source field as its inlet identifier.

The city configuration specifies the appropriate inlet ID field.

The preprocessing script:

1.  Creates a standardized `ID` field.
2.  Removes records without an ID.
3.  Creates `X_ft` and `Y_ft`.
4.  Removes duplicate inlet IDs.
5.  Retains only inlets connected to the final pipe network.

------------------------------------------------------------------------

## 8. Connectivity Methods

Connectivity is handled differently depending on the information
available in the source data.

### Existing Connectivity

Used for:

-   Charlotte
-   Winston-Salem

The source upstream and downstream fields are mapped to:

-   `From_ID`
-   `To_ID`

No nearest-neighbor connectivity is generated for these cities.

### KDTree Connectivity

Used for:

-   Raleigh
-   Greensboro
-   Apex
-   Asheville
-   Fayetteville

The process is:

``` text
Pipe Geometry
     |
     v
Extract Pipe Start/End Points
     |
     v
Build KDTree from Inlet Coordinates
     |
     v
Nearest Inlet Search
     |
     +----> From_ID
     |
     +----> To_ID
```

The nearest inlet is selected independently for the pipe start and pipe
end.

For KDTree cities, the script also calculates:

-   `From_Distance_ft`
-   `To_Distance_ft`
-   `Max_Distance_ft`

### Hybrid Connectivity

Used for:

-   Wilmington

Existing upstream/downstream IDs are used when available.

For missing connectivity values, KDTree nearest-neighbor matching is
used to fill the missing IDs.

------------------------------------------------------------------------

## 9. Distance-Based QA

For KDTree cities, the preprocessing script evaluates the distance
between each pipe endpoint and its assigned inlet.

The maximum of the two endpoint distances is stored as:

`Max_Distance_ft`

The script reports the number of pipe matches in the following ranges:

-   0 ft

-   0--1 ft

-   1--2 ft

-   2--3 ft

A **3-foot maximum endpoint distance** is currently used for KDTree
matching.

Pipes are retained when both:

``` text
From_Distance_ft <= 3 ft
To_Distance_ft <= 3 ft
```

The IQR-based thresholding approach was not used in the final
preprocessing workflow.

------------------------------------------------------------------------

## 10. Data Cleaning

After connectivity is generated, the preprocessing script performs
additional cleaning.

### Self-loop removal

Connections where:

``` text
From_ID == To_ID
```

are removed.

### ID validation

Only pipe connections whose `From_ID` and `To_ID` exist in the inlet ID
set are retained.

### Duplicate connection removal

Duplicate pipe connections between the same pair of inlet IDs are
removed.

### Connected inlet filtering

Only inlets appearing in the final pipe connectivity are retained in the
final inlet layer.

------------------------------------------------------------------------

## 11. QA and Verification

The preprocessing workflow reports:

-   Input inlet count
-   Input pipe count
-   Final inlet count
-   Final pipe count
-   Unique From_ID count
-   Unique To_ID count
-   Unique connected inlet count
-   Average pipes per inlet
-   Distance statistics for KDTree cities
-   Removed pipe count and percentage for KDTree cities

The final output can also be opened and reviewed in QGIS.

Random pipe connections were manually reviewed during the development
and validation process.

------------------------------------------------------------------------

## 12. Final Outputs

For each processed city, the final GeoPackage is stored under:

``` text
geopackage/
    City/
        Final/
            City.gpkg
```

Each final GeoPackage contains two layers:

### Inlets

Fields include:

-   `ID`
-   `lat`
-   `lon`
-   `X_ft`
-   `Y_ft`
-   `geometry`

### Pipes

For existing-connectivity cities:

-   `From_ID`
-   `To_ID`
-   `geometry`

For KDTree cities:

-   `From_ID`
-   `To_ID`
-   `From_Distance_ft`
-   `To_Distance_ft`
-   `Max_Distance_ft`
-   `geometry`

------------------------------------------------------------------------

## 13. QA Report

The preprocessing script creates:

``` text
geopackage/
    All_Cities_QA_Report.csv
```

The report summarizes the input and final record counts and processing
information for each city.

------------------------------------------------------------------------

## 14. Suggested Repository Structure

``` text
Stormwater_Project/
│
├── README.md
│
├── Data_Collection/
│   ├── fecthdatabycities.py
│   └── city_configs.py
│
├── Preprocessing/
│   └── final_code_to_extract.py
│
├── Data/
│   └── geopackage/
│       ├── Charlotte/
│       ├── WinstonSalem/
│       ├── Raleigh/
│       ├── Greensboro/
│       ├── Apex/
│       ├── Asheville/
│       ├── Fayetteville/
│       └── Wilmington/
│
└── Documentation/
    └── Project_Presentation.pptx
```

------------------------------------------------------------------------

## 15. Software Requirements

Recommended environment:

-   Python 3.11+
-   GeoPandas
-   Pandas
-   NumPy
-   SciPy
-   Shapely
-   Matplotlib
-   Requests

Install the main dependencies with:

``` bash
pip install geopandas pandas numpy scipy shapely matplotlib requests
```

------------------------------------------------------------------------

## 16. Running the Workflow

### Step 1 --- Configure data sources

Update:

``` text
city_configs.py
```

with the appropriate ArcGIS REST service URLs and layer IDs.

### Step 2 --- Download source data

Run the data collection script:

``` bash
python fecthdatabycities.py
```

Verify the download QA output.

### Step 3 --- Organize input datasets

Place the inlet and pipe GeoPackages in:

``` text
geopackage/
    <CITY_NAME>/
        Inlets.gpkg
        Pipes.gpkg
```

Replace `<CITY_NAME>` with the city you configured in `fecthdatabycities.py`. Rename pipes and chosen inlets to match `Pipes.gpkg` and `Inlets.gpkg`.

### Step 4 --- Run preprocessing

Run:

``` bash
python final_code_to_extract.py
```

### Step 5 --- Review outputs

Check:

``` text
geopackage/City/Final/City.gpkg
```

and:

``` text
geopackage/All_Cities_QA_Report.csv
```

------------------------------------------------------------------------

## 17. Notes

-   Source datasets differ between municipalities, so city-specific
    inlet ID and connectivity fields are maintained in the
    configuration.
-   Existing connectivity is preferred when reliable upstream/downstream
    IDs are available.
-   KDTree is used when explicit connectivity is unavailable.
-   Wilmington uses a hybrid approach because existing connectivity is
    available for part of the dataset and missing values require spatial
    matching.
-   The final preprocessing workflow does not use the earlier IQR-based
    distance threshold approach.
