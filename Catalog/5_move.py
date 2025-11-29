"""
mover.py — Moves files based on AI scores or decision JSON

Works with images in the same directory (no separate thumbnail folder needed)

Usage:
    # Move files in same directory where image_scores.json exists
    python mover.py /path/to/images
    
    # Or use pre-made decisions.json
    python mover.py /path/to/images --decisions decisions.json
    
    # Dry run (preview without moving)
    python mover.py /path/to/images --dry-run
    
    # Custom thresholds
    python mover.py /path/to/images --content-thresh 0.30 --neg-thresh 0.20
"""

import os
import sys
import shutil
import json
from pathlib import Path
import argparse

DEFAULT_CONTENT_THRESH = 0.25
DEFAULT_NEGATIVE_THRESH = 0.22

def load_scores_from_dir(target_dir):
    """Load image_scores.json from directory"""
    db_path = Path(target_dir) / "image_scores.json"
    
    if not db_path.exists():
        print(f"❌ No score database found: {db_path}")
        print(f"💡 Run: python scanner.py {target_dir}")
        return None
    
    try:
        with open(db_path, 'r') as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data):,} scores")
        return data
    except Exception as e:
        print(f"❌ Failed to load scores: {e}")
        return None

def load_decisions_json(decisions_path):
    """Load pre-made decisions.json"""
    try:
        with open(decisions_path, 'r') as f:
            data = json.load(f)
        
        keep = data.get('keep', [])
        discard = data.get('discard', [])
        print(f"✅ Loaded decisions: {len(keep):,} keep, {len(discard):,} discard")
        return keep, discard
    except Exception as e:
        print(f"❌ Failed to load decisions: {e}")
        return None, None

def map_score_to_file(score_path, target_dir):
    """Find actual file from score path (handles path variations)"""
    target_dir = Path(target_dir).resolve()
    score_path = Path(score_path)
    
    # If score_path is absolute and exists, return it
    if score_path.is_absolute() and score_path.exists():
        return score_path
    
    # Try as relative path from target_dir
    candidate = target_dir / score_path
    if candidate.exists():
        return candidate
    
    # Try just the filename in target_dir (recursive search)
    filename = score_path.name
    for root, dirs, files in os.walk(target_dir):
        # Skip output folders
        if any(skip in Path(root).parts for skip in ['Keep', 'Discard', 'webP-OG']):
            continue
        if filename in files:
            return Path(root) / filename
    
    return None

def apply_thresholds(score_data, content_thresh, neg_thresh):
    """Apply thresholds to scores"""
    keep_list = []
    discard_list = []
    
    for path, scores in score_data.items():
        is_good = (scores['real'] > content_thresh) or (scores['cgi'] > content_thresh)
        is_not_trash = scores['neg'] < neg_thresh
        
        if is_good and is_not_trash:
            keep_list.append(path)
        else:
            discard_list.append(path)
    
    return keep_list, discard_list

def safe_move(src, dest_folder, dry_run=False):
    """Move file with duplicate handling"""
    src = Path(src)
    dest_folder = Path(dest_folder)
    
    if not src.exists():
        return False, "Source doesn't exist"
    
    if src.parent == dest_folder:
        return False, "Already in target folder"
    
    dest_path = dest_folder / src.name
    counter = 1
    
    while dest_path.exists():
        if src.samefile(dest_path):
            return False, "Same file already exists"
        dest_path = dest_folder / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    
    if dry_run:
        return True, f"Would move to {dest_path}"
    
    try:
        shutil.move(str(src), str(dest_path))
        return True, "Moved"
    except Exception as e:
        return False, f"Error: {e}"

