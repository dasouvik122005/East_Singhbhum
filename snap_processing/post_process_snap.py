import os
import glob
import re
import argparse
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
import rasterio
from rasterio.mask import mask
import geopandas as gpd
from shapely.geometry import mapping

# Sentinel-1 radar wavelength in mm
S1_WAVELENGTH_MM = 55.462

def parse_args():
    parser = argparse.ArgumentParser(description="Post-process SNAP unwrapped phase stack and validate with wells")
    parser.add_index = parser.add_argument
    parser.add_index("--insar_file", type=str, required=True, 
                        help="Path to SNAP unwrapped stack product (.dim file)")
    parser.add_index("--well_file", type=str, required=True, 
                        help="Path to CGWB well water level Excel file")
    parser.add_index("--shapefile", type=str, required=True, 
                        help="Path to East Singhbhum district shapefile")
    parser.add_index("--out_dir", type=str, default="../results", 
                        help="Directory to save final figures and tables")
    parser.add_index("--incidence_angle", type=float, default=39.7, 
                        help="Radar incidence angle in degrees (default: 39.7)")
    return parser.parse_args()

def parse_dates_from_band(filename):
    match = re.search(r'MST_(\d{8})_SLV_(\d{8})', filename)
    if match:
        return match.group(1), match.group(2)
        
    match2 = re.search(r'Unw_Phase_ifg_(\d{2}[A-Za-z]{3}\d{4})_(\d{2}[A-Za-z]{3}\d{4})', filename)
    if match2:
        try:
            m_dt = datetime.strptime(match2.group(1), "%d%b%Y")
            s_dt = datetime.strptime(match2.group(2), "%d%b%Y")
            return m_dt.strftime("%Y%m%d"), s_dt.strftime("%Y%m%d")
        except ValueError:
            pass
            
    return None

