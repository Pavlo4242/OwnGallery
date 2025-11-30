"""
Ultra-Optimized AI Image Sorter
Improvements over Version 2:
- Larger adaptive batch sizes
- Mixed precision training (AMP)
- Persistent workers
- Memory pinning
- Progress bar with ETA
"""

import os
import sys
import shutil
import json
import time
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast
from PIL import Image
from tqdm import tqdm

# === CONFIGURATION ===
DEFAULT_CONTENT_THRESH = 0.25
DEFAULT_NEGATIVE_THRESH = 0.22
DB_FILENAME = "image_scores.json"
# ====================

def check_setup():
    try:
        import torch
        from PIL import Image
        from transformers import CLIPProcessor, CLIPModel
        return True
    except ImportError:
        print("❌ Missing dependencies. Install with:")
        print("pip install torch torchvision transformers pillow tqdm")
        return False

def load_model():
    from transformers import CLIPModel, CLIPProcessor
    print("🔄 Loading AI Model...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Device: {device.upper()}")
    
    if device == "cuda":
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
    
    model_name = "laion/CLIP-ViT-L-14-laion2B-s32B-b82K"
    try:
        model = CLIPModel.from_pretrained(model_name).to(device)
        processor = CLIPProcessor.from_pretrained(model_name)
    except:
        print("⚠️  Falling back to OpenAI model...")
        model_name = "openai/clip-vit-large-patch14"
        model = CLIPModel.from_pretrained(model_name).to(device)
        processor = CLIPProcessor.from_pretrained(model_name)
    
    model.eval()  # Set to evaluation mode
    
    # Use half precision on GPU
    if device == "cuda":
        model = model.half()
    
    return model, processor, device

def get_prompt_config():
    """Returns all prompts with their category mappings"""
    prompts_real = ["photograph", "photorealistic", "raw photo", "dslr", "4k", "8k",
                   "detailed skin texture", "masterpiece", "nude", "erotic photography",
                   "nsfw", "uncensored"]
    prompts_cgi = ["3d render", "unreal engine 5", "octane render", "blender",
                  "digital art", "3d anime", "highly detailed cg", "3d hentai",
                  "hyper-realistic", "realistic", "nsfw anime", "explicit", "detailed anatomy"]
    prompts_neg = ["sketch", "pencil drawing", "doodle", "flat color", "cel shading",
                  "pig", "cow", "loli", "mlp", "pregnant", "vector art", "monochrome",
                  "low quality", "text", "watermark", "censored", "mosaic", "blur", "bad anatomy"]
    prompts_aesthetic = ["masterpiece", "best quality", "extremely detailed", "absurdres",
                        "incredible", "award winning"]
    prompts_porn = ["porn", "hardcore sex", "explicit sex", "penetration", "fellatio", "xxx"]
    prompts_hentai = ["hentai", "ahegao", "2d anime", "anime style nsfw", "ecchi", "oppai"]
    prompts_art = ["digital art", "illustration", "painting", "artstation",
                  "deviantart", "concept art 8k"]
    prompts_censored = ["censored", "mosaic censor", "bars", "black bars", "convenience store censor"]
    prompts_loli = ["loli", "shota", "toddlercon", "flat chest", "childlike"]
    prompts_guro = ["guro", "gore", "ryona", "dismemberment", "bloodbath"]
    prompts_furry = ["furry", "anthro", "scalies", "fursona", "yiff"]
    prompts_bdsm = ["bdsm", "bondage", "shibari", "rope bondage", "leather", "latex", "gimp suit", "ballgag"]
    prompts_feet = ["feet", "foot fetish", "barefoot", "soles", "toes", "foot worship"]
    prompts_bbw = ["bbw", "chubby", "curvy", "thick", "plump", "ssbbw"]
    prompts_cosplay = ["cosplay", "costume", "maid outfit", "bunny girl", "catgirl", "school uniform"]
    prompts_monster = ["monster girl", "tentacles", "slime girl", "demon girl", "succubus", "lamia"]
    prompts_futa = ["futanari", "dickgirl", "trap", "newhalf"]
    prompts_pegging = ["pegging", "strapon", "female domination", "femdom"]
    prompts_gay = ["gay", "yaoi", "male x male", "bara", "muscular male"]
    prompts_lesbian = ["lesbian", "yuri", "girl on girl", "tribadism"]
    prompts_pov = ["pov", "point of view", "first person view"]
    prompts_closeup = ["closeup", "macro", "extreme closeup", "spread pussy", "spread anus"]
    prompts_cum = ["cum", "bukkake", "cumshot", "facial", "creampie", "ahegao cum"]
    prompts_anal = ["anal", "buttsex", "anal sex", "ass fucking"]
    prompts_group = ["group sex", "orgy", "gangbang", "foursome", "threesome"]
    prompts_outdoor = ["outdoor", "public sex", "exhibitionism", "forest", "beach sex"]

    prompt_sections = [
        ("real", prompts_real), ("cgi", prompts_cgi), ("neg", prompts_neg),
        ("aesthetic", prompts_aesthetic), ("porn", prompts_porn), ("hentai", prompts_hentai),
        ("art", prompts_art), ("censored", prompts_censored), ("loli", prompts_loli),
        ("guro", prompts_guro), ("furry", prompts_furry), ("bdsm", prompts_bdsm),
        ("feet", prompts_feet), ("bbw", prompts_bbw), ("cosplay", prompts_cosplay),
        ("monster", prompts_monster), ("futa", prompts_futa), ("pegging", prompts_pegging),
        ("gay", prompts_gay), ("lesbian", prompts_lesbian), ("pov", prompts_pov),
        ("closeup", prompts_closeup), ("cum", prompts_cum), ("anal", prompts_anal),
        ("group", prompts_group), ("outdoor", prompts_outdoor)
    ]
    
    all_prompts = []
    section_lengths = {}
    offsets = {}
    cumsum = 0
    
    for name, prompts in prompt_sections:
        all_prompts.extend(prompts)
        section_lengths[name] = len(prompts)
        offsets[name] = cumsum
        cumsum += len(prompts)
    
    return all_prompts, section_lengths, offsets

