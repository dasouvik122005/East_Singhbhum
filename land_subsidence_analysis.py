# =============================================================================
# Land Subsidence Analysis — East Singhbhum District, Jharkhand
# =============================================================================
# Combines:
#   1. GRACE/GRACE-FO TWSA monthly rasters (2002–2026)
#   2. CGWB Well Water Level observations (1994–2024)
#
# Outputs:
#   - Figure 1: TWSA time series with trend
#   - Figure 2: Well water level time series (all blocks)
#   - Figure 3: Combined TWSA vs Well Water Level (dual axis)
#   - Figure 4: Block-wise groundwater level trends
#   - Figure 5: Pixel-wise TWSA trend map (Sen's slope)
#   - Figure 6: Estimated land subsidence map
#   - CSV:      Summary statistics table
# =============================================================================

import os
import glob
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from matplotlib.ticker import AutoMinorLocator
from scipy import stats
import rasterio
from rasterio.plot import show as rshow
import pymannkendall as mk

warnings.filterwarnings("ignore")

# ---------- nice plot style ----------
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "#f9f9f9",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

# =====================================================================
# CONFIGURATION — Adjust these parameters
# =====================================================================

# File paths
TWSA_DIR = r"C:\Users\souvi\Desktop\Program\east_singhbum\output"
WELL_FILE = r"C:\Users\souvi\Desktop\Program\east_singhbum\East Singhbum_1354.xlsx"
OUTPUT_DIR = r"C:\Users\souvi\Desktop\Program\east_singhbum\results"

# Aquifer parameters for East Singhbhum (hard-rock terrain)
# These are typical values for the Chotanagpur Plateau / Singhbhum Craton
# Adjust based on CGWB district reports if available
Sy = 0.03          # Specific Yield (dimensionless) — typical for hard rock: 0.01–0.05
Ssk = 5e-5         # Skeletal specific storage (m⁻¹) — typical: 1e-5 to 1e-3
AQUIFER_THICKNESS = 20.0   # Aquifer thickness in meters — weathered zone: 10–30 m

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print(" LAND SUBSIDENCE ANALYSIS — EAST SINGHBHUM")
print("=" * 70)

# =====================================================================
# PART 1: Load GRACE TWSA rasters
# =====================================================================

print("\n[1/6] Loading GRACE TWSA rasters...")

tif_files = sorted(glob.glob(os.path.join(TWSA_DIR, "*_East_Singhbhum_TWSA.tif")))
print(f"      Found {len(tif_files)} TWSA GeoTIFF files.")

twsa_dates = []
twsa_means = []
twsa_arrays = []
profile_ref = None

for f in tif_files:
    basename = os.path.basename(f)
    # Parse date from filename: "2002_04_East_Singhbhum_TWSA.tif"
    parts = basename.split("_")
    year, month = int(parts[0]), int(parts[1])
    twsa_dates.append(datetime(year, month, 15))  # mid-month

    with rasterio.open(f) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata
        if profile_ref is None:
            profile_ref = src.profile.copy()
            ref_transform = src.transform
            ref_shape = data.shape

        # Mask nodata
        data[data == nodata] = np.nan
        twsa_arrays.append(data)
        twsa_means.append(np.nanmean(data))

twsa_dates = np.array(twsa_dates)
twsa_means = np.array(twsa_means)
twsa_stack = np.stack(twsa_arrays, axis=0)  # shape: (time, rows, cols)

print(f"      Date range: {twsa_dates[0]:%Y-%m} to {twsa_dates[-1]:%Y-%m}")
print(f"      Raster shape: {ref_shape[0]} rows × {ref_shape[1]} cols")
print(f"      Mean TWSA range: {np.nanmin(twsa_means):.2f} to {np.nanmax(twsa_means):.2f} cm")

# =====================================================================
# PART 2: Load Well Water Level data
# =====================================================================

print("\n[2/6] Loading CGWB Well Water Level data...")

