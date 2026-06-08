# Land Subsidence Analysis - East Singhbhum District, Jharkhand

A geospatial analysis project that estimates **land subsidence** in East Singhbhum district by integrating NASA's **GRACE/GRACE-FO** satellite gravity data with **CGWB** (Central Ground Water Board) well water level observations.

---

## Study Area

**East Singhbhum** is located in southeastern Jharkhand, India, and is part of the **Singhbhum Craton / Chotanagpur Plateau**. The district headquarters is **Jamshedpur**. The geology is predominantly hard crystalline rock with shallow weathered-zone aquifers.

---

## Methodology

Land subsidence is estimated using the **one-dimensional poroelastic compaction model**:

```
Subsidence (ds) = Ssk x b x dh
```

Where:
- **Ssk** = Skeletal specific storage (compressibility of aquifer skeleton)
- **b** = Aquifer thickness
- **dh** = Change in hydraulic head (from well water level trends)

### Workflow

```
Step 1: Extract GRACE TWSA          Step 2: Analyze Well Data         Step 3: Estimate Subsidence
+---------------------+            +---------------------+           +----------------------+
| GRACE NetCDF        |            | CGWB Well WL Excel  |           | Combine TWSA + WL    |
| (CSR RL06.3 Mascon) |            | (1994-2024)         |           | Compute trends       |
|         |           |            |         |           |           | Apply ds = Ssk*b*dh  |
|         v           |            |         v           |           | Generate maps/plots  |
| Clip to East        |            | Block-wise trends   |           +----------------------+
| Singhbhum shapefile |            | Mann-Kendall test   |
| Export monthly TIFFs|            | Sen's slope         |
+---------------------+            +---------------------+
```

---

## Data Sources