def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    
    print("=" * 70)
    print(" SNAP InSAR Post-Processing & Validation")
    print("=" * 70)
    
    # Check inputs
    dim_path = args.insar_file
    if not os.path.exists(dim_path):
        print(f"Error: SNAP .dim file not found at: {dim_path}")
        return
        
    data_dir = dim_path.replace(".dim", ".data")
    if not os.path.exists(data_dir):
        print(f"Error: SNAP .data folder not found at: {data_dir}")
        print("Please make sure SNAP has generated the data bands.")
        return
        
    # Step 1: Scan unwrapped phase raster bands
    print(f"Scanning data directory: {data_dir}")
    # ENVI raw image files have .img extension
    unw_files = sorted(glob.glob(os.path.join(data_dir, "Unw_Phase_*.img")))
    cc_files = sorted(glob.glob(os.path.join(data_dir, "coh_*.img")))
    
    print(f"Found {len(unw_files)} unwrapped phase bands.")
    print(f"Found {len(cc_files)} coherence bands.")
    
    if len(unw_files) == 0:
        print("Error: No unwrapped phase bands (.img) found. Make sure you unwrapped and imported the phase.")
        return
        
    # Step 2: Load district shapefile
    print(f"\n[1/5] Loading district shapefile: {args.shapefile}")
    gdf = gpd.read_file(args.shapefile)
    geom = [mapping(g) for g in gdf.geometry]
    
    # Step 3: Extract time-series and average velocity
    print("\n[2/5] Reading phase raster bands and converting to vertical displacement...")
    rad_to_mm = - S1_WAVELENGTH_MM / (4.0 * np.pi)
    cos_theta = np.cos(np.radians(args.incidence_angle))
    
    # We will accumulate displacement over time for each pixel
    # Sort pairs based on slave dates
    pairs_data = []
    for f in unw_files:
        dates = parse_dates_from_band(f)
        if dates:
            m_date, s_date = dates
            pairs_data.append((datetime.strptime(s_date, "%Y%m%d"), m_date, s_date, f))
            
    pairs_data = sorted(pairs_data, key=lambda x: x[0])
    
    # Read first band to establish shape and geotransform
    first_band_path = pairs_data[0][3]
    with rasterio.open(first_band_path) as src:
        # Mask to shapefile
        out_image, out_transform = mask(src, geom, crop=True, nodata=-9999.0)
        out_meta = src.profile.copy()
        
    rows, cols = out_image[0].shape
    print(f"      Grid size: {cols} cols × {rows} rows")
    
    # Accumulators
    M = len(pairs_data)
    disp_vertical_stack = np.full((M + 1, rows, cols), np.nan, dtype=np.float32)
    disp_vertical_stack[0] = 0.0 # start date has 0 displacement
    
    dates_list = [datetime.strptime(pairs_data[0][1], "%Y%m%d")] # start with Master date
    
    for idx, (dt, m_date, s_date, f) in enumerate(pairs_data):
        dates_list.append(dt)
        print(f"      Reading band {idx+1}/{M}: MST {m_date} -> SLV {s_date}")
        with rasterio.open(f) as src:
            img, _ = mask(src, geom, crop=True, nodata=-9999.0)
            img = img[0].astype(np.float32)
            img[img == -9999.0] = np.nan
            
            # Convert phase (radians) to vertical displacement (mm)
            disp_los = img * rad_to_mm
            disp_vert = disp_los / cos_theta
            
            disp_vertical_stack[idx + 1] = disp_vert
            
    # Calculate average velocity (mm/year) for each pixel
    print("\n[3/5] Calculating average vertical velocity map...")
    t_years = np.array([(d - dates_list[0]).days / 365.25 for d in dates_list])
    
    velocity_map = np.full((rows, cols), np.nan, dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            ts = disp_vertical_stack[:, r, c]
            valid = ~np.isnan(ts)
            if np.sum(valid) > 2:
                # Linear regression fit to get velocity (slope)
                slope, _ = np.polyfit(t_years[valid], ts[valid], 1)
                velocity_map[r, c] = slope
                
    # Save the vertical velocity map as GeoTIFF
    out_meta.update({
        "height": rows,
        "width": cols,
        "transform": out_transform,
        "nodata": -9999.0,
        "dtype": "float32",
        "count": 1
    })
    vel_output_path = os.path.join(os.path.dirname(args.insar_file), "insar_vertical_velocity_clipped.tif")
    with rasterio.open(vel_output_path, "w", **out_meta) as dst:
        dst.write(np.where(np.isnan(velocity_map), -9999.0, velocity_map).astype(np.float32), 1)
    print(f"      Vertical velocity map saved: {os.path.basename(vel_output_path)}")
    
    # Step 4: Block-wise statistics
    print("\n[4/5] Extracting block-wise zonal statistics...")
    has_blocks = 'BLOCK' in gdf.columns or 'block' in gdf.columns
    block_col = 'BLOCK' if 'BLOCK' in gdf.columns else 'block' if 'block' in gdf.columns else None
    
    block_insar_rates = {}
    if block_col:
        for idx, row in gdf.iterrows():
            block_name = row[block_col]
            block_geom = [mapping(row.geometry)]
            with rasterio.open(vel_output_path) as src:
                try:
                    block_img, _ = mask(src, block_geom, crop=True, nodata=-9999.0)
                    block_img = block_img[0]
                    block_img[block_img == -9999.0] = np.nan
                    avg_rate = np.nanmean(block_img)
                    if not np.isnan(avg_rate):
                        block_insar_rates[block_name] = avg_rate
                except ValueError:
                    pass
                    
    # Step 5: Well Validation & Plotting
    print("\n[5/5] Correlating displacement timeseries with well water levels...")
    with np.errstate(all='ignore'):
        insar_mean_ts = np.nanmean(disp_vertical_stack, axis=(1, 2))
    insar_mean_ts = np.nan_to_num(insar_mean_ts, nan=0.0)
    
    # Load CGWB Well data
    df_well = pd.read_excel(args.well_file)
    df_well['Date'] = pd.to_datetime(df_well['Date'])
    wl_monthly = df_well.groupby("Date")["WL(mbgl)"].mean().reset_index().sort_values("Date")
    
    overlap_mask = (wl_monthly["Date"] >= min(dates_list)) & (wl_monthly["Date"] <= max(dates_list))
    wl_overlap = wl_monthly[overlap_mask].copy()
    
    df_insar_ts = pd.DataFrame({"Date": dates_list, "InSAR_disp": insar_mean_ts})
    merged = pd.merge_asof(
        wl_overlap.sort_values("Date"),
        df_insar_ts.sort_values("Date"),
        on="Date",
        tolerance=pd.Timedelta("45D"),
        direction="nearest"
    ).dropna(subset=["InSAR_disp", "WL(mbgl)"])
    
    r_corr, p_corr = np.nan, np.nan
    if len(merged) > 3:
        r_corr, p_corr = stats.pearsonr(merged["InSAR_disp"], -merged["WL(mbgl)"])
        print(f"      Pearson Correlation: r = {r_corr:.3f} (p = {p_corr:.2e})")
        
    # Plot Figure 7: Velocity Map
    print("\n  Generating Figure 7: InSAR Vertical Velocity Map...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    vmax = np.nanmax(np.abs(velocity_map)) if not np.isnan(np.nanmax(velocity_map)) else 5.0
    if vmax == 0:
        vmax = 5.0
    im = ax.imshow(velocity_map, cmap="RdYlBu", vmin=-vmax, vmax=vmax,
                   extent=[
                       out_transform.c, out_transform.c + out_transform.a * cols,
                       out_transform.f + out_transform.e * rows, out_transform.f
                   ])
    gdf.boundary.plot(ax=ax, color="black", linewidth=1.2)
    ax.set_title("Sentinel-1 InSAR Vertical Deformation Rate — East Singhbhum\n(SNAP GPT InSAR Pipeline, 2026)", fontsize=12, pad=10)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    cbar = plt.colorbar(im, ax=ax, label="Deformation Rate (mm/year)", shrink=0.8, pad=0.03)
    
    fig7_path = os.path.join(args.out_dir, "Fig7_InSAR_vertical_velocity_map.png")
    fig.savefig(fig7_path, bbox_inches="tight")
    plt.close()
    print(f"      Saved: Fig7_InSAR_vertical_velocity_map.png")
    
    # Plot Figure 8: Timeseries Comparison
    print("  Generating Figure 8: InSAR vs Well WL Time-Series...")
    fig, ax1 = plt.subplots(figsize=(10, 5), dpi=300)
    color1 = "#4F46E5"
    ax1.plot(dates_list, insar_mean_ts, color=color1, linewidth=2, label="InSAR Cumulative Disp. (mm)")
    ax1.fill_between(dates_list, insar_mean_ts, alpha=0.1, color=color1)
    ax1.set_xlabel("Year")
    ax1.set_ylabel("InSAR Cumulative Vertical Displacement (mm)", color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.grid(True, linestyle="--", alpha=0.5)
    
    ax2 = ax1.twinx()
    color2 = "#DC2626"
    ax2.plot(wl_overlap["Date"], wl_overlap["WL(mbgl)"], color=color2, linewidth=1.5, marker="o", markersize=4, linestyle="--", alpha=0.8, label="Well WL (mbgl)")
    ax2.set_ylabel("Well Groundwater Level (m bgl)", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.invert_yaxis()
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)
    ax1.xaxis.set_major_locator(mdates.YearLocator(1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    
    if not np.isnan(r_corr):
        corr_text = f"Pearson r = {r_corr:.3f}\n(p = {p_corr:.2e})\nOverlapping period"
        ax1.text(0.02, 0.05, corr_text, transform=ax1.transAxes, fontsize=9,
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray", alpha=0.8))
                 
    ax1.set_title("Validation: InSAR Ground Deformation vs. Well Groundwater Table (SNAP)", fontsize=11, pad=10)
    plt.tight_layout()
    fig8_path = os.path.join(args.out_dir, "Fig8_InSAR_vs_Groundwater_TimeSeries.png")
    fig.savefig(fig8_path, bbox_inches="tight")
    plt.close()
    print(f"      Saved: Fig8_InSAR_vs_Groundwater_TimeSeries.png")
    
    # Save Summary Table
    print("  Creating summary CSV table...")
    well_summary_path = os.path.join(args.out_dir, "subsidence_summary.csv")
    if os.path.exists(well_summary_path):
        df_well_sub = pd.read_csv(well_summary_path)
        df_well_sub["InSAR_Subsidence_Rate_mm_yr"] = df_well_sub["Block"].map(block_insar_rates)
        final_summary_path = os.path.join(args.out_dir, "insar_block_summary.csv")
        df_well_sub.to_csv(final_summary_path, index=False)
        print(f"      Saved: insar_block_summary.csv")
    else:
        df_simple = pd.DataFrame(list(block_insar_rates.items()), columns=["Block", "InSAR_Subsidence_Rate_mm_yr"])
        final_summary_path = os.path.join(args.out_dir, "insar_block_summary.csv")
        df_simple.to_csv(final_summary_path, index=False)
        print(f"      Saved: insar_block_summary.csv")
        
    print("\nPost-Processing and Validation Complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
