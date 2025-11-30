"""
thumbnail_generator_cpu.py — Ultra-Fast CPU Multithreaded Thumbnail Creator
Creates 512px thumbnails preserving folder structure — perfect for CLIP sorting.
Zero GPU/Torch dependency → works on any machine.

Usage:
    python thumbnail_generator_cpu.py /path/to/images
    python thumbnail_generator_cpu.py              # Current folder
    python thumbnail_generator_cpu.py --threads 16 --size 384
"""

import os
import argparse
from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import sys

# === CONFIGURATION ===
DEFAULT_SIZE = 512
DEFAULT_QUALITY = 88
DEFAULT_THREADS = min(16, os.cpu_count() * 2 or 8)  # Usually 8–32 threads
SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.gif'}

def create_single_thumbnail(args):
    src_path, source_root, thumb_root, size, quality = args
    
    try:
        # Skip if thumbnail already exists and is newer than source
        rel_path = src_path.relative_to(source_root)
        thumb_path = thumb_root / rel_path
        thumb_path = thumb_path.with_suffix('.jpg')  # Force .jpg output
        
        if thumb_path.exists():
            if thumb_path.stat().st_mtime >= src_path.stat().st_mtime:
                return None  # Already up to date
        
        # Open and resize
        with Image.open(src_path) as img:
            # Convert GIFs and transparent PNGs properly
            if img.format == "GIF" or (img.mode in ("RGBA", "LA", "P") and "transparency" in img.info):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
                
            # High-quality resize + center crop
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            if img.width != size or img.height != size:
                # Pad or crop to exact size
                bg = Image.new("RGB", (size, size), (0, 0, 0))
                offset = ((size - img.width) // 2, (size - img.height) // 2)
                bg.paste(img, offset)
                img = bg
            elif max(img.width, img.height) > size:
                # Rare case: still too big after thumbnail
                img = img.resize((size, size), Image.Resampling.LANCZOS)

        # Create directory and save
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(thumb_path, "JPEG", quality=quality, optimize=True, subsampling=0)
        return str(thumb_path)
    except Exception as e:
        return f"ERROR {src_path.name}: {e}"

def create_thumbnails_cpu(
    source_dir,
    thumb_dir=None,
    size=DEFAULT_SIZE,
    quality=DEFAULT_QUALITY,
    max_workers=DEFAULT_THREADS
):
    source_root = Path(source_dir).resolve()
    thumb_root = Path(thumb_dir).resolve() if thumb_dir else source_root / "thumbnails"

    print("=" * 70)
    print(" THUMBNAIL GENERATOR — CPU MULTITHREADED (NO GPU)")
    print("=" * 70)
    print(f" Source folder: {source_root}")
    print(f" Output folder: {thumb_root}")
    print(f" Size: {size}×{size}px")
    print(f" JPEG Quality: {quality}")
    print(f" Threads: {max_workers}")
    print("=" * 70)

    # Gather all image files
    print("Scanning for images...")
    image_paths = []
    for ext in SUPPORTED_EXTS:
        image_paths.extend(source_root.rglob(f"*{ext}"))
        image_paths.extend(source_root.rglob(f"*{ext.upper()}"))

    # Remove duplicates and skip thumbnails folder
    image_paths = [
        p for p in set(image_paths)
        if "thumbnails" not in p.parts and p.is_file()
    ]

    if not image_paths:
        print("No images found!")
        return

    print(f"Found {len(image_paths):,} images")

    # Prepare tasks
    tasks = [
        (path, source_root, thumb_root, size, quality)
        for path in image_paths
    ]

    # Process with thread pool
    saved_count = 0
    errors = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(create_single_thumbnail, task): task[0] for task in tasks}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Creating thumbnails", unit="img", colour="#00ff99"):
            result = future.result()
            if result is None:
                pass  # Was up to date
            elif result.startswith("ERROR"):
                errors.append(result)
            else:
                saved_count += 1

    # Final report
    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)
    print(f" Total images processed: {len(image_paths):,}")
    print(f" New thumbnails created: {saved_count:,}")
    print(f" Skipped (already up-to-date): {len(image_paths) - saved_count:,}")
    if errors:
        print(f" Errors: {len(errors)}")
        if len(errors) < 20:
            for e in errors[:10]:
                print(f"   {e}")
            if len(errors) > 10:
                print(f"   ... and {len(errors)-10} more")
    print(f"\nThumbnails ready at:\n   {thumb_root}")
    print(f"\nNext: Run your CLIP sorter on the thumbnails folder!")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Fast CPU thumbnail generator for AI sorting")
    parser.add_argument("folder", nargs="?", default=".", help="Source folder (default: current)")
    parser.add_argument("--thumb-dir", type=str, help="Custom output folder (default: <source>/thumbnails)")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE, help=f"Thumbnail size (default: {DEFAULT_SIZE})")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help="JPEG quality 1-100 (default: 88)")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS, help=f"Number of threads (default: auto)")

    args = parser.parse_args()

    if not Path(args.folder).exists():
        print(f"Folder not found: {args.folder}")
        sys.exit(1)

    create_thumbnails_cpu(
        source_dir=args.folder,
        thumb_dir=args.thumb_dir,
        size=args.size,
        quality=args.quality,
        max_workers=args.threads
    )

if __name__ == "__main__":
    main()