import os
import glob
import re
import subprocess
import argparse
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description="Automate SNAP GPT InSAR processing on Windows")
    parser.add_index = parser.add_argument
    parser.add_index("--zip_dir", type=str, default="./zip_data", 
                        help="Directory containing raw Sentinel-1 SLC zip files")
    parser.add_index("--out_dir", type=str, default="./output", 
                        help="Directory to save output BEAM-DIMAP interferograms")
    parser.add_index("--subswath", type=str, default="IW2", 
                        help="S1 subswath to split (default: IW2, covers East Singhbhum)")
    parser.add_index("--first_burst", type=int, default=3, 
                        help="First burst index (default: 3)")
    parser.add_index("--last_burst", type=int, default=5, 
                        help="Last burst index (default: 5)")
    parser.add_index("--gpt_path", type=str, default="gpt", 
                        help="Path to SNAP gpt executable (default: 'gpt' if in system PATH)")
    parser.add_index("--dry_run", action="store_true", 
                        help="Analyze inputs and print commands without executing them")
    return parser.parse_args()

def parse_s1_date(filename):
    # Match: S1A_IW_SLC__1SDV_20260601T001254_...
    match = re.search(r'S1[AB]_IW_SLC__.*_(\d{8})T', os.path.basename(filename))
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d")
    return None

def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    
    print("=" * 70)
    print(" SNAP GPT InSAR Coregistration & Interferogram Automation")
    print("=" * 70)
    
    # Step 1: Scan zip files
    zip_files = sorted(glob.glob(os.path.join(args.zip_dir, "S1*_IW_SLC__*.zip")))
    print(f"Scanning zip folder: {args.zip_dir}")
    print(f"Found {len(zip_files)} raw Sentinel-1 SLC zip files.")
    
    if len(zip_files) < 2:
        print("Error: You need at least 2 Sentinel-1 SLC zip files in the zip directory to form an interferogram.")
        return
        
    # Parse dates
    scene_data = []
    for f in zip_files:
        dt = parse_s1_date(f)
        if dt:
            scene_data.append((dt, f))
            
    # Sort chronologically
    scene_data = sorted(scene_data, key=lambda x: x[0])
    
    # Print scene inventory
    print("\nScene Inventory:")
    for dt, f in scene_data:
        print(f"  - {dt.strftime('%Y-%m-%d')}: {os.path.basename(f)}")
        
    # Step 2: Auto-select Master (median date)
    median_idx = len(scene_data) // 2
    master_date, master_file = scene_data[median_idx]
    
    print("\nMaster Selection:")
    print(f"  Selected Median Master Image: {master_date.strftime('%Y-%m-%d')}")
    print(f"  Master File:                  {os.path.basename(master_file)}")
    
    slaves = [x for i, x in enumerate(scene_data) if i != median_idx]
    print(f"  Total Slave Images:           {len(slaves)}")
    print("-" * 70)
    
    # Step 3: Run processing loop
    graph_xml = os.path.join(os.path.dirname(__file__), "insar_graph.xml")
    if not os.path.exists(graph_xml):
        print(f"Error: XML graph file not found at: {graph_xml}")
        return
        
    # Test if gpt is available
    if not args.dry_run:
        try:
            subprocess.run([args.gpt_path, "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print(f"Error: SNAP executable '{args.gpt_path}' was not found in your system PATH.")
            print("Please make sure SNAP is installed and added to PATH, or specify the path manually:")
            print("E.g., python run_snap_gpt.py --gpt_path \"C:\\Program Files\\snap\\bin\\gpt.exe\" ...")
            return

    print("\n[Processing Loop]")
    master_date_str = master_date.strftime("%Y%m%d")
    
    for idx, (slave_date, slave_file) in enumerate(slaves):
        slave_date_str = slave_date.strftime("%Y%m%d")
        output_name = f"MST_{master_date_str}_SLV_{slave_date_str}_ifg"
        output_dim = os.path.join(args.out_dir, f"{output_name}.dim")
        
        print(f"\n[{idx+1}/{len(slaves)}] Forming Interferogram: MST {master_date_str} - SLV {slave_date_str}")
        print(f"  Output: {os.path.basename(output_dim)}")
        
        # Check if already completed
        if os.path.exists(output_dim):
            print("  Skipped: Output file already exists (Resume Mode).")
            continue
            
        # Compile gpt parameters
        gpt_cmd = [
            args.gpt_path,
            graph_xml,
            f"-Pmaster={os.path.abspath(master_file)}",
            f"-Pslave={os.path.abspath(slave_file)}",
            f"-Poutput={os.path.abspath(output_dim)}",
            f"-Psubswath={args.subswath}",
            f"-PfirstBurst={args.first_burst}",
            f"-PlastBurst={args.last_burst}"
        ]
        
        print("  Command Line:")
        print("  " + " ".join(gpt_cmd))
        
        if args.dry_run:
            print("  [Dry Run] Command would be executed.")
            continue
            
        # Execute command
        try:
            print("  Processing with SNAP... (this may take a few minutes)")
            result = subprocess.run(gpt_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("  Success: Product generated.")
        except subprocess.CalledProcessError as e:
            print("  FAILED: SNAP gpt exited with an error.")
            print(f"  Error Log:\n{e.stderr}")
            # Keep going to process other pairs
            continue
            
    print("\n" + "=" * 70)
    print(" SNAP GPT InSAR Processing Complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