class ImageListDataset(Dataset):
    """Optimized dataset with error handling"""
    def __init__(self, image_paths, processor, target_size=224):
        self.image_paths = image_paths
        self.processor = processor
        self.target_size = target_size
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        path = self.image_paths[idx]
        try:
            image = Image.open(path).convert("RGB")
            # Use processor's built-in preprocessing
            pixel_values = self.processor(
                images=image, 
                return_tensors="pt"
            ).pixel_values.squeeze(0)
            return pixel_values, path
        except Exception as e:
            # Return zero tensor for corrupt images
            return torch.zeros((3, self.target_size, self.target_size)), "CORRUPT"

def get_optimal_batch_size(device):
    """Determine optimal batch size based on available VRAM"""
    if device == "cpu":
        return 16
    
    try:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        if vram_gb >= 16:
            return 64  # High-end GPU
        elif vram_gb >= 8:
            return 48  # Mid-range GPU
        elif vram_gb >= 6:
            return 32  # Entry-level GPU
        else:
            return 16  # Low VRAM
    except:
        return 32  # Default fallback

def scan_thumbnails(source_root, custom_thumb_dir=None, force_rescan=False):
    """Optimized batch processing with progress tracking"""
    source_root = Path(source_root).resolve()
    
    # Determine thumbnail directory
    if custom_thumb_dir:
        thumb_dir = Path(custom_thumb_dir).resolve()
        print(f"📂 Custom thumbnail directory: {thumb_dir}")
    else:
        thumb_dir = source_root / "thumbnails"
    
    if not thumb_dir.exists():
        print(f"❌ Thumbnails folder not found: {thumb_dir}")
        print(f"💡 Run: python thumbnail_generator.py {source_root}")
        return {}, {}
    
    if not check_setup():
        return {}, {}
    
    # Build thumbnail → original mapping
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    thumb_to_orig = {}
    
    print("🔍 Mapping thumbnails to originals...")
    for thumb_path in thumb_dir.rglob('*'):
        if thumb_path.suffix.lower() not in valid_exts:
            continue
        
        rel_path = thumb_path.relative_to(thumb_dir)
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
    
    if not force_rescan and db_path.exists():
        try:
            with open(db_path, 'r') as f:
                score_data = json.load(f)
            print(f"💾 Loaded {len(score_data):,} existing scores")
        except:
            print("⚠️  Database corrupted, starting fresh")
    
    # Find new thumbnails to process
    new_thumbs = [t for t in thumb_to_orig.keys() if t not in score_data]
    
    if not new_thumbs:
        print("✅ All thumbnails already scored!")
        return score_data, thumb_to_orig
    
    print(f"\n🎯 Processing {len(new_thumbs):,} new thumbnails...")
    
    # Load model and prepare prompts
    model, processor, device = load_model()
    all_prompts, section_lengths, offsets = get_prompt_config()
    
    # Pre-compute text embeddings (ONCE)
    print("📝 Pre-computing text embeddings...")
    with torch.no_grad():
        text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True).to(device)
        if device == "cuda":
            # Use automatic mixed precision for text encoding
            with autocast():
                text_outputs = model.get_text_features(**text_inputs)
        else:
            text_outputs = model.get_text_features(**text_inputs)
        
        text_embeds = text_outputs / text_outputs.norm(p=2, dim=-1, keepdim=True)
    
    # Setup DataLoader with optimizations
    dataset = ImageListDataset(new_thumbs, processor)
    batch_size = get_optimal_batch_size(device)
    
    print(f"⚙️  Batch size: {batch_size}")
    
    # Persistent workers speed up data loading
    num_workers = 4 if device == "cuda" else 2
    
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        shuffle=False,
        pin_memory=(device == "cuda"),  # Speed up CPU→GPU transfer
        persistent_workers=(num_workers > 0)
    )
    
    print(f"🚀 Starting batch processing...\n")
    
    start_time = time.time()
    processed = 0
    
    try:
        with torch.no_grad():
            # Use tqdm for progress bar
            pbar = tqdm(loader, desc="Processing", unit="batch")
            
            for images, paths in pbar:
                # Filter corrupt images
                valid_mask = [p != "CORRUPT" for p in paths]
                if not any(valid_mask):
                    continue
                
                images = images[valid_mask].to(device)
                current_paths = [p for p, m in zip(paths, valid_mask) if m]
                
                # Use AMP for faster inference on GPU
                if device == "cuda":
                    with autocast():
                        image_outputs = model.get_image_features(pixel_values=images)
                else:
                    image_outputs = model.get_image_features(pixel_values=images)
                
                # Normalize embeddings
                image_embeds = image_outputs / image_outputs.norm(p=2, dim=-1, keepdim=True)
                
                # Calculate similarity scores
                sims = (image_embeds @ text_embeds.T).float().cpu().numpy()
                
                # Extract category scores
                for i, path in enumerate(current_paths):
                    row = sims[i]
                    scores = {}
                    for name, length in section_lengths.items():
                        start = offsets[name]
                        end = start + length
                        scores[name] = float(row[start:end].max())
                    
                    score_data[path] = scores
                    processed += 1
                
                # Update progress bar with speed
                elapsed = time.time() - start_time
                img_per_sec = processed / elapsed if elapsed > 0 else 0
                pbar.set_postfix({
                    'imgs/s': f'{img_per_sec:.1f}',
                    'total': f'{processed:,}/{len(new_thumbs):,}'
                })
                
                # Periodic auto-save
                if processed % 500 == 0:
                    with open(db_path, 'w') as f:
                        json.dump(score_data, f, indent=2)
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user. Saving progress...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Final save
    with open(db_path, 'w') as f:
        json.dump(score_data, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n✅ Processed {processed:,} images in {elapsed:.1f}s ({processed/elapsed:.1f} imgs/s)")
    print(f"💾 Database saved: {db_path}")
    
    return score_data, thumb_to_orig

def apply_thresholds(score_data, thumb_to_orig, content_thresh, neg_thresh):
    """Apply filtering thresholds"""
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
        return
    
    dest_path = dest_folder / src.name
    counter = 1
    
    while dest_path.exists():
        if src.samefile(dest_path):
            return
        dest_path = dest_folder / f"{src.stem}_{counter}{src.suffix}"
        counter += 1
    
    try:
        shutil.move(str(src), str(dest_path))
    except Exception as e:
        print(f"⚠️  Move failed for {src.name}: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Ultra-Fast AI Image Sorter"
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
        help="Custom thumbnail directory"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full re-scan (ignore existing scores)"
    )
    
    args = parser.parse_args()
    source_dir = Path(args.folder).resolve()
    db_path = source_dir / DB_FILENAME
    
    # Force rescan if requested
    if args.force and db_path.exists():
        print("🔥 FORCE MODE: Deleting old database")
        db_path.unlink()
    
    print("=" * 60)
    print("🚀 ULTRA-FAST AI IMAGE SORTER")
    if args.force:
        print("⚡ FORCE RE-SCAN ENABLED")
    print("=" * 60)
    print(f"📁 Working Directory: {source_dir}\n")
    
    # PHASE 1: SCAN
    score_data, thumb_to_orig = scan_thumbnails(
        source_dir, 
        args.thumb_dir,
        args.force
    )
    
    if not score_data:
        print("❌ No data found. Exiting.")
        return
    
    # PHASE 2: INTERACTIVE FILTERING
    c_thresh = DEFAULT_CONTENT_THRESH
    n_thresh = DEFAULT_NEGATIVE_THRESH
    
    while True:
        print("\n" + "=" * 60)
        print(f"⚙️  CURRENT THRESHOLDS:")
        print(f"   Content (Real/CGI): {c_thresh}")
        print(f"   Negative (Trash):   {n_thresh}")
        print("=" * 60)
        
        keep_files, discard_files = apply_thresholds(
            score_data, thumb_to_orig, c_thresh, n_thresh
        )
        
        print(f"\n📊 PREVIEW:")
        print(f"   ✅ KEEP:    {len(keep_files):,} files")
        print(f"   ❌ DISCARD: {len(discard_files):,} files")
        
        print("\n🎯 OPTIONS:")
        print("  [1] Adjust Content Threshold")
        print("  [2] Adjust Negative Threshold")
        print("  [3] 🚀 EXECUTE MOVE")
        print("  [4] Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            try:
                c_thresh = float(input("New Content Threshold (0.0-1.0): "))
            except:
                print("⚠️  Invalid input")
        
        elif choice == '2':
            try:
                n_thresh = float(input("New Negative Threshold (0.0-1.0): "))
            except:
                print("⚠️  Invalid input")
        
        elif choice == '3':
            total = len(keep_files) + len(discard_files)
            print(f"\n⚠️  WARNING: Moving {total:,} files")
            confirm = input("Continue? (yes/no): ").strip().lower()
            
            if confirm == 'yes':
                keep_dir = source_dir / "Keep"
                discard_dir = source_dir / "Discard"
                keep_dir.mkdir(exist_ok=True)
                discard_dir.mkdir(exist_ok=True)
                
                print("\n📦 Moving files...")
                for f in tqdm(keep_files, desc="Keep"):
                    safe_move(f, keep_dir)
                for f in tqdm(discard_files, desc="Discard"):
                    safe_move(f, discard_dir)
                
                print("✅ Complete! Thumbnails preserved for re-sorting.")
                break
        
        elif choice == '4':
            print("👋 Goodbye!")
            break

if __name__ == "__main__":
    main()