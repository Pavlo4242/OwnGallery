"""
previewer.py — Interactive threshold adjustment and preview
Shows what WILL be moved without actually moving anything

Usage:
    python previewer.py /path/to/thumbnails
    python previewer.py /path/to/thumbnails --export decisions.json
"""

import os
import sys
import json
from pathlib import Path
import argparse

DEFAULT_CONTENT_THRESH = 0.25
DEFAULT_NEGATIVE_THRESH = 0.22

def load_scores(target_dir):
    """Load image scores database"""
    db_path = Path(target_dir) / "image_scores.json"
    
    if not db_path.exists():
        print(f"❌ No score database found: {db_path}")
        print(f"💡 Run: python scanner.py {target_dir}")
        return None
    
    try:
        with open(db_path, 'r') as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data):,} image scores")
        return data
    except Exception as e:
        print(f"❌ Failed to load database: {e}")
        return None

def apply_thresholds(score_data, content_thresh, neg_thresh):
    """Determine keep/discard for each image"""
    keep_list = []
    discard_list = []
    
    for path, scores in score_data.items():
        if not Path(path).exists():
            continue
        
        is_good = (scores['real'] > content_thresh) or (scores['cgi'] > content_thresh)
        is_not_trash = scores['neg'] < neg_thresh
        
        if is_good and is_not_trash:
            keep_list.append(path)
        else:
            discard_list.append(path)
    
    return keep_list, discard_list

def show_sample(file_list, label, count=5):
    """Show sample filenames"""
    if not file_list:
        return
    
    print(f"\n  {label} (showing {min(count, len(file_list))} of {len(file_list):,}):")
    for path in file_list[:count]:
        filename = Path(path).name
        print(f"    • {filename}")
    
    if len(file_list) > count:
        print(f"    ... and {len(file_list) - count:,} more")

def export_decisions(keep_list, discard_list, output_path):
    """Export keep/discard decisions to JSON"""
    decisions = {
        "keep": keep_list,
        "discard": discard_list,
        "stats": {
            "keep_count": len(keep_list),
            "discard_count": len(discard_list),
            "total": len(keep_list) + len(discard_list)
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(decisions, f, indent=2)
    
    print(f"✅ Decisions exported to: {output_path}")

def interactive_preview(target_dir, export_path=None):
    """Interactive threshold adjustment"""
    target_dir = Path(target_dir).resolve()
    
    print("="*60)
    print("AI IMAGE SORTER - PREVIEW MODE")
    print("="*60)
    print(f"📁 Thumbnails Directory: {target_dir}") 
    print(f"📊 Scores File: {target_dir / 'image_scores.json'}")  # ADD THIS LINE
    
    score_data = load_scores(target_dir)
    if not score_data:
        return
    
    c_thresh = DEFAULT_CONTENT_THRESH
    n_thresh = DEFAULT_NEGATIVE_THRESH
    
    while True:
        print("\n" + "="*60)
        print(f"⚙️  CURRENT THRESHOLDS:")
        print(f"   Content (Real/CGI):  {c_thresh}")
        print(f"   Negative (Quality):  {n_thresh}")
        print("="*60)
        
        keep_list, discard_list = apply_thresholds(score_data, c_thresh, n_thresh)
        
        total = len(keep_list) + len(discard_list)
        keep_pct = (len(keep_list) / total * 100) if total > 0 else 0
        discard_pct = (len(discard_list) / total * 100) if total > 0 else 0
        
        print(f"\n📊 PREVIEW RESULTS:")
        print(f"   ✅ KEEP:    {len(keep_list):,} ({keep_pct:.1f}%)")
        print(f"   ❌ DISCARD: {len(discard_list):,} ({discard_pct:.1f}%)")
        print(f"   📁 TOTAL:   {total:,}")
        
        # Show samples
        show_sample(keep_list, "✅ KEEP Examples", 3)
        show_sample(discard_list, "❌ DISCARD Examples", 3)
        
        print("\n🎯 OPTIONS:")
        print("  [1] Change Content Threshold (higher = stricter)")
        print("  [2] Change Negative Threshold (lower = stricter)")
        print("  [3] Show detailed statistics")
        print("  [4] Export decisions to JSON")
        print("  [5] Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            try:
                new_val = float(input(f"New Content Threshold (current: {c_thresh}): "))
                if 0.1 <= new_val <= 1.0:
                    c_thresh = new_val
                else:
                    print("⚠️  Value must be between 0.1 and 1.0")
            except:
                print("⚠️  Invalid number")
        
        elif choice == '2':
            try:
                new_val = float(input(f"New Negative Threshold (current: {n_thresh}): "))
                if 0.1 <= new_val <= 1.0:
                    n_thresh = new_val
                else:
                    print("⚠️  Value must be between 0.1 and 1.0")
            except:
                print("⚠️  Invalid number")
        
        elif choice == '3':
            print("\n" + "="*60)
            print("📈 DETAILED STATISTICS")
            print("="*60)
            
            # Analyze score distributions
            real_scores = [s['real'] for s in score_data.values()]
            cgi_scores = [s['cgi'] for s in score_data.values()]
            neg_scores = [s['neg'] for s in score_data.values()]
            
            print(f"Real scores:     min={min(real_scores):.2f} max={max(real_scores):.2f} avg={sum(real_scores)/len(real_scores):.2f}")
            print(f"CGI scores:      min={min(cgi_scores):.2f} max={max(cgi_scores):.2f} avg={sum(cgi_scores)/len(cgi_scores):.2f}")
            print(f"Negative scores: min={min(neg_scores):.2f} max={max(neg_scores):.2f} avg={sum(neg_scores)/len(neg_scores):.2f}")
            
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            if export_path:
                output = Path(export_path)
            else:
                output = target_dir / "decisions.json"
            
            export_decisions(keep_list, discard_list, output)
            print(f"\n💡 Copy this file + thumbnails to review elsewhere")
            print(f"💡 Or use: python mover.py <originals_dir> --decisions {output}")
        
        elif choice == '5':
            print("\n👋 Exiting preview mode")
            break

def main():
    parser = argparse.ArgumentParser(
        description="Preview AI sorting decisions without moving files"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=os.getcwd(),
        help="Folder containing image_scores.json (default: current directory)"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export decisions to JSON file"
    )
    
    args = parser.parse_args()
    interactive_preview(args.folder, args.export)

if __name__ == "__main__":
    main()