# ==================================================
#  Goon5000_Resizer_MkV_WebP_Preserved.py
#  Resizes + optimizes. WebPs are sacred and preserved.
# ==================================================

import os
import signal
import sys
from PIL import Image
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Ctrl+C = clean exit
def ctrl_c_handler(sig, frame):
    print("\n\nResizer interrupted – all progress saved, WebPs untouched.")
    sys.exit(0)
signal.signal(signal.SIGINT, ctrl_c_handler)

def process_image(args):
    path, max_w, max_h, quality = args
    try:
        with Image.open(path) as im:
            orig_w, orig_h = im.size
            filename = os.path.basename(path)

            # Skip if already small enough (but still re-save JPGs with optimization)
            needs_resize = orig_w > max_w or orig_h > max_h

            if needs_resize:
                ratio = min(max_w / orig_w, max_h / orig_h)
                new_size = (int(orig_w * ratio), int(orig_h * ratio))
                im = im.resize(new_size, Image.LANCZOS)

            # ─── WEBP: Convert to JPG, preserve original in webP-OG/ ───
            if path.lower().endswith('.webp'):
                if im.mode in ("RGBA", "LA", "PA"):
                    im = im.convert("RGB")
                jpg_path = os.path.splitext(path)[0] + '.jpg'
                im.save(jpg_path, "JPEG", quality=quality, optimize=True, subsampling="4:2:0")

                # Preserve original WebP
                og_dir = os.path.join(os.path.dirname(path), "webP-OG")
                os.makedirs(og_dir, exist_ok=True)
                shutil.move(path, os.path.join(og_dir, filename))

                return "webp_converted", filename, (orig_w, orig_h)

            # ─── PNG: Convert to JPG, delete original ───
            elif path.lower().endswith('.png'):
                if im.mode in ("RGBA", "LA", "PA"):
                    im = im.convert("RGB")
                jpg_path = os.path.splitext(path)[0] + '.jpg'
                im.save(jpg_path, "JPEG", quality=quality, optimize=True, subsampling="4:2:0")
                os.remove(path)
                return "png_converted", filename, (orig_w, orig_h)

            # ─── JPG/JPEG: Resize + re-optimize in place ───
            elif path.lower().endswith(('.jpg', '.jpeg')):
                im = im.convert("RGB")
                im.save(path, "JPEG", quality=quality, optimize=True, subsampling="4:2:0")
                return "jpg_processed", filename, (orig_w, orig_h)

            else:
                return "skipped_unknown", filename, (orig_w, orig_h)

    except Exception as e:
        return "error", os.path.basename(path), str(e)


def goon5000_resizer(folder=None, max_w=1920, max_h=1080, quality=90, jobs=None):
    folder = folder or os.getcwd()
    jobs = jobs or mp.cpu_count()

    print("GOON5000 RESIZER MK-V (WebP PRESERVED EDITION)")
    print("=" * 68)
    print(f"Folder         : {folder}")
    print(f"Max resolution : {max_w}×{max_h}")
    print(f"JPEG quality   : {quality}")
    print(f"CPU cores      : {jobs}")
    print(f"WebP policy    : CONVERT TO JPG + KEEP ORIGINAL IN webP-OG/")
    print("=" * 68)

    images = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                images.append(os.path.join(root, f))

    if not images:
        print("No images found.")
        return

    print(f"Found {len(images):,} images → commencing holy optimization\n")

    args_list = [(p, max_w, max_h, quality) for p in images]

    stats = {
        "webp_converted": 0,
        "png_converted": 0,
        "jpg_processed": 0,
        "skipped_unknown": 0,
        "error": 0
    }

    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(process_image, a): a[0] for a in args_list}

        for future in tqdm(as_completed(futures),
                           total=len(futures),
                           desc="Resizing · Converting · Preserving WebPs",
                           unit="img",
                           colour="#ff6600",
                           dynamic_ncols=True):
            cat = future.result()[0]
            stats[cat] += 1

    print("\n" + "═" * 68)
    print("GOON5000 RESIZER MISSION COMPLETE")
    print("═" * 68)
    print(f"Total images         : {len(images):,}")
    print(f"WebP → JPG (kept OG) : {stats['webp_converted']:,}")
    print(f"PNG → JPG (deleted)  : {stats['png_converted']:,}")
    print(f"JPG optimized        : {stats['jpg_processed']:,}")
    print(f"Errors               : {stats['error']:,}")
    print("\nAll WebPs are safe in webP-OG/ subfolders.")
    print("Your dataset is now perfectly uniform and training-ready.")
    print("Go train the ultimate model.")
    print("═" * 68)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Goon5000 Resizer – WebPs preserved forever")
    parser.add_argument("folder", nargs="?", default=os.getcwd(), help="Folder to process")
    parser.add_argument("--max-w", type=int, default=1920)
    parser.add_argument("--max-h", type=int, default=1080)
    parser.add_argument("--quality", type=int, default=90)
    parser.add_argument("--jobs", type=int, default=None, help="CPU cores (default: all)")
    args = parser.parse_args()

    goon5000_resizer(args.folder, args.max_w, args.max_h, args.quality, args.jobs)