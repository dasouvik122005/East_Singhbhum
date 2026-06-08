# File: grace_east_singhbhum_export.py

import os
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rioxarray
import xarray as xr
from rasterio.crs import CRS
from rasterio.transform import from_origin
from shapely.geometry import mapping

warnings.filterwarnings("ignore")

# ==========================================

# INPUT FILES

# ==========================================

nc_file = r"C:\Users\souvi\Desktop\Program\east_singhbum\grace\CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc"

shp_file = r"C:\Users\souvi\Desktop\Program\east_singhbum\shapefile\East_singhum_wgs.shp"

output_dir = r"C:\Users\souvi\Desktop\Program\east_singhbum\output"

os.makedirs(output_dir, exist_ok=True)

# ==========================================

# READ GRACE NETCDF

# ==========================================

ds = xr.open_dataset(nc_file, mask_and_scale=True)

lwe = ds["lwe_thickness"]

dates = pd.to_datetime("2002-01-01") + pd.to_timedelta(
ds["time"].values,
unit="D"
)

lwe = (
lwe.assign_coords(
lon=((lwe.lon + 180) % 360) - 180
)
.sortby("lon")
)

lwe = lwe.assign_coords(time=("time", dates))

if "grid_mapping" in lwe.attrs:
    del lwe.attrs["grid_mapping"]

# ==========================================

# READ DISTRICT SHAPEFILE

# ==========================================

district = gpd.read_file(shp_file)

if district.crs is None:
    district = district.set_crs("EPSG:4326")

district = district.to_crs("EPSG:4326")

district_geom = district.unary_union

# ==========================================

# CROP USING DISTRICT BOUNDS

# ==========================================

xmin, ymin, xmax, ymax = district.total_bounds

buffer = 0.5

lwe_crop = lwe.sel(
lon=slice(xmin - buffer, xmax + buffer),
lat=slice(ymin - buffer, ymax + buffer)
)

# ==========================================

# CRS AND CLIP

# ==========================================

lwe_crop = (
lwe_crop
.rio.set_spatial_dims(
x_dim="lon",
y_dim="lat"
)
.rio.write_crs("EPSG:4326")
)

lwe_clip = lwe_crop.rio.clip(
[mapping(district_geom)],
"EPSG:4326",
drop=True,
all_touched=True
)

# ==========================================

# GEOTIFF SETTINGS

# ==========================================

lat_vals = lwe_clip.lat.values
lon_vals = lwe_clip.lon.values

xres = abs(float(lon_vals[1] - lon_vals[0]))
yres = abs(float(lat_vals[1] - lat_vals[0]))

transform = from_origin(
float(lon_vals.min()) - xres / 2,
float(lat_vals.max()) + yres / 2,
xres,
yres
)

# ==========================================

# EXPORT TIFFS

# ==========================================

for i in range(lwe_clip.sizes["time"]):
    current_date = pd.Timestamp(
        lwe_clip.time.values[i]
    )

    output_file = os.path.join(
        output_dir,
        f"{current_date:%Y_%m}_East_Singhbhum_TWSA.tif"
    )

    data = (
        lwe_clip
        .isel(time=i)
        .values
        .astype(np.float32)
    )

    if lat_vals[0] < lat_vals[-1]:
        data = np.flipud(data)

    data[np.isnan(data)] = -9999.0

    with rasterio.open(
        output_file,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=-9999.0,
        compress="LZW",
    ) as dst:

        dst.write(data, 1)

        dst.update_tags(
            date=current_date.strftime("%Y-%m-%d"),
            units="cm",
            variable="lwe_thickness",
            region="East Singhbhum",
            mission="GRACE"
            if current_date.year < 2018
            else "GRACE-FO",
        )

    print(f"Saved: {output_file}")

print("\nFinished exporting all East Singhbhum GRACE GeoTIFFs.")