df_well = pd.read_excel(WELL_FILE)
df_well["Date"] = pd.to_datetime(df_well["Date"])
df_well = df_well.sort_values("Date")

print(f"      Total records: {len(df_well)}")
print(f"      Date range: {df_well['Date'].min():%Y-%m} to {df_well['Date'].max():%Y-%m}")
print(f"      Blocks: {df_well['BLOCK'].nunique()}")
print(f"      Villages: {df_well['VILLAGE'].nunique()}")

# Compute district-wide mean water level per date
wl_monthly = df_well.groupby("Date")["WL(mbgl)"].agg(["mean", "std", "count"]).reset_index()
wl_monthly.columns = ["Date", "WL_mean", "WL_std", "WL_count"]

# Block-wise mean
wl_block = df_well.groupby(["Date", "BLOCK"])["WL(mbgl)"].mean().reset_index()

# =====================================================================
# FIGURE 1: GRACE TWSA Time Series with Trend
# =====================================================================

print("\n[3/6] Plotting TWSA time series...")

fig, ax = plt.subplots(figsize=(14, 5))

# Convert dates to numeric for regression
x_num = mdates.date2num(twsa_dates)
slope, intercept, r_value, p_value, std_err = stats.linregress(x_num, twsa_means)
trend_line = slope * x_num + intercept

# Sen's slope on the mean time series
mk_result = mk.original_test(twsa_means)

ax.plot(twsa_dates, twsa_means, color="#2563EB", linewidth=1.2, alpha=0.8, label="Monthly TWSA")
ax.plot(twsa_dates, trend_line, color="#DC2626", linewidth=2, linestyle="--",
        label=f"Linear trend: {slope * 365.25:.3f} cm/yr (p={p_value:.2e})")

ax.fill_between(twsa_dates, twsa_means, alpha=0.15, color="#2563EB")
ax.axhline(0, color="gray", linewidth=0.8, linestyle="-")

ax.set_xlabel("Year")
ax.set_ylabel("TWSA (cm of water equivalent)")
ax.set_title("GRACE/GRACE-FO Total Water Storage Anomaly — East Singhbhum District")
ax.legend(loc="upper right", framealpha=0.9)
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.xaxis.set_minor_locator(mdates.YearLocator(1))

# Annotate MK result
mk_text = f"Mann-Kendall: τ = {mk_result.Tau:.3f}, trend = {mk_result.trend}"
ax.text(0.02, 0.05, mk_text, transform=ax.transAxes,
        fontsize=9, bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"))

plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "Fig1_TWSA_timeseries.png"), bbox_inches="tight")
plt.close()
print("      Saved: Fig1_TWSA_timeseries.png")

# =====================================================================
# FIGURE 2: Well Water Level Time Series (by Block)
# =====================================================================

print("\n[4/6] Plotting Well Water Level time series...")

blocks = sorted(df_well["BLOCK"].unique())
# Use a nice colormap
cmap = plt.cm.get_cmap("tab10", len(blocks))

fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

# Panel A: District-wide mean
ax = axes[0]
ax.plot(wl_monthly["Date"], wl_monthly["WL_mean"], color="#0F766E",
        linewidth=1.5, marker="o", markersize=3, label="District mean WL")
ax.fill_between(wl_monthly["Date"],
                wl_monthly["WL_mean"] - wl_monthly["WL_std"],
                wl_monthly["WL_mean"] + wl_monthly["WL_std"],
                alpha=0.2, color="#0F766E", label="±1 Std Dev")

# Trend line
x_wl = mdates.date2num(wl_monthly["Date"])
sl_wl, int_wl, r_wl, p_wl, _ = stats.linregress(x_wl, wl_monthly["WL_mean"])
ax.plot(wl_monthly["Date"], sl_wl * x_wl + int_wl, color="#DC2626",
        linewidth=2, linestyle="--",
        label=f"Trend: {sl_wl * 365.25:.3f} m/yr (p={p_wl:.2e})")

