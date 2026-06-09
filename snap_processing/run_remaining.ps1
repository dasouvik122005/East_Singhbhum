$ErrorActionPreference = "Stop"
Write-Host "1. Running SNAPHU Phase Unwrapping (Single Threaded)..."
Set-Location ".\output\snaphu_export\MST_20260505_SLV_20260129_ifg"
& "..\..\..\snaphu\snaphu\bin\snaphu.exe" -f snaphu.conf Phase_ifg_srd_VV_05May2026_29Jan2026.snaphu.img 25679
Set-Location "..\..\..\"

Write-Host "`n2. Importing Unwrapped Phase back to SNAP..."
gpt snaphuImport.xml

Write-Host "`n3. Running Range-Doppler Terrain Correction..."
gpt Terrain-Correction -Ssource=".\output\insar_unwrapped_stack.dim" -PdemName="SRTM 3Sec" -PpixelSpacingInMeter=30 -PmapProjection="WGS84(DD)" -t ".\output\insar_tc.dim"

Write-Host "`n4. Running Post-Processing Validation Script..."
python post_process_snap.py --insar_file .\output\insar_tc.dim --well_file "..\East Singhbum_1354.xlsx" --shapefile "..\shapefile\East_singhum_wgs.shp" --out_dir ..\results

Write-Host "`nALL DONE!"
