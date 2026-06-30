#!/usr/bin/env python3
"""
Script to audit dist_to_enemy_hq calculation
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import parse_init, calculate_paths


def main():
    print("[Audit] Starting distance scale audit", file=sys.stderr)
    
    # Read game initialization data from stdin
    try:
        M, S = parse_init()
    except Exception as e:
        print(f"[Audit] Error parsing init: {e}", file=sys.stderr)
        return
    
    # Calculate paths
    P = calculate_paths(M)
    
    # Prepare audit data
    audit_data = {
        "map": {
            "N": M.N,
            "my_hq": M.my_hq,
            "opp_hq": M.opp_hq,
            "strongholds": M.strongholds,
            "x": M.x,
            "y": M.y
        },
        "dist_matrix": [
            [
                float(x) if x != float('inf') else "inf" 
                for x in row
            ] 
            for row in P.dist
        ],
        "example_distances": {
            "0_80": P.dist[0][80],  # Left HQ to Right HQ
            "0_1": P.dist[0][1],
            "0_2": P.dist[0][2],
            "80_79": P.dist[80][79],
            "80_78": P.dist[80][78]
        },
        "euclid_examples": {}
    }
    
    # Calculate some euclid_ceil examples
    import math
    def euclid_ceil(M, u, v):
        return math.ceil(math.hypot(M.x[u] - M.x[v], M.y[u] - M.y[v]))
    
    audit_data["euclid_examples"]["0_80"] = euclid_ceil(M, 0, 80)
    audit_data["euclid_examples"]["0_1"] = euclid_ceil(M, 0, 1)
    audit_data["euclid_examples"]["1_80"] = euclid_ceil(M, 1, 80)
    
    # Write audit data to file
    audit_file = Path(__file__).parent.parent / "logs" / "distance_audit.json"
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)
    
    print(f"[Audit] Distance audit data written to {audit_file}", file=sys.stderr)
    print("OK", flush=True)


if __name__ == "__main__":
    main()
