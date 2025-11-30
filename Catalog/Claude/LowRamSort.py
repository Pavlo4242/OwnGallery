"""
LOW VRAM OPTIMIZED SORTER for GTX 1650 / 4GB GPUs
Key optimizations:
- Smaller CLIP model (OpenAI base)
- Larger batch sizes (less overhead)
- No FP16 (better compatibility)
- Gradient checkpointing
- Aggressive memory clearing
"""

import os
import sys
import shutil
import json
import time
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from tqdm import tqdm
import gc

# === CONFIGURATION ===
DEFAULT_CONTENT_THRESH = 0.25
DEFAULT_NEGATIVE_THRESH = 0.22
DB_FILENAME = "image_scores.json"
VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
# ====================

def clear_gpu_memory():
    """Aggressively clear GPU memory"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()

def load_clip_model():
    """Load lightweight CLIP model optimized for 4GB VRAM"""
    from transformers import CLIPModel, CLIPProcessor
    
    print("\n" + "=" * 60)
    print("🤖 LOADING OPTIMIZED MODEL (4GB VRAM)")
    print("=" * 60)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Device: {device.upper()}")
        
    
    if device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"   GPU: {gpu_name}")
        print(f"   VRAM: {vram_gb:.1f}GB")
    
    # Use smaller, faster model for low VRAM
    model_name = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
    #model_name = "openai/clip-vit-base-patch32"  # Much smaller than ViT-L
    print(f"📦 Loading {model_name} (lightweight)...")
    
    model = CLIPModel.from_pretrained(model_name).to(device)
    processor = CLIPProcessor.from_pretrained(model_name)
    use_safetensors=True   # ← add this line
    model.eval()
    
    print("✅ Model loaded (FP32 for stability)")
    
    return model, processor, device

def get_prompt_config():
    """Streamlined prompts for faster processing"""
    prompts = {
        "real": ["photograph", "photorealistic", "raw photo", "dslr", "detailed skin", "nude photo"],
        "cgi": ["3d render", "cgi", "digital art", "3d anime", "realistic render"],
        "neg": ["sketch", "drawing", "low quality", "text", "watermark", "blur", "bad anatomy"],
        "aesthetic": ["masterpiece", "best quality", "detailed", "award winning"],
        "porn": ["porn", "explicit sex", "xxx"],
        "hentai": ["hentai", "anime nsfw", "ecchi"],
        "art": ["digital art", "illustration", "painting"],
        "censored": ["censored", "mosaic", "bars"],
        "loli": ["loli", "childlike"],
        "guro": ["gore", "guro"],
        "furry": ["furry", "anthro"],
        "bdsm": ["bdsm", "bondage", "latex"],
        "feet": ["feet", "foot fetish"],
        "bbw": ["bbw", "curvy", "thick"],
        "cosplay": ["cosplay", "costume"],
        "anal": ["anal sex"],
        "group": ["group sex", "orgy"],
    }
    
    all_prompts = []
    section_lengths = {}
    offsets = {}
    cumsum = 0
    
    for name, prompt_list in prompts.items():
        all_prompts.extend(prompt_list)
        section_lengths[name] = len(prompt_list)
        offsets[name] = cumsum
        cumsum += len(prompt_list)
    
    return all_prompts, section_lengths, offsets

class ImageDataset(Dataset):
    """Memory-efficient dataset"""
    def __init__(self, image_paths, processor):
        self.paths = image_paths
        self.processor = processor
    
    def __len__(self):
        return len(self.paths)
    
    def __getitem__(self, idx):
        path = self.paths[idx]
        try:
            image = Image.open(path).convert("RGB")
            # Resize to 224 before processing to save memory
            image = image.resize((224, 224), Image.LANCZOS)
            pixel_values = self.processor(
                images=image,
                return_tensors="pt"
            ).pixel_values.squeeze(0)
            return pixel_values, path
        except Exception:
            return torch.zeros((3, 224, 224)), "CORRUPT"

def process_thumbnails(thumb_dir, source_dir):
    """Process with aggressive memory management"""
    thumb_dir = Path(thumb_dir)
    source_dir = Path(source_dir)
    
    print("\n" + "=" * 60)
    print("🎯 PROCESSING IMAGES")
    print("=" * 60)
    
    # Build mapping
    thumb_to_orig = {}
    print("🔍 Mapping thumbnails...")
    for thumb_path in thumb_dir.rglob('*'):
        if thumb_path.suffix.lower() not in VALID_EXTENSIONS:
            continue
        
        rel_path = thumb_path.relative_to(thumb_dir)
        orig_stem = source_dir / rel_path.parent / rel_path.stem
        
        for ext in VALID_EXTENSIONS:
            candidate = orig_stem.with_suffix(ext)
            if candidate.exists():
                thumb_to_orig[str(thumb_path)] = str(candidate)
                break
    
    print(f"📸 Found {len(thumb_to_orig):,} pairs")
    
    # Load existing scores
    db_path = source_dir / DB_FILENAME
    score_data = {}
    
    if db_path.exists():
        try:
            with open(db_path, 'r') as f:
                score_data = json.load(f)
            print(f"💾 Loaded {len(score_data):,} existing scores")
        except:
            print("⚠️  Database corrupted")
    
    # Find new images
    new_thumbs = [t for t in thumb_to_orig.keys() if t not in score_data]
    
    if not new_thumbs:
        print("✅ All images already processed!")
        return score_data, thumb_to_orig
    
    print(f"🎯 Processing {len(new_thumbs):,} new images\n")
    
    # Load model
    model, processor, device = load_clip_model()
    all_prompts, section_lengths, offsets = get_prompt_config()
    
    # Pre-compute text embeddings
    print("📝 Pre-computing text embeddings...")
    with torch.no_grad():
        text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True).to(device)
        text_outputs = model.get_text_features(**text_inputs)
        text_embeds = text_outputs / text_outputs.norm(p=2, dim=-1, keepdim=True)
    
    clear_gpu_memory()
    
    # Optimal batch size for 4GB VRAM
    batch_size = 32  # Larger batches = less overhead
    
    print(f"⚙️  Batch size: {batch_size}")
    print(f"🚀 Starting processing...\n")
    
    dataset = ImageDataset(new_thumbs, processor)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=0,  # Single worker to save memory
        shuffle=False,
        pin_memory=False  # Disable for low VRAM
    )
    
    processed = 0
    start_time = time.time()
    
    try:
        with torch.no_grad():
            pbar = tqdm(loader, desc="Processing", unit="batch")
            
            for batch_idx, (images, paths) in enumerate(pbar):
                # Filter corrupt images
                valid_mask = [p != "CORRUPT" for p in paths]
                if not any(valid_mask):
                    continue
                
                images = images[valid_mask].to(device)
                current_paths = [p for p, m in zip(paths, valid_mask) if m]
                
                # Process images
                image_outputs = model.get_image_features(pixel_values=images)
                image_embeds = image_outputs / image_outputs.norm(p=2, dim=-1, keepdim=True)
                
                # Calculate scores
                sims = (image_embeds @ text_embeds.T).float().cpu().numpy()
                
                # Save scores
                for i, path in enumerate(current_paths):
                    row = sims[i]
                    scores = {}
                    for name, length in section_lengths.items():
                        start = offsets[name]
                        end = start + length
                        scores[name] = float(row[start:end].max())
                    
                    score_data[path] = scores
                    processed += 1
                
                # Update progress
                elapsed = time.time() - start_time
                imgs_per_sec = processed / elapsed if elapsed > 0 else 0
                pbar.set_postfix({
                    'imgs/s': f'{imgs_per_sec:.1f}',
                    'total': f'{processed:,}/{len(new_thumbs):,}'
                })
                
                # Clear memory every 10 batches
                if batch_idx % 10 == 0:
                    clear_gpu_memory()
                
                # Auto-save every 500 images
                if processed % 500 == 0:
                    with open(db_path, 'w') as f:
                        json.dump(score_data, f, indent=2)
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted! Saving...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    # Final save
    with open(db_path, 'w') as f:
        json.dump(score_data, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n✅ Processed {processed:,} images in {elapsed:.1f}s")
    print(f"   Speed: {processed/elapsed:.1f} imgs/sec")
    print(f"💾 Scores saved: {db_path}")
    
    clear_gpu_memory()
    
    return score_data, thumb_to_orig

def apply_thresholds(score_data, thumb_to_orig, thresholds):
    """Enhanced filtering with all categories"""
    keep_list = []
    discard_list = []
    
    for thumb_path, scores in score_data.items():
        orig_path = thumb_to_orig.get(thumb_path)
        if not orig_path or not Path(orig_path).exists():
            continue
        
        s = scores
        t = thresholds
        
        # Main content requirement
        is_good_content = (s['real'] > t['content']) or (s['cgi'] > t['content'])
        
        # Negative / trash filter
        is_clean = s['neg'] < t['negative']
        
        # Optional hard bans (e.g. loli, guro)
        banned = (
            s.get('loli', 0) > t.get('loli', 0.3) or
            s.get('guro', 0) > t.get('guro', 0.3) or
            s.get('censored', 0) > t.get('censored', 0.4)
        )
        
        # NSFW filters (only apply if enabled)
        too_nsfw = False
        if t.get('nsfw_strict', False):
            too_nsfw = any(s.get(cat, 0) > t.get(cat + '_thresh', 0.3) 
                          for cat in ['porn', 'hentai', 'bdsm', 'feet', 'furry', 'anal', 'group'])
        
        if is_good_content and is_clean and not banned and not too_nsfw:
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
        print(f"⚠️  Move failed: {e}")

def interactive_sorting(score_data, thumb_to_orig, source_dir):
    """Interactive threshold adjustment"""
    c_thresh = DEFAULT_CONTENT_THRESH
    n_thresh = DEFAULT_NEGATIVE_THRESH
    
    # === ENHANCED THRESHOLDS ===
    DEFAULT_THRESHOLDS = {
        'content': 0.25,
        'negative': 0.22,
        'loli': 0.30,
        'guro': 0.30,
        'censored': 0.40,
        'nsfw_strict': False,  # Set True to enable strict NSFW filtering
        'porn_thresh': 0.35,
        'hentai_thresh': 0.35,
        'bdsm_thresh': 0.35,
        'feet_thresh': 0.35,
        'furry_thresh': 0.35,
    }
    
    while True:
        print("\n" + "=" * 60)
        print("⚙️  SORTING CONFIGURATION")
        print("=" * 60)
        print(f"   Content Threshold: {c_thresh}")
        print(f"   Negative Threshold: {n_thresh}")
        print("=" * 60)
        
        keep_files, discard_files = apply_thresholds(
            score_data, thumb_to_orig, c_thresh, n_thresh
        )
        
        total = len(keep_files) + len(discard_files)
        keep_pct = (len(keep_files) / total * 100) if total > 0 else 0
        
        print(f"\n📊 PREVIEW:")
        print(f"   ✅ KEEP:    {len(keep_files):,} ({keep_pct:.1f}%)")
        print(f"   ❌ DISCARD: {len(discard_files):,} ({100-keep_pct:.1f}%)")
        
        print("\n🎯 OPTIONS:")
        print("  [1] Adjust Content Threshold")
        print("  [2] Adjust Negative Threshold")
        print("  [3] 🚀 EXECUTE MOVE")
        print("  [4] Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            try:
                new_val = float(input("New Content Threshold (0.0-1.0): "))
                if 0.0 <= new_val <= 1.0:
                    c_thresh = new_val
            except:
                print("⚠️  Invalid input")
        
        elif choice == '2':
            try:
                new_val = float(input("New Negative Threshold (0.0-1.0): "))
                if 0.0 <= new_val <= 1.0:
                    n_thresh = new_val
            except:
                print("⚠️  Invalid input")
        
        elif choice == '3':
            print(f"\n⚠️  WARNING: Moving {total:,} files")
            confirm = input("\nType 'YES' to confirm: ").strip()
            
            if confirm == 'YES':
                keep_dir = source_dir / "Keep"
                discard_dir = source_dir / "Discard"
                keep_dir.mkdir(exist_ok=True)
                discard_dir.mkdir(exist_ok=True)
                
                print("\n📦 Moving files...")
                for f in tqdm(keep_files, desc="Keep"):
                    safe_move(f, keep_dir)
                for f in tqdm(discard_files, desc="Discard"):
                    safe_move(f, discard_dir)
                
                print("\n✅ Complete!")
                break
        
        elif choice == '4':
            break

def main():
    print("\n" + "=" * 60)
    print("🚀 LOW VRAM IMAGE SORTER (GTX 1650 OPTIMIZED)")
    print("=" * 60)
    
    # Get directories
    source_dir = Path(input("Enter source directory (or press Enter for current): ").strip() or os.getcwd())
    thumb_dir = source_dir / "thumbnails"
    
    if not thumb_dir.exists():
        print(f"❌ Thumbnails not found: {thumb_dir}")
        print("Run thumbnail generator first!")
        return
    
    print(f"📁 Source: {source_dir}")
    print(f"📂 Thumbnails: {thumb_dir}")
    
    # Process
    score_data, thumb_to_orig = process_thumbnails(thumb_dir, source_dir)
    
    if not score_data:
        print("❌ No data generated")
        return
    
    # Sort
    interactive_sorting(score_data, thumb_to_orig, source_dir)
    
    print("\n" + "=" * 60)
    print("✅ ALL DONE!")
    print("=" * 60)

if __name__ == "__main__":
    main()