def move_files(target_dir, decisions_path=None, 
               content_thresh=DEFAULT_CONTENT_THRESH, 
               neg_thresh=DEFAULT_NEGATIVE_THRESH,
               dry_run=False):
    """Main file moving logic"""
    
    target_dir = Path(target_dir).resolve()
    
    print("="*60)
    print("AI IMAGE MOVER")
    print("="*60)
    print(f"📁 Working directory: {target_dir}")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be moved")
    
    # Load decisions
    keep_paths = []
    discard_paths = []
    
    if decisions_path:
        # Load from decisions.json
        print(f"📋 Using decisions from: {decisions_path}")
        keep_paths, discard_paths = load_decisions_json(decisions_path)
        if keep_paths is None:
            return
    
    else:
        # Load from scores in same directory
        print(f"📂 Loading scores from directory")
        
        score_data = load_scores_from_dir(target_dir)
        if not score_data:
            return
        
        print(f"⚙️  Applying thresholds: Content={content_thresh}, Negative={neg_thresh}")
        keep_paths, discard_paths = apply_thresholds(score_data, content_thresh, neg_thresh)
    
    print("="*60)
    
    # Map score paths to actual files
    print(f"\n🔗 Finding {len(keep_paths) + len(discard_paths):,} files...")
    
    keep_files = []
    discard_files = []
    not_found = []
    
    for score_path in keep_paths:
        actual_file = map_score_to_file(score_path, target_dir)
        if actual_file:
            keep_files.append(actual_file)
        else:
            not_found.append(score_path)
    
    for score_path in discard_paths:
        actual_file = map_score_to_file(score_path, target_dir)
        if actual_file:
            discard_files.append(actual_file)
        else:
            not_found.append(score_path)
    
    print(f"✅ Found {len(keep_files):,} files to KEEP")
    print(f"❌ Found {len(discard_files):,} files to DISCARD")
    
    if not_found:
        print(f"⚠️  {len(not_found):,} files not found (may have been moved/deleted)")
    
    if not keep_files and not discard_files:
        print("\n❌ No files to move!")
        return
    
    # Confirm
    if not dry_run:
        print("\n" + "="*60)
        print("⚠️  WARNING: About to move files!")
        print(f"   ✅ {len(keep_files):,} → Keep/")
        print(f"   ❌ {len(discard_files):,} → Discard/")
        print("="*60)
        confirm = input("Continue? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Aborted")
            return
    
    # Create directories
    keep_dir = target_dir / "Keep"
    discard_dir = target_dir / "Discard"
    
    if not dry_run:
        keep_dir.mkdir(exist_ok=True)
        discard_dir.mkdir(exist_ok=True)
    
    # Move files
    print(f"\n{'🔍 SIMULATING' if dry_run else '📦 MOVING'} files...")
    
    moved_keep = 0
    moved_discard = 0
    errors = []
    
    for file in keep_files:
        success, msg = safe_move(file, keep_dir, dry_run)
        if success:
            moved_keep += 1
        else:
            errors.append(f"{file.name}: {msg}")
    
    for file in discard_files:
        success, msg = safe_move(file, discard_dir, dry_run)
        if success:
            moved_discard += 1
        else:
            errors.append(f"{file.name}: {msg}")
    
    # Summary
    print("\n" + "="*60)
    print(f"{'DRY RUN ' if dry_run else ''}COMPLETE")
    print("="*60)
    print(f"✅ Keep:    {moved_keep:,} files {'would be ' if dry_run else ''}moved")
    print(f"❌ Discard: {moved_discard:,} files {'would be ' if dry_run else ''}moved")
    
    if errors:
        print(f"\n⚠️  Errors/Skipped: {len(errors)}")
        for err in errors[:10]:
            print(f"   • {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors)-10} more")
    
    if not dry_run:
        print(f"\n📂 Files moved to:")
        print(f"   {keep_dir}")
        print(f"   {discard_dir}")
    
    print("="*60)

def main():
    parser = argparse.ArgumentParser(
        description="Move files based on AI scoring decisions"
    )
    parser.add_argument(
        "folder",
        help="Directory containing images and image_scores.json"
    )
    parser.add_argument(
        "--decisions",
        type=str,
        help="Path to decisions.json file (optional)"
    )
    parser.add_argument(
        "--content-thresh",
        type=float,
        default=DEFAULT_CONTENT_THRESH,
        help=f"Content threshold (default: {DEFAULT_CONTENT_THRESH})"
    )
    parser.add_argument(
        "--neg-thresh",
        type=float,
        default=DEFAULT_NEGATIVE_THRESH,
        help=f"Negative threshold (default: {DEFAULT_NEGATIVE_THRESH})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be moved without actually moving"
    )
    
    args = parser.parse_args()
    
    move_files(
        args.folder,
        args.decisions,
        args.content_thresh,
        args.neg_thresh,
        args.dry_run
    )

if __name__ == "__main__":
    main()