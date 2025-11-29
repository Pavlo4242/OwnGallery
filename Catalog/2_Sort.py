"""
sorter_thumbnails.py — AI Sorter that processes thumbnails but moves ORIGINALS
Works with thumbnail_generator.py output structure

Usage:
    1. python thumbnail_generator.py /path/to/images
    2. python sorter_thumbnails.py /path/to/images
"""

import os
import sys
import shutil
import json
import time
from pathlib import Path

# === DEFAULT CONFIGURATION ===
DEFAULT_CONTENT_THRESH = 0.25
DEFAULT_NEGATIVE_THRESH = 0.22
DB_FILENAME = "image_scores.json"
# =============================

def check_setup():
    try:
        import torch
        from PIL import Image
        from transformers import CLIPProcessor, CLIPModel
        return True
    except ImportError:
        return False

def load_model():
    from transformers import CLIPProcessor, CLIPModel
    print("Loading AI Model (LAION Uncensored)...")
    model_name = "laion/CLIP-ViT-L-14-laion2B-s32B-b82K"
    try:
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        return model, processor
    except:
        print("Falling back to OpenAI model...")
        model_name = "openai/clip-vit-large-patch14"
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        return model, processor

def get_image_scores(model, processor, image_path):
    import torch
    from PIL import Image
    try:
        image = Image.open(image_path).convert("RGB")
        
        prompts_real = ["photograph", "photorealistic", "raw photo", "dslr", "4k", "8k", "detailed skin texture", "masterpiece", "nude", "erotic photography", "nsfw", "uncensored"]
        prompts_cgi = ["3d render", "unreal engine 5", "octane render", "blender", "digital art", "3d anime", "highly detailed cg", "3d hentai", "nsfw anime", "explicit", "detailed anatomy"]
        prompts_neg = ["sketch", "pencil drawing", "doodle", "flat color", "cel shading", "vector art", "monochrome", "low quality", "text", "watermark", "censored", "mosaic", "blur", "bad anatomy"]

        all_prompts = prompts_real + prompts_cgi + prompts_neg
        inputs = processor(text=all_prompts, images=image, return_tensors="pt", padding=True, truncation=True)

        with torch.no_grad():
            outputs = model(**inputs)
            
        image_embeds = outputs.image_embeds / outputs.image_embeds.norm(p=2, dim=-1, keepdim=True)
        text_embeds = outputs.text_embeds / outputs.text_embeds.norm(p=2, dim=-1, keepdim=True)
        sims = (image_embeds @ text_embeds.T).squeeze(0)

        len_real = len(prompts_real)
        len_cgi = len(prompts_cgi)
        max_real = sims[:len_real].max().item()
        max_cgi = sims[len_real : len_real + len_cgi].max().item()
        max_neg = sims[len_real + len_cgi :].max().item()
        
        return {"real": max_real, "cgi": max_cgi, "neg": max_neg}
    except Exception as e:
        print(f"Error scanning {image_path}: {e}")
        return None

def scan_thumbnails(source_root, custom_thumb_dir=None):
    """Scan thumbnails folder and map back to originals"""
    source_root = Path(source_root).resolve()
    
    if custom_thumb_dir:
        thumb_dir = Path(custom_thumb_dir).resolve()
        print(f"📂 Using custom thumbnail directory: {thumb_dir}")
    else:
        thumb_dir = source_root / "thumbnails"
    
    if not thumb_dir.exists():
        print(f"❌ Thumbnails folder not found: {thumb_dir}")
        print(f"💡 Run: python thumbnail_generator.py {source_root}")
        if custom_thumb_dir:
            print(f"   Or: python thumbnail_generator.py {source_root} --thumb-dir {custom_thumb_dir}")
        return {}, {}
    
    if not check_setup():
        return {}, {}
    
    # Build mapping: thumbnail_path -> original_path
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    thumb_to_orig = {}
    
    print("🔍 Mapping thumbnails to originals...")
    for thumb_path in thumb_dir.rglob('*'):
        if thumb_path.suffix.lower() not in valid_exts:
            continue
        
        # Calculate relative path and find original
        rel_path = thumb_path.relative_to(thumb_dir)
        
        # Try to find original with any valid extension
        orig_stem = source_root / rel_path.parent / rel_path.stem
        for ext in valid_exts:
            candidate = orig_stem.with_suffix(ext)
            if candidate.exists():
                thumb_to_orig[str(thumb_path)] = str(candidate)
                break
    
    print(f"📸 Found {len(thumb_to_orig):,} thumbnail↔original pairs")
    
    # Load existing database
    db_path = source_root / DB_FILENAME
    score_data = {}
    if db_path.exists():
        try:
            with open(db_path, 'r') as f:
                score_data = json.load(f)
            print(f"💾 Loaded {len(score_data)} existing scores")
        except:
            print("⚠️  Database corrupted, starting fresh")
    
    # Identify new thumbnails to scan
    new_thumbs = [t for t in thumb_to_orig.keys() if t not in score_data]
    
    if not new_thumbs:
        print("✅ All thumbnails already scored!")
        return score_data, thumb_to_orig
    
    print(f"🎯 Scanning {len(new_thumbs)} new thumbnails with AI...\n")
    model, processor = load_model()
    
    count = 0
    try:
        for thumb_path in new_thumbs:
            scores = get_image_scores(model, processor, thumb_path)
            if scores:
                score_data[thumb_path] = scores
                count += 1
                
                if count % 50 == 0:
                    print(f"📊 Scanned {count}/{len(new_thumbs)}... (Auto-saving)")
                    with open(db_path, 'w') as f:
                        json.dump(score_data, f, indent=2)
                        
    except KeyboardInterrupt:
        print("\n⚠️  Scan interrupted! Saving progress...")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        print("💾 Saving what we have...")
    
    # Final save
    with open(db_path, 'w') as f:
        json.dump(score_data, f, indent=2)
    print(f"✅ Database updated: {db_path}")
    
    return score_data, thumb_to_orig