| Dataset | Source | Period | Resolution |
|---------|--------|--------|------------|
| GRACE/GRACE-FO TWSA | [CSR RL06.3 Mascons](https://www2.csr.utexas.edu/grace/) | Apr 2002 - Apr 2026 | ~0.25 deg (~25 km) |
| Well Water Levels | CGWB (Central Ground Water Board) | Jan 1994 - May 2024 | Point (44 villages, 11 blocks) |
| District Boundary | Survey of India / State GIS | - | Vector (WGS 84) |

---

## Project Structure

```
east_singhbum/
|
|-- grace/                                  # GRACE NetCDF data (not in repo, ~112 MB)
|   +-- CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc
|
|-- shapefile/                              # East Singhbhum district boundary
|   |-- East_singhum_wgs.shp
|   |-- East_singhum_wgs.dbf
|   |-- East_singhum_wgs.prj
|   +-- East_singhum_wgs.shx
|
|-- output/                                 # Monthly TWSA GeoTIFFs (254 files)
|   |-- 2002_04_East_Singhbhum_TWSA.tif
|   |-- 2002_05_East_Singhbhum_TWSA.tif
|   |-- ...
|   +-- 2026_04_East_Singhbhum_TWSA.tif
|
|-- results/                                # Analysis outputs (figures + CSV)
|   |-- Fig1_TWSA_timeseries.png
|   |-- Fig2_WellLevel_timeseries.png
|   |-- Fig3_TWSA_vs_WellLevel.png
|   |-- Fig4_Blockwise_WL_trends.png
|   |-- Fig5_TWSA_trend_map.png
|   |-- Fig6_Subsidence_estimation.png
|   +-- subsidence_summary.csv
|
|-- East Singhbum_1354.xlsx                 # CGWB well water level data (1354 records)
|-- grace_east_singhum_export.py            # Script 1: Extract TWSA from GRACE NetCDF
|-- land_subsidence_analysis.py             # Script 2: Main subsidence analysis
|-- requirements.txt                        # Python dependencies
+-- README.md                               # This file
```

---

## Scripts

### 1. `grace_east_singhum_export.py` - GRACE Data Extraction

Reads the GRACE/GRACE-FO NetCDF file, clips the `lwe_thickness` (Liquid Water Equivalent) variable to the East Singhbhum boundary using the shapefile, and exports **254 monthly GeoTIFF** rasters to the `output/` folder.

**Input:** `grace/CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc` + `shapefile/East_singhum_wgs.shp`  
**Output:** `output/YYYY_MM_East_Singhbhum_TWSA.tif` (254 files)

### 2. `land_subsidence_analysis.py` - Main Analysis

Combines GRACE TWSA rasters with CGWB well water level data to perform:

1. **TWSA Time Series Analysis** - Monthly mean TWSA with linear trend and Mann-Kendall test
2. **Well Water Level Analysis** - District-wide and block-wise groundwater level trends
3. **GRACE vs Well Validation** - Dual-axis comparison with Pearson correlation
4. **Block-wise Trend Analysis** - Sen's slope and Mann-Kendall for each block
5. **Pixel-wise TWSA Trend Map** - Spatial Sen's slope with significance masking
6. **Land Subsidence Estimation** - Using ds = Ssk x b x dh for each block

**Input:** `output/*.tif` + `East Singhbum_1354.xlsx`  
**Output:** 6 figures + `subsidence_summary.csv` in `results/`

---

## Aquifer Parameters Used

| Parameter | Value | Notes |
|-----------|-------|-------|
| Specific Yield (Sy) | 0.03 | Hard rock typical: 0.01-0.05 |
| Skeletal Specific Storage (Ssk) | 5 x 10^-5 m^-1 | Hard rock typical |
| Aquifer Thickness (b) | 20 m | Weathered zone: 10-30 m |
| Skeletal Storativity (Ss = Ssk x b) | 0.001 | Dimensionless |

> **Note:** These are default values for hard-rock terrain. For more accurate results, update with values from the CGWB East Singhbhum Aquifer Report.

---

## Key Results

### TWSA Analysis
- TWSA oscillates between **-34 cm** (dry) and **+31 cm** (monsoon)
- Linear trend: **-0.139 cm/year** (p = 0.305, **not significant**)
- Mann-Kendall: **no significant trend** (tau = -0.046)

### GRACE vs Well Correlation
- Pearson **r = 0.617** (p = 4.2 x 10^-10) - **highly significant**
- Validates that GRACE captures real groundwater dynamics

### Block-wise Subsidence Estimates

| Block | WL Trend (m/yr) | MK Test | Subs Rate (mm/yr) | Total (mm) |
|-------|-----------------|---------|-------------------|------------|
| Chakulia | -0.1506 | decreasing** | 0.1506 | 4.57 |
| Golmuri Cum Jugsalai | -0.0781 | decreasing* | 0.0781 | 2.37 |
| Dhalbhumgarh | +0.0344 | no trend | 0.0344 | 1.04 |
| Potka | -0.0199 | no trend | 0.0199 | 0.61 |
| Musabani | -0.0156 | no trend | 0.0156 | 0.39 |
| Bahragora | -0.0046 | no trend | 0.0046 | 0.14 |
| Ghatshila | -0.0075 | no trend | 0.0075 | 0.13 |

- **District Average Subsidence Rate:** 0.044 mm/year
- **District Average Total Subsidence:** 1.32 mm (over ~30 years)

### Overall Assessment: **LOW SUBSIDENCE RISK**

East Singhbhum shows very low land subsidence due to:
1. Hard-rock terrain (Singhbhum Craton) resistant to compaction
2. Most blocks show stable or rising water levels
3. Good monsoon recharge replenishes groundwater annually
4. No large-scale irrigational pumping

---

## Output Figures

### Figure 1: GRACE TWSA Time Series
Shows monthly Total Water Storage Anomaly with linear trend and Mann-Kendall result.

### Figure 2: Well Water Level Time Series
Top: District mean with std deviation. Bottom: Block-wise breakdown.

### Figure 3: TWSA vs Well Level Validation
Dual-axis comparison showing strong correlation (r = 0.617).

### Figure 4: Block-wise Groundwater Trends
Bar chart of water level trends per block with statistical significance.

### Figure 5: TWSA Trend Map
Pixel-wise Sen's slope with significance mask (Mann-Kendall p <= 0.05).

### Figure 6: Subsidence Estimation
Block-wise subsidence rate (mm/yr) and cumulative subsidence (mm).

---

## How to Run

### Prerequisites
```bash
pip install -r requirements.txt
```

### Step 1: Extract GRACE Data (optional - output TIFFs already provided)
```bash
python grace_east_singhum_export.py
```
> Requires the GRACE NetCDF file (~112 MB, not included in repo).  
> Download from: https://www2.csr.utexas.edu/grace/

### Step 2: Run Subsidence Analysis
```bash
python land_subsidence_analysis.py
```
> Generates all 6 figures and the summary CSV in the `results/` folder.

---

## Limitations

1. **GRACE spatial resolution** (~300 km mascons) is coarse for district-level analysis
2. **GWSA not isolated** - Soil moisture & surface water not subtracted from TWSA (would need GLDAS data)
3. **Default aquifer parameters** - Site-specific values from CGWB reports would improve accuracy
4. **Indicative estimates** - For precise subsidence measurements, InSAR (Sentinel-1) analysis is recommended

## Future Work

- Download GLDAS NOAH data to isolate Groundwater Storage Anomaly (GWSA) from TWSA
- Process Sentinel-1 InSAR for millimeter-scale surface deformation maps
- Obtain site-specific aquifer parameters from CGWB
- Perform sensitivity analysis on Sy, Ssk, and b parameters

---

## References

1. Save, H., Bettadpur, S., & Tapley, B.D. (2016). High resolution CSR GRACE RL05 mascons. *J. Geophys. Res. Solid Earth*, 121.
2. Rodell, M., et al. (2004). The Global Land Data Assimilation System. *Bull. Amer. Meteor. Soc.*, 85(3), 381-394.
3. Central Ground Water Board (CGWB), Ministry of Jal Shakti, Government of India.