ax.set_ylabel("Water Level (m bgl)")
ax.set_title("Groundwater Level — East Singhbhum District (All Wells)")
ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
ax.invert_yaxis()  # deeper = lower on plot

# Panel B: Block-wise
ax = axes[1]
for i, block in enumerate(blocks):
    block_data = wl_block[wl_block["BLOCK"] == block]
    ax.plot(block_data["Date"], block_data["WL(mbgl)"],
            color=cmap(i), linewidth=1, alpha=0.8, marker=".", markersize=2, label=block)

ax.set_xlabel("Year")
ax.set_ylabel("Water Level (m bgl)")
ax.set_title("Groundwater Level by Block")
ax.legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.9)
ax.invert_yaxis()
ax.xaxis.set_major_locator(mdates.YearLocator(3))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "Fig2_WellLevel_timeseries.png"), bbox_inches="tight")
plt.close()
print("      Saved: Fig2_WellLevel_timeseries.png")

# =====================================================================
# FIGURE 3: Combined TWSA vs Well Water Level (Dual Axis)
# =====================================================================

print("\n[5/6] Plotting combined TWSA vs Well Water Level...")

# Filter to overlapping period (2002 onwards)
mask_wl = wl_monthly["Date"] >= "2002-01-01"
wl_overlap = wl_monthly[mask_wl].copy()

fig, ax1 = plt.subplots(figsize=(14, 6))

# TWSA on left axis
color1 = "#2563EB"
ax1.plot(twsa_dates, twsa_means, color=color1, linewidth=1.2, alpha=0.8, label="GRACE TWSA")
ax1.fill_between(twsa_dates, twsa_means, alpha=0.1, color=color1)
ax1.set_xlabel("Year")
ax1.set_ylabel("TWSA (cm water eq.)", color=color1)
ax1.tick_params(axis="y", labelcolor=color1)

# Well WL on right axis (inverted — deeper water = less storage)
ax2 = ax1.twinx()
color2 = "#DC2626"
ax2.plot(wl_overlap["Date"], wl_overlap["WL_mean"], color=color2,
         linewidth=1.5, marker="o", markersize=4, alpha=0.8, label="Well WL (mbgl)")
ax2.set_ylabel("Water Level (m bgl)", color=color2)
ax2.tick_params(axis="y", labelcolor=color2)
ax2.invert_yaxis()  # Invert so that rising WL (storage loss) goes down

ax1.set_title("GRACE TWSA vs Groundwater Level — East Singhbhum (2002–2024)")

# Combined legend
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", framealpha=0.9)

ax1.xaxis.set_major_locator(mdates.YearLocator(2))
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

# Compute correlation between TWSA and WL over overlapping dates
# Resample TWSA to quarterly to match well data
df_twsa = pd.DataFrame({"Date": twsa_dates, "TWSA": twsa_means})
df_twsa["Date"] = pd.to_datetime(df_twsa["Date"])
df_twsa = df_twsa.set_index("Date").resample("QS").mean().dropna().reset_index()

merged = pd.merge_asof(
    wl_overlap.sort_values("Date"),
    df_twsa.sort_values("Date"),
    on="Date",
    tolerance=pd.Timedelta("60D"),
    direction="nearest"
).dropna(subset=["TWSA", "WL_mean"])

if len(merged) > 5:
    r_corr, p_corr = stats.pearsonr(merged["TWSA"], -merged["WL_mean"])
    corr_text = f"Pearson r = {r_corr:.3f} (p = {p_corr:.3e})\n(TWSA vs −WL: negative WL means deeper)"
    ax1.text(0.02, 0.05, corr_text, transform=ax1.transAxes, fontsize=9,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray"))

plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "Fig3_TWSA_vs_WellLevel.png"), bbox_inches="tight")
plt.close()
print("      Saved: Fig3_TWSA_vs_WellLevel.png")

# =====================================================================
# FIGURE 4: Block-wise Groundwater Level Trends (Bar Chart)
# =====================================================================

print("\n      Computing block-wise trends...")

