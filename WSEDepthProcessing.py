#########################
# Processing Script For #
#  HEC-RAS Flood Grids  #
#  By: Patrick O'Shea   #
#########################

# For this script to work, users will need to meet these conditions:
#
# 1) Have an arcgispro python environment
#    - This should come with an arcgis pro licence
#    - The typical path where this environment should be is: C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3
# 
# 2) Have the spatial analyst extension for arcgis pro
# 
# 3) Have all of the depth grids from HEC-RAS saved in a single folder as geotiffs
# 
# 4) create both a temp folder and an output folder for storing files    

# Import packages
import arcpy
import os
import re

# Set your input/output folders
input_folder = r"PATH TO DEPTH GRID FOLDER" # path to where depth grids are stored
output_folder = r"PATH TO OUTPUT FOLDER" # output folder path
temp_gdb = r"PATH TO TEMP GEODATABASE" # temporary path NEEDS TO BE A GEODATABASE

# Set Environment settings
arcpy.env.workspace = input_folder
arcpy.env.overwriteOutput = True

# Get list of all depth grids in the folder, this assumes that they are saved as geotiffs
tif_files = arcpy.ListRasters("*.tif")

# Initiate loop to go through all geotiffs
for tif in tif_files:
    print(f"Processing {tif}...")

    # Extract the base name from the geotiff and then clean it up for processing
    base_name = os.path.splitext(tif)[0]
    base_name_clean = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)[:40]  # keep under 40 chars

    # Establish paths for intermediate and final output files
    int_raster = os.path.join(temp_gdb,  base_name_clean + "_int.tif")
    polygon = os.path.join(temp_gdb, base_name_clean + "_poly")
    dissolved = os.path.join(temp_gdb,  base_name_clean + "_dissolved")
    singleparts = os.path.join(temp_gdb,  base_name_clean + "_singleparts")
    WSE_polygon = os.path.join(output_folder,  base_name_clean + "_WSE")
    final_output = os.path.join(output_folder,  base_name_clean + "_Depth.tif")

    # Processing Steps: 
    # 1) Convert raster to integer (required to convert raster to polygon tool)
    arcpy.sa.Int(tif).save(int_raster)

    # 2) Convert integer raster to polygon
    arcpy.conversion.RasterToPolygon(int_raster, polygon, "NO_SIMPLIFY", "Value")

    # 3) Dissolve polygons (this merges into a single multipart polygon)
    arcpy.management.Dissolve(polygon, dissolved)

    # 4. Break multipart polygon into single parts
    arcpy.management.MultipartToSinglepart(dissolved, singleparts)

    # 5. Find and keep only the polygon with the largest area (assumed that the largest polygon is the river flooding 
    #    and that all other polygons are hydraulically disconnected)

    # Start by adding an area field
    arcpy.management.AddGeometryAttributes(singleparts, "AREA", Area_Unit="SQUARE_METERS")

    # Use a search cursor to find the largest area feature
    max_area = 0
    max_oid = None
    with arcpy.da.SearchCursor(singleparts, ["OID@", "Shape_Area"]) as cursor:
        for oid, area in cursor:
            if area > max_area:
                max_area = area
                max_oid = oid

    # Create a feature layer from the singleparts feature class
    arcpy.management.MakeFeatureLayer(singleparts, "singleparts_lyr")   
    expression = f'OBJECTID = {max_oid}'
    arcpy.management.SelectLayerByAttribute("singleparts_lyr", "NEW_SELECTION", expression)
    arcpy.management.CopyFeatures("singleparts_lyr", WSE_polygon)

    # 6. Extract by mask using the selected polygon and original raster
    arcpy.sa.ExtractByMask(tif, WSE_polygon).save(final_output)

    print(f"Finished: {final_output}")

    # 7. Clean up intermediate files in the temp folder
    for file in [int_raster, polygon, dissolved, singleparts]:
        try:
            if arcpy.Exists(file):
                arcpy.mangement.Delete(file)
                print(f"Deleted temp file: {file}")

        except Exception as error:
            print(f"Could not delete {file}: {error}")


print("All rasters processed.")