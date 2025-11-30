#!/usr/bin/env python
"""
5_ExportRepSampleForGallery.py

Converts representative_gallery.json (from CreateRepSample.py)
into everything needed for:
   • makegallery.py  → clean thumbnails folder + working web server
   • previewer.py    → fake image_scores.json so you can interactively browse/tune

Usage:
    python 5_ExportRepSampleForGallery.py "Q:\Collection Zprion\representative_gallery.json" --out Q:\RepSample_Preview
"""

import json
import argparse
from pathlib import Path
import shutil
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Convert RepSample JSON → Gallery + Previewer ready")
    parser.add_argument("input_json", type=str, help="Path to representative_gallery.json")
    parser.add_argument("--out", "-o", type=str, required=True, help="Output root folder (will be created)")
    parser.add_argument("--copy-thumbs", action="store_true", help="Copy thumbnails (safer, uses space)")
    parser.add_argument("--symlink", action="store_true", help="Use symlinks instead of copying (fast, but Windows needs admin/dev mode)")
    args = parser.parse_args()

    in_path = Path(args.input_json)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    thumbs_out = out_root / "thumbnails"
    fullres_out = out_root / "gallery"  # optional
    thumbs_out.mkdir(exist_ok=True)
    fullres_out.mkdir(exist_ok=True)

    print(f"Loading {in_path} ...")
    with open(in_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    gallery_items = data["gallery"]
    print(f"Found {len(gallery_items):,} representative images")

    # We'll generate fake but realistic scores so previewer.py works nicely
    fake_scores_template = {
        "real": 0.75,
        "cgi": 0.85,
        "neg": 0.05,        # very low = high quality
        "aesthetic": 0.82,
        "porn": 0.60,
        "hentai": 0.78,
        "art": 0.88,
        "censored": 0.10,
        "loli": 0.05,
        "guro": 0.02,
        "furry": 0.08,
        # ... add more if you want
    }

    # Adjust slightly based on type
    score_variants = {
        "visual_unique":       {"real": 0.88, "cgi": 0.72, "aesthetic": 0.90},
        "visual_collection":   {"real": 0.70, "cgi": 0.90, "aesthetic": 0.78},
        "visual_representative": {"real": 0.78, "cgi": 0.82, "aesthetic": 0.85},
    }

    scores_db = {}

    print("Processing images...")
    for item in tqdm(gallery_items, desc="Copying & scoring"):
        thumb_src = Path(item["thumb"])
        orig_src = Path(item["path"])

        if not thumb_src.exists():
            print(f"Warning: Thumbnail missing: {thumb_src}")
            continue

        # Destination paths (flatten or keep structure — I recommend keeping folder structure)
        rel_thumb = thumb_src.relative_to(thumb_src.anchor)  # keeps subfolders
        dest_thumb = thumbs_out / rel_thumb
        dest_thumb.parent.mkdir(parents=True, exist_ok=True)

        dest_full = fullres_out / rel_thumb.with_name(orig_src.name)
        dest_full.parent.mkdir(parents=True, exist_ok=True)

        # Copy or symlink thumbnail
        if args.symlink:
            if dest_thumb.exists(): dest_thumb.unlink(missing_ok=True)
            try:
                dest_thumb.parent.mkdir(parents=True, exist_ok=True)
                dest_thumb.symlink_to(thumb_src)
            except OSError:
                print("Symlink failed (normal on Windows without dev mode), falling back to copy")
                shutil.copy2(thumb_src, dest_thumb)
        else:
            shutil.copy2(thumb_src, dest_thumb)

        # Copy full-res (optional, only if you want lightbox)
        if orig_src.exists():
            shutil.copy2(orig_src, dest_full)

        # Generate fake scores
        base = fake_scores_template.copy()
        variant = score_variants.get(item["type"], {})
        base.update(variant)
        # Add tiny random noise so previewer graphs look natural
        import random
        for k in base:
            base[k] += random.uniform(-0.05, 0.05)
            base[k] = max(0.0, min(0.99, base[k]))

        scores_db[str(dest_thumb)] = base

    # Save image_scores.json for previewer.py
    scores_path = out_root / "image_scores.json"
    with open(scores_path, 'w', encoding='utf-8') as f:
        json.dump(scores_db, f, indent=2)

    # Save a tiny manifest
    manifest = {
        "source_repsample": str(in_path),
        "generated_at": data["generated_at"],
        "total_images": len(gallery_items),
        "stats": data["stats"],
        "note": "This folder is ready for makegallery.py and previewer.py"
    }
    with open(out_root / "README.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "="*60)
    print("SUCCESS! Your representative sample is ready")
    print("="*60)
    print(f"   Output folder: {out_root}")
    print(f"   Thumbnails:   {thumbs_out} ({len(list(thumbs_out.rglob('*.*'))):,} files)")
    print(f"   Full-res:     {fullres_out} (optional lightbox)")
    print(f"   Scores DB:    {scores_path}")
    print("\nNext steps:")
    print("   1. cd into the output folder")
    print("   2. python makegallery.py")
    print("   3. Open http://localhost:8000")
    print("   4. Or run: python previewer.py .   (to fine-tune thresholds visually)")
    print("="*60)

if __name__ == "__main__":
    main()