block_trends = []
for block in blocks:
    bdata = df_well[df_well["BLOCK"] == block].copy()
    bdata = bdata.groupby("Date")["WL(mbgl)"].mean().reset_index().sort_values("Date")

    if len(bdata) < 5:
        continue

    x = mdates.date2num(bdata["Date"])
    y = bdata["WL(mbgl)"].values
    sl, intc, r, p, se = stats.linregress(x, y)

    # Mann-Kendall
    try:
        mk_r = mk.original_test(y)
        mk_trend = mk_r.trend
        mk_p = mk_r.p
    except Exception:
        mk_trend = "no trend"
        mk_p = 1.0

    block_trends.append({
        "Block": block,
        "Trend_m_per_yr": sl * 365.25,
        "R_squared": r ** 2,
        "P_value": p,
        "MK_trend": mk_trend,
        "MK_p": mk_p,
        "Mean_WL": y.mean(),
        "N_obs": len(bdata),
    })

df_trends = pd.DataFrame(block_trends).sort_values("Trend_m_per_yr", ascending=False)

fig, ax = plt.subplots(figsize=(12, 6))
colors = ["#DC2626" if t > 0 else "#059669" for t in df_trends["Trend_m_per_yr"]]
bars = ax.barh(df_trends["Block"], df_trends["Trend_m_per_yr"], color=colors, edgecolor="white", height=0.6)

ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel("Water Level Trend (m/year)")
ax.set_title("Block-wise Groundwater Level Trend — East Singhbhum\n(Positive = deepening = depletion)")

for bar, p_val in zip(bars, df_trends["P_value"]):
    sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
    ax.text(bar.get_width() + 0.001, bar.get_y() + bar.get_height() / 2,
            f" {bar.get_width():.4f} {sig}", va="center", fontsize=9)

ax.text(0.02, 0.02, "Significance: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant",
        transform=ax.transAxes, fontsize=8, style="italic")

plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "Fig4_Blockwise_WL_trends.png"), bbox_inches="tight")
plt.close()
print("      Saved: Fig4_Blockwise_WL_trends.png")

# =====================================================================
# FIGURE 5: Pixel-wise TWSA Trend Map (Sen's Slope)
# =====================================================================

print("\n[6/6] Computing pixel-wise TWSA trend (Sen's slope)...")

ntime, nrows, ncols = twsa_stack.shape
trend_map = np.full((nrows, ncols), np.nan, dtype=np.float32)
pval_map = np.full((nrows, ncols), np.nan, dtype=np.float32)

# Time as fractional years for Sen's slope
t_years = np.array([(d - twsa_dates[0]).days / 365.25 for d in twsa_dates])

for r in range(nrows):
    for c in range(ncols):
        pixel_ts = twsa_stack[:, r, c]
        valid = ~np.isnan(pixel_ts)
        if valid.sum() < 10:
            continue
        try:
            result = mk.original_test(pixel_ts[valid])
            trend_map[r, c] = result.slope  # cm/year
            pval_map[r, c] = result.p
        except Exception:
            pass

print(f"      Trend range: {np.nanmin(trend_map):.4f} to {np.nanmax(trend_map):.4f} cm/yr")

# Plot the trend map
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Panel A: Sen's slope
ax = axes[0]
vmax = max(abs(np.nanmin(trend_map)), abs(np.nanmax(trend_map)))
if vmax == 0:
    vmax = 1
im = ax.imshow(trend_map, cmap="RdBu", vmin=-vmax, vmax=vmax,
               extent=[
                   ref_transform.c, ref_transform.c + ref_transform.a * ncols,
                   ref_transform.f + ref_transform.e * nrows, ref_transform.f
               ])
ax.set_title("TWSA Trend (Sen's Slope)\ncm/year (2002–2026)")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
plt.colorbar(im, ax=ax, label="cm/year", shrink=0.8)