def apply_thresholds(score_data, thumb_to_orig, content_thresh, neg_thresh):
    """Apply thresholds but return ORIGINAL file paths"""
    keep_list = []
    discard_list = []
    
    for thumb_path, scores in score_data.items():
        orig_path = thumb_to_orig.get(thumb_path)
        if not orig_path or not Path(orig_path).exists():
            continue
        
        is_good = (scores['real'] > content_thresh) or (scores['cgi'] > content_thresh)
        is_not_trash = scores['neg'] < neg_thresh
        
        if is_good and is_not_trash:
            keep_list.append(orig_path)
        else:
            discard_list.append(orig_path)
    
    return keep_list, discard_list

def safe_move(src, dest_folder):
    """Move file with duplicate handling"""
    src = Path(src)
    dest_folder = Path(dest_folder)
    
    if src.parent == dest_folder:
        return  # Already there
    
    dest_path = dest_folder / src.name
    counter = 1
    
    while dest_path.exists():
        if src.samefile(dest_path):
            return  # Same file
        dest_path = dest_folder / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    
    try:
        shutil.move(str(src), str(dest_path))
    except Exception as e:
        print(f"⚠️  Move failed: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="AI Image Sorter (processes thumbnails, moves originals)"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=os.getcwd(),
        help="Source folder containing original images"
    )
    parser.add_argument(
        "--thumb-dir",
        type=str,
        default=None,
        help="Custom thumbnail directory path (default: <folder>/thumbnails)"
    )
    args = parser.parse_args()
    
    source_dir = Path(args.folder).resolve()
    print("="*60)
    print("AI IMAGE SORTER (Thumbnail Mode)")
    print("="*60)
    print(f"📁 Working Directory: {source_dir}\n")
    
    # PHASE 1: SCAN THUMBNAILS
    score_data, thumb_to_orig = scan_thumbnails(source_dir, args.thumb_dir)
    
    if not score_data:
        print("❌ No data found. Exiting.")
        return
    
    # PHASE 2: INTERACTIVE FILTERING
    c_thresh = DEFAULT_CONTENT_THRESH
    n_thresh = DEFAULT_NEGATIVE_THRESH
    
    while True:
        print("\n" + "="*60)
        print(f"⚙️  CURRENT SETTINGS:")
        print(f"   Content Threshold: {c_thresh}")
        print(f"   Negative Threshold: {n_thresh}")
        print("="*60)
        
        keep_files, discard_files = apply_thresholds(
            score_data, thumb_to_orig, c_thresh, n_thresh
        )
        
        print(f"\n📊 PREVIEW RESULTS:")
        print(f"   ✅ KEEP:    {len(keep_files):,}")
        print(f"   ❌ DISCARD: {len(discard_files):,}")
        
        print("\n🎯 OPTIONS:")
        print("  [1] Change Content Threshold (Realism/CGI)")
        print("  [2] Change Negative Threshold (Flat/Sketch)")
        print("  [3] 🚀 EXECUTE MOVE (Moves ORIGINAL files)")
        print("  [4] Exit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            try:
                c_thresh = float(input("New Content Threshold (e.g., 0.25): "))
            except:
                print("⚠️  Invalid number")
        
        elif choice == '2':
            try:
                n_thresh = float(input("New Negative Threshold (e.g., 0.22): "))
            except:
                print("⚠️  Invalid number")
        
        elif choice == '3':
            print(f"\n⚠️  WARNING: This will move {len(keep_files) + len(discard_files):,} ORIGINAL files")
            confirm = input("Continue? (y/n): ").strip().lower()
            
            if confirm == 'y':
                keep_dir = source_dir / "Keep"
                discard_dir = source_dir / "Discard"
                keep_dir.mkdir(exist_ok=True)
                discard_dir.mkdir(exist_ok=True)
                
                print("\n📦 Moving files...")
                for f in keep_files:
                    safe_move(f, keep_dir)
                for f in discard_files:
                    safe_move(f, discard_dir)
                
                print("✅ Done! Thumbnails remain unchanged.")
                print("💡 You can re-run this script to re-sort.")
                break
        
        elif choice == '4':
            break

if __name__ == "__main__":
    main()