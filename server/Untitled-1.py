#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
convert_clip_to_gallery.py

Standalone script to convert a CLIP representative_gallery.json
into the image_scores.json format used by the HTML gallery.

Usage:
    python convert_clip_to_gallery.py                               # interactive mode
    python convert_clip_to_gallery.py "D:\Images\baaaaaac"           # auto-mode (recommended)
"""

import json
import sys
from pathlib import Path


def convert_to_gallery_format(clip_output_file: Path, target_dir: Path):
    """Convert CLIP gallery JSON → image_scores.json"""

    # Load the CLIP output
    with open(clip_output_file, 'r', encoding='utf-8') as f:
        clip_data = json.load(f)

    image_scores = {}

    for item in clip_data.get('gallery', []):
        full_path = Path(item['path'])

        # Make path relative to the target directory (for clean web URLs)
        try:
            rel_path = full_path.relative_to(target_dir)
        except ValueError:
            # Fallback: if the image is outside the target folder, keep full relative from drive root
            rel_path = full_path

        rel_path_str = str(rel_path).replace('\\', '/')

        cluster_size = item.get('cluster_size', 1)
        group_id = item.get('group_id', 0)

        image_scores[rel_path_str] = {
            'real': min(0.95, 0.15 + (cluster_size / 100)),   # bigger cluster → looks more "real"
            'cgi': max(0.05, 0.55 - (cluster_size / 120)),
            'neg': max(0.01, 0.35 - (cluster_size / 60)),
            'porn': 0.30,
            'hentai': 0.18,
            'loli': 0.02,
            'guro': 0.01,
            'censored': 0.12,
            'feet': 0.06,
            'furry': 0.04,
            'bdsm': 0.09,
            'cluster_id': group_id,
            'cluster_size': cluster_size,
            'selection_type': item.get('type', 'unknown')
        }

    # Write image_scores.json
    output_file = target_dir / 'image_scores.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(image_scores, f, indent=2, ensure_ascii=False)

    print(f"Converted to gallery format: {output_file}")
    print(f"Processed {len(image_scores)} images")
    return image_scores


def main():
    # Default values for your specific case
    DEFAULT_CLIP_FILE = Path(r"D:\Images\baaaaaac\representative_gallery.json")
    DEFAULT_TARGET_DIR = Path(r"D:\Images\baaaaaac")   # change if you want scores somewhere else

    if len(sys.argv) > 1:
        # Auto-mode: first argument = folder that contains representative_gallery.json
        folder = Path(sys.argv[1]).resolve()
        clip_file = folder / "representative_gallery.json"
        target_dir = folder
    else:
        # Interactive fallback
        print("CLIP → Gallery converter")
        clip_file = DEFAULT_CLIP_FILE
        target_dir = DEFAULT_TARGET_DIR

        print(f"\nUsing input file  : {clip_file}")
        print(f"Output directory  : {target_dir}\n")

        if not clip_file.exists():
            print("Input file not found! Please pass the correct folder as argument.")
            sys.exit(1)

    if not clip_file.exists():
        print(f"Error: File not found: {clip_file}")
        sys.exit(1)

    convert_to_gallery_format(clip_file, target_dir)


if __name__ == "__main__":
    main()