# Panel B: Significance mask
ax = axes[1]
sig_mask = np.where(pval_map <= 0.05, trend_map, np.nan)
im2 = ax.imshow(sig_mask, cmap="RdBu", vmin=-vmax, vmax=vmax,
                extent=[
                    ref_transform.c, ref_transform.c + ref_transform.a * ncols,
                    ref_transform.f + ref_transform.e * nrows, ref_transform.f
                ])
ax.set_title("Significant Trends Only\n(p ≤ 0.05, Mann-Kendall)")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
plt.colorbar(im2, ax=ax, label="cm/year", shrink=0.8)

plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "Fig5_TWSA_trend_map.png"), bbox_inches="tight")
plt.close()
print("      Saved: Fig5_TWSA_trend_map.png")

# =====================================================================
# FIGURE 6: Estimated Land Subsidence
# =====================================================================

print("\n      Computing estimated land subsidence...")

# Method: Use well water level trend to estimate head change,
# then apply poroelastic formula:  Δs = Ssk × b × Δh
#
# We compute total Δh per block from 2002 to 2024 (~22 years)

print(f"\n      Aquifer Parameters Used:")
print(f"        Specific Yield (Sy)           = {Sy}")
print(f"        Skeletal specific storage (Ssk)= {Ssk} m^-1")
print(f"        Aquifer thickness (b)          = {AQUIFER_THICKNESS} m")
print(f"        Skeletal storativity (Ss=Ssk*b)= {Ssk * AQUIFER_THICKNESS}")

# Compute total head change (Δh) per block over the full record
subsidence_results = []
for block in blocks:
    bdata = df_well[df_well["BLOCK"] == block].copy()
    bdata = bdata.groupby("Date")["WL(mbgl)"].mean().reset_index().sort_values("Date")

    if len(bdata) < 5:
        continue

    # Linear trend over the full record
    x = mdates.date2num(bdata["Date"])
    y = bdata["WL(mbgl)"].values
    sl, intc, r, p, se = stats.linregress(x, y)

    # Total years spanned
    total_years = (bdata["Date"].max() - bdata["Date"].min()).days / 365.25
    trend_m_yr = sl * 365.25  # m/year deepening

    # Total head change (positive = water level dropped = Δh increase)
    total_dh = trend_m_yr * total_years  # meters

    # Subsidence estimation
    # Δs = Ssk × b × Δh  (in meters)
    subsidence_m = Ssk * AQUIFER_THICKNESS * abs(total_dh)
    subsidence_mm = subsidence_m * 1000  # convert to mm
    subsidence_rate_mm_yr = (Ssk * AQUIFER_THICKNESS * abs(trend_m_yr)) * 1000  # mm/year

    subsidence_results.append({
        "Block": block,
        "Total_Years": round(total_years, 1),
        "WL_Trend_m_yr": round(trend_m_yr, 4),
        "Total_dh_m": round(total_dh, 2),
        "Subsidence_Rate_mm_yr": round(subsidence_rate_mm_yr, 4),
        "Total_Subsidence_mm": round(subsidence_mm, 2),
        "Direction": "Deepening" if trend_m_yr > 0 else "Rising",
    })

df_sub = pd.DataFrame(subsidence_results).sort_values("Total_Subsidence_mm", ascending=False)

# Bar chart of subsidence
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# Panel A: Subsidence rate (mm/year)
ax = axes[0]
colors = ["#7C3AED" if s > 0 else "#059669" for s in df_sub["WL_Trend_m_yr"]]
bars = ax.barh(df_sub["Block"], df_sub["Subsidence_Rate_mm_yr"], color=colors, edgecolor="white", height=0.6)
ax.set_xlabel("Estimated Subsidence Rate (mm/year)")
ax.set_title(f"Estimated Land Subsidence Rate by Block\n(Ssk={Ssk}, b={AQUIFER_THICKNESS}m)")

for bar, rate in zip(bars, df_sub["Subsidence_Rate_mm_yr"]):
    ax.text(bar.get_width() + 0.0005, bar.get_y() + bar.get_height() / 2,
            f" {rate:.4f}", va="center", fontsize=9)

