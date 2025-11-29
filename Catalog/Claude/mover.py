"""
mover.py — Moves ORIGINAL files based on AI scores or decision JSON

This script maps thumbnail paths back to originals and moves them.

Usage:
    # Move originals based on image_scores.json in thumbnail dir
    python mover.py /path/to/originals --thumb-dir /path/to/thumbnails
    
    # Or use pre-made decisions.json
    python mover.py /path/to/originals --decisions decisions.json
    
    # Dry run (preview without moving)
    python mover.py /path/to/originals --thumb-dir /path/to/thumbnails --dry-run
"""

import os
import sys
import shutil
import json
from pathlib import Path
import argparse

DEFAULT_CONTENT_THRESH = 0.25
DEFAULT_NEGATIVE_THRESH = 0.22

def load_scores_from_thumbs(thumb_dir):
    """Load image_scores.json from thumbnail directory"""
    db_path = Path(thumb_dir) / "image_scores.json"
    
    if not db_path.exists():
        print(f"❌ No score database found: {db_path}")
        return None
    
    try:
        with open(db_path, 'r') as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data):,} scores from thumbnails")
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

def map_thumb_to_original(thumb_path, thumb_root, orig_root):
    """Find original file from thumbnail path"""
    thumb_root = Path(thumb_root).resolve()
    orig_root = Path(orig_root).resolve()
    thumb_path = Path(thumb_path)
    
    # Get relative path
    try:
        rel_path = thumb_path.relative_to(thumb_root)
    except ValueError:
        # thumb_path might not be under thumb_root if it's just a filename
        rel_path = Path(thumb_path.name)
    
    # Try to find original with various extensions
    valid_exts = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
    
    orig_stem = orig_root / rel_path.parent / rel_path.stem
    
    for ext in valid_exts:
        candidate = orig_stem.with_suffix(ext)
        if candidate.exists():
            return candidate
    
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

def move_files(orig_dir, thumb_dir=None, decisions_path=None, 
               content_thresh=DEFAULT_CONTENT_THRESH, 
               neg_thresh=DEFAULT_NEGATIVE_THRESH,
               dry_run=False):
    """Main file moving logic"""
    
    orig_dir = Path(orig_dir).resolve()
    
    print("="*60)
    print("AI IMAGE MOVER")
    print("="*60)
    print(f"📁 Original files: {orig_dir}")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be moved")
    
    # Load decisions
    keep_thumbs = []
    discard_thumbs = []
    
    if decisions_path:
        # Load from decisions.json
        print(f"📋 Using decisions from: {decisions_path}")
        keep_thumbs, discard_thumbs = load_decisions_json(decisions_path)
        if keep_thumbs is None:
            return
        thumb_dir = Path(decisions_path).parent  # Assume same directory
    
    elif thumb_dir:
        # Load from thumbnail scores
        print(f"📂 Thumbnail directory: {thumb_dir}")
        thumb_dir = Path(thumb_dir).resolve()
        
        score_data = load_scores_from_thumbs(thumb_dir)
        if not score_data:
            return
        
        print(f"⚙️  Applying thresholds: Content={content_thresh}, Negative={neg_thresh}")
        keep_thumbs, discard_thumbs = apply_thresholds(score_data, content_thresh, neg_thresh)
    
    else:
        print("❌ Must specify either --thumb-dir or --decisions")
        return
    
    print("="*60)
    
    # Map thumbnails to originals
    print(f"\n🔗 Mapping {len(keep_thumbs) + len(discard_thumbs):,} thumbnails to originals...")
    
    keep_originals = []
    discard_originals = []
    not_found = []
    
    for thumb_path in keep_thumbs:
        orig = map_thumb_to_original(thumb_path, thumb_dir, orig_dir)
        if orig:
            keep_originals.append(orig)
        else:
            not_found.append(thumb_path)
    
    for thumb_path in discard_thumbs:
        orig = map_thumb_to_original(thumb_path, thumb_dir, orig_dir)
        if orig:
            discard_originals.append(orig)
        else:
            not_found.append(thumb_path)
    
    print(f"✅ Found {len(keep_originals):,} originals to KEEP")
    print(f"❌ Found {len(discard_originals):,} originals to DISCARD")
    
    if not_found:
        print(f"⚠️  {len(not_found):,} originals not found (may have been moved/deleted)")
    
    if not keep_originals and not discard_originals:
        print("\n❌ No files to move!")
        return
    
    # Confirm
    if not dry_run:
        print("\n" + "="*60)
        print("⚠️  WARNING: About to move files!")
        print(f"   ✅ {len(keep_originals):,} → Keep/")
        print(f"   ❌ {len(discard_originals):,} → Discard/")
        print("="*60)
        confirm = input("Continue? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Aborted")
            return
    
    # Create directories
    keep_dir = orig_dir / "Keep"
    discard_dir = orig_dir / "Discard"
    
    if not dry_run:
        keep_dir.mkdir(exist_ok=True)
        discard_dir.mkdir(exist_ok=True)
    
    # Move files
    print(f"\n{'🔍 SIMULATING' if dry_run else '📦 MOVING'} files...")
    
    moved_keep = 0
    moved_discard = 0
    errors = []
    
    for orig in keep_originals:
        success, msg = safe_move(orig, keep_dir, dry_run)
        if success:
            moved_keep += 1
        else:
            errors.append(f"{orig.name}: {msg}")
    
    for orig in discard_originals:
        success, msg = safe_move(orig, discard_dir, dry_run)
        if success:
            moved_discard += 1
        else:
            errors.append(f"{orig.name}: {msg}")
    
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
        description="Move original files based on AI scoring decisions"
    )
    parser.add_argument(
        "folder",
        help="Original images directory"
    )
    parser.add_argument(
        "--thumb-dir",
        type=str,
        help="Thumbnail directory containing image_scores.json"
    )
    parser.add_argument(
        "--decisions",
        type=str,
        help="Path to decisions.json file (alternative to --thumb-dir)"
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
    
    if not args.thumb_dir and not args.decisions:
        print("❌ Error: Must specify either --thumb-dir or --decisions")
        parser.print_help()
        return
    
    move_files(
        args.folder,
        args.thumb_dir,
        args.decisions,
        args.content_thresh,
        args.neg_thresh,
        args.dry_run
    )

if __name__ == "__main__":
    main()