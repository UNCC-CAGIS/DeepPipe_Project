CITY_CONFIG = {

    "Raleigh": {
        "url": "https://maps.raleighnc.gov/arcgis/rest/services/PublicWorks/Stormwater/MapServer",
        "layers": [0, 1, 2, 8, 11],
        "layer_roles": {
            0: "inlet",
            1: "junction",
            2: "IO",
            8: "channel",
            11: "pipe"
        }
    },

    "Greensboro": {
        "url": "https://gis.greensboro-nc.gov/arcgis/rest/services/WaterResources/StormwaterRAIN_MS/MapServer",
        "layers": [21, 22, 23, 24, 30]
    },

    "Fayetteville": {
        "url": "https://gismaps.ci.fayetteville.nc.us/cwmain/rest/services/Stormwater/MapServer",
        "layers": [2, 4, 5],
        "layer_roles": {
            2: "structure",
            4: "channel",
            5: "pipe"
        }
    },
    "Wilmington": {
        "url": "https://gis.wilmingtonnc.gov/arcgis/rest/services/PubSvc/Stormwater_Inventory/MapServer/",
        "layers": [0, 3]
    },
    "WinstonSalem": {
        "url": "https://maps.co.forsyth.nc.us/arcgis/rest/services/Stormwater/SW_Reference/MapServer",
        "layers": [0, 1]
    },

    "Apex": {
        "url": "https://gis.apexnc.org/server/rest/services/Operational/Apex_Stormwater/MapServer",
        "layers": [3, 4, 10, 12]
    },

    "Charlotte_Pipes": {
        "url": "https://gis.charlottenc.gov/arcgis/rest/services/STM/StormPipes/MapServer",
        "layers": [0]
    },

    "Charlotte_Structures": {
        "url": "https://gis.charlottenc.gov/arcgis/rest/services/STM/StormStructures/MapServer",
        "layers": [0]
    },

    "Asheville_Pipes": {
        "url": "https://gis.ashevillenc.gov/server/rest/services/Stormwater/StormwaterLines/MapServer",
        "layers": [1]
    },

    "Asheville_Inlets": {
        "url": "https://gis.ashevillenc.gov/server/rest/services/Stormwater/StormwaterStructure/MapServer",
        "layers": [39, 9, 38, 11]
    }
}