# Panel B: Total cumulative subsidence (mm)
ax = axes[1]
bars2 = ax.barh(df_sub["Block"], df_sub["Total_Subsidence_mm"], color="#1E40AF", edgecolor="white", height=0.6)
ax.set_xlabel("Total Estimated Subsidence (mm)")
ax.set_title(f"Cumulative Subsidence over Record Period")

for bar, tot in zip(bars2, df_sub["Total_Subsidence_mm"]):
    ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
            f" {tot:.2f}", va="center", fontsize=9)

plt.tight_layout()
fig.savefig(os.path.join(OUTPUT_DIR, "Fig6_Subsidence_estimation.png"), bbox_inches="tight")
plt.close()
print("      Saved: Fig6_Subsidence_estimation.png")

# =====================================================================
# Save summary CSV
# =====================================================================

print("\n" + "=" * 70)
print(" RESULTS SUMMARY")
print("=" * 70)

# Merge block trend and subsidence
df_summary = pd.merge(df_trends, df_sub, on="Block", how="outer")
df_summary.to_csv(os.path.join(OUTPUT_DIR, "subsidence_summary.csv"), index=False)

print("\n  Block-wise Results:")
print("  " + "-" * 90)
print(f"  {'Block':<25} {'WL Trend':>10} {'MK Test':>10} {'Subs Rate':>12} {'Total Subs':>12}")
print(f"  {'':25} {'(m/yr)':>10} {'':>10} {'(mm/yr)':>12} {'(mm)':>12}")
print("  " + "-" * 90)

for _, row in df_sub.iterrows():
    block = row["Block"]
    mk_row = df_trends[df_trends["Block"] == block]
    mk_t = mk_row["MK_trend"].values[0] if len(mk_row) > 0 else "—"
    print(f"  {block:<25} {row['WL_Trend_m_yr']:>10.4f} {str(mk_t):>10} {row['Subsidence_Rate_mm_yr']:>12.4f} {row['Total_Subsidence_mm']:>12.2f}")

print("  " + "-" * 90)

# District-wide summary
mean_sub_rate = df_sub["Subsidence_Rate_mm_yr"].mean()
total_sub_mean = df_sub["Total_Subsidence_mm"].mean()
print(f"\n  District Average Subsidence Rate:  {mean_sub_rate:.4f} mm/year")
print(f"  District Average Total Subsidence: {total_sub_mean:.2f} mm")

print(f"\n  TWSA Mann-Kendall trend: {mk_result.trend} (tau = {mk_result.Tau:.3f})")
print(f"  TWSA Sen's slope: {mk_result.slope:.4f} cm/year")

if len(merged) > 5:
    print(f"\n  Correlation (TWSA vs -WL):  r = {r_corr:.3f}, p = {p_corr:.3e}")

print(f"\n  Results saved to: {OUTPUT_DIR}")
print(f"    - Fig1_TWSA_timeseries.png")
print(f"    - Fig2_WellLevel_timeseries.png")
print(f"    - Fig3_TWSA_vs_WellLevel.png")
print(f"    - Fig4_Blockwise_WL_trends.png")
print(f"    - Fig5_TWSA_trend_map.png")
print(f"    - Fig6_Subsidence_estimation.png")
print(f"    - subsidence_summary.csv")

print("\n" + "=" * 70)
print(" IMPORTANT NOTES")
print("=" * 70)
print(f"""
  1. Subsidence estimates use the poroelastic formula:
     ds = Ssk * b * dh
     where Ssk = {Ssk} m^-1, b = {AQUIFER_THICKNESS} m

  2. Current parameters are DEFAULT values for hard-rock terrain.
     For more accurate results, update with values from:
     - CGWB East Singhbhum Aquifer Report
     - Published literature on Singhbhum Craton hydrogeology

  3. The subsidence estimates are INDICATIVE. For precise values,
     InSAR (Sentinel-1) analysis is recommended.

  4. Positive WL trend = water table is going deeper = depletion
     Negative WL trend = water table is rising = recharge
""")

print("Done!")
