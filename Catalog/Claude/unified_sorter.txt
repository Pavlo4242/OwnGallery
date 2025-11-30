"""
unified_sorter.py – All-in-One AI Image Sorter
Automatically handles thumbnail generation and AI processing

Features:
- Interactive directory selection
- Auto-detects existing thumbnails
- Generates thumbnails if needed
- Processes with optimized CLIP model
- Interactive threshold adjustment
- Moves original files based on AI scores

Usage:
    python unified_sorter.py
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
THUMBNAIL_SIZE = 512
THUMBNAIL_QUALITY = 85
VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
# ====================


def check_dependencies():
    """Verify all required packages are installed"""
    try:
        import torch
        from PIL import Image
        from transformers import CLIPProcessor, CLIPModel
        from torchvision import transforms
        from tqdm import tqdm
        return True
    except ImportError as e:
        print("❌ Missing dependencies!")
        print("\nPlease install required packages:")
        print("pip install torch torchvision transformers pillow tqdm")
        print(f"\nMissing: {e}")
        return False


def prompt_directory():
    """Interactive directory selection with validation"""
    print("=" * 60)
    print("🎯 AI IMAGE SORTER - DIRECTORY SETUP")
    print("=" * 60)
    
    while True:
        print("\nOptions:")
        print("  [1] Use current directory")
        print("  [2] Enter custom path")
        print("  [Q] Quit")
        
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == 'q':
            print("👋 Goodbye!")
            sys.exit(0)
        
        if choice == '1':
            source_dir = Path.cwd()
        elif choice == '2':
            path_input = input("Enter directory path: ").strip()
            source_dir = Path(path_input).expanduser().resolve()
        else:
            print("⚠️  Invalid choice")
            continue
        
        if not source_dir.exists():
            print(f"❌ Directory does not exist: {source_dir}")
            continue
        
        if not source_dir.is_dir():
            print(f"❌ Path is not a directory: {source_dir}")
            continue
        
        # Check if directory has images
        has_images = any(
            f.suffix.lower() in VALID_EXTENSIONS
            for f in source_dir.rglob('*')
            if f.is_file() and 'thumbnails' not in f.parts
        )
        
        if not has_images:
            print(f"⚠️  No images found in: {source_dir}")
            retry = input("Try another directory? (y/n): ").strip().lower()
            if retry != 'y':
                sys.exit(0)
            continue
        
        print(f"✅ Selected: {source_dir}")
        return source_dir


def find_thumbnails(source_dir):
    """Check for existing thumbnails in expected location"""
    default_thumb_dir = source_dir / "thumbnails"
    
    print("\n" + "=" * 60)
    print("🔍 THUMBNAIL DETECTION")
    print("=" * 60)
    
    # Check default location
    if default_thumb_dir.exists() and default_thumb_dir.is_dir():
        thumb_count = sum(
            1 for f in default_thumb_dir.rglob('*')
            if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS
        )
        
        if thumb_count > 0:
            print(f"✅ Found {thumb_count:,} thumbnails in default location")
            print(f"📂 {default_thumb_dir}")
            use_existing = input("\nUse these thumbnails? (y/n): ").strip().lower()
            if use_existing == 'y':
                return default_thumb_dir
    
    # Ask for custom location
    print("\n🔍 Thumbnails not found in default location")
    print("   Expected: {source_dir}/thumbnails/")
    
    while True:
        print("\nOptions:")
        print("  [1] Generate thumbnails now")
        print("  [2] Specify custom thumbnail location")
        print("  [Q] Quit")
        
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == 'q':
            sys.exit(0)
        
        if choice == '1':
            return None  # Signal to generate
        
        if choice == '2':
            custom_path = input("Enter thumbnail directory path: ").strip()
            custom_dir = Path(custom_path).expanduser().resolve()
            
            if not custom_dir.exists():
                print(f"❌ Directory does not exist: {custom_dir}")
                continue
            
            thumb_count = sum(
                1 for f in custom_dir.rglob('*')
                if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS
            )
            
            if thumb_count == 0:
                print(f"❌ No thumbnails found in: {custom_dir}")
                continue
            
            print(f"✅ Found {thumb_count:,} thumbnails")
            return custom_dir
        
        print("⚠️  Invalid choice")


def validate_thumbnail_structure(thumb_dir, source_dir):
    """Verify thumbnails mirror source structure"""
    print("\n🔍 Validating thumbnail structure...")
    
    # Get all source images
    source_images = [
        f for f in source_dir.rglob('*')
        if f.is_file() 
        and f.suffix.lower() in VALID_EXTENSIONS
        and 'thumbnails' not in f.parts
    ]
    
    # Check if thumbnails exist for source images
    matched = 0
    for src_file in source_images[:100]:  # Sample first 100
        rel_path = src_file.relative_to(source_dir)
        
        # Try to find corresponding thumbnail
        thumb_candidates = [
            thumb_dir / rel_path.with_suffix('.jpg'),
            thumb_dir / rel_path,
        ]
        
        if any(t.exists() for t in thumb_candidates):
            matched += 1
    
    match_rate = matched / min(100, len(source_images)) if source_images else 0
    
    print(f"   Matched: {matched}/{min(100, len(source_images))} samples")
    
    if match_rate < 0.5:
        print("⚠️  WARNING: Thumbnail structure may not match source")
        print("   Expected: thumbnails mirror source folder structure")
        proceed = input("\nContinue anyway? (y/n): ").strip().lower()
        return proceed == 'y'
    
    print("✅ Structure validated")
    return True


# ============= THUMBNAIL GENERATION =============

class ThumbnailDataset(Dataset):
    def __init__(self, file_paths, thumb_size=512):
        from torchvision import transforms
        self.paths = file_paths
        self.thumb_size = thumb_size
        self.transform = transforms.Compose([
            transforms.Resize(thumb_size, interpolation=transforms.InterpolationMode.LANCZOS),
            transforms.CenterCrop(thumb_size),
        ])
    
    def __len__(self):
        return len(self.paths)
    
    def __getitem__(self, idx):
        path = self.paths[idx]
        try:
            img = Image.open(path).convert("RGB")
            return self.transform(img), path
        except Exception as e:
            return None, path


def generate_thumbnails(source_dir, thumb_size=512, quality=85, batch_size=32):
    """Generate thumbnails with progress tracking - Windows compatible"""
    thumb_dir = source_dir / "thumbnails"
    
    print("\n" + "=" * 60)
    print("🎨 GENERATING THUMBNAILS")
    print("=" * 60)
    print(f"📁 Source: {source_dir}")
    print(f"📦 Output: {thumb_dir}")
    print(f"🎯 Size: {thumb_size}x{thumb_size}px")
    print(f"💾 Quality: {quality}")
    print("=" * 60)
    
    # Collect all image paths
    image_paths = [
        f for f in source_dir.rglob('*')
        if f.is_file()
        and f.suffix.lower() in VALID_EXTENSIONS
        and 'thumbnails' not in f.parts
    ]
    
    if not image_paths:
        print("❌ No images found!")
        return None
    
    print(f"📸 Found {len(image_paths):,} images\n")
    
    # Process WITHOUT multiprocessing (Windows-safe)
    from torchvision import transforms
    transform = transforms.Compose([
        transforms.Resize(thumb_size, interpolation=transforms.InterpolationMode.LANCZOS),
        transforms.CenterCrop(thumb_size),
    ])
    
    total_saved = 0
    
    # Process with progress bar
    for src_path in tqdm(image_paths, desc="Creating thumbnails", unit="img"):
        try:
            # Load and transform
            img = Image.open(src_path).convert("RGB")
            img = transform(img)
            
            # Calculate output path
            rel_path = Path(src_path).relative_to(source_dir)
            thumb_path = thumb_dir / rel_path.with_suffix('.jpg')
            
            # Create directories
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip if up-to-date
            if thumb_path.exists():
                if thumb_path.stat().st_mtime > Path(src_path).stat().st_mtime:
                    continue
            
            # Save thumbnail
            img.save(thumb_path, "JPEG", quality=quality, optimize=True)
            total_saved += 1
            
        except Exception as e:
            print(f"\n⚠️  Failed: {src_path.name}: {e}")
    
    print(f"\n✅ Generated {total_saved:,} new thumbnails")
    print(f"📂 Location: {thumb_dir}")
    
    return thumb_dir


# ============= AI PROCESSING =============

def load_clip_model():
    """Load CLIP model with optimizations"""
    from transformers import CLIPModel, CLIPProcessor
    
    print("\n" + "=" * 60)
    print("🤖 LOADING AI MODEL")
    print("=" * 60)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Device: {device.upper()}")
    
    if device == "cuda":
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"   GPU: {gpu_name}")
        print(f"   VRAM: {vram_gb:.1f}GB")
    
    model_name = "laion/CLIP-ViT-L-14-laion2B-s32B-b82K"
    
    print(f"📦 Loading {model_name}...")
    try:
        model = CLIPModel.from_pretrained(model_name).to(device)
        processor = CLIPProcessor.from_pretrained(model_name)
    except Exception as e:
        print("⚠️  Falling back to OpenAI model...")
        model_name = "openai/clip-vit-large-patch14"
        model = CLIPModel.from_pretrained(model_name).to(device)
        processor = CLIPProcessor.from_pretrained(model_name)
    
    model.eval()
    
    if device == "cuda":
        model = model.half()
    
    print("✅ Model loaded")
    
    return model, processor, device


def get_prompt_config():
    """Define all prompt categories"""
    prompts = {
        "real": ["photograph", "photorealistic", "raw photo", "dslr", "4k", "8k",
                "detailed skin texture", "masterpiece", "nude", "erotic photography"],
        "cgi": ["3d render", "unreal engine 5", "octane render", "blender",
               "digital art", "3d anime", "hyper-realistic", "realistic"],
        "neg": ["sketch", "pencil drawing", "doodle", "flat color", "low quality",
               "text", "watermark", "censored", "mosaic", "blur", "bad anatomy"],
        "aesthetic": ["masterpiece", "best quality", "extremely detailed", "absurdres"],
        "porn": ["porn", "explicit sex", "penetration", "xxx"],
        "hentai": ["hentai", "ahegao", "anime nsfw", "ecchi"],
        "art": ["digital art", "illustration", "painting", "artstation"],
        "censored": ["censored", "mosaic censor", "bars", "black bars"],
        "loli": ["loli", "shota", "childlike"],
        "guro": ["guro", "gore", "ryona"],
        "furry": ["furry", "anthro", "yiff"],
        "bdsm": ["bdsm", "bondage", "shibari", "rope bondage"],
        "feet": ["feet", "foot fetish", "barefoot", "soles"],
        "bbw": ["bbw", "chubby", "curvy", "thick"],
        "cosplay": ["cosplay", "costume", "maid outfit"],
        "monster": ["monster girl", "tentacles", "demon girl"],
        "futa": ["futanari", "dickgirl", "trap"],
        "gay": ["gay", "yaoi", "male x male"],
        "lesbian": ["lesbian", "yuri", "girl on girl"],
        "pov": ["pov", "point of view", "first person"],
        "anal": ["anal", "anal sex"],
        "group": ["group sex", "orgy", "gangbang"],
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
    """Dataset for batch processing"""
    def __init__(self, image_paths, processor):
        self.paths = image_paths
        self.processor = processor
    
    def __len__(self):
        return len(self.paths)
    
    def __getitem__(self, idx):
        path = self.paths[idx]
        try:
            image = Image.open(path).convert("RGB")
            pixel_values = self.processor(
                images=image,
                return_tensors="pt"
            ).pixel_values.squeeze(0)
            return pixel_values, path
        except Exception:
            return torch.zeros((3, 224, 224)), "CORRUPT"


def get_optimal_batch_size(device):
    """Determine batch size based on VRAM"""
    if device == "cpu":
        return 16
    
    try:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        if vram_gb >= 16:
            return 64
        elif vram_gb >= 8:
            return 48
        elif vram_gb >= 6:
            return 32
        else:
            return 16
    except:
        return 32


def process_images(thumb_dir, source_dir, force_rescan=False):
    """Process thumbnails with CLIP and generate scores"""
    thumb_dir = Path(thumb_dir)
    source_dir = Path(source_dir)
    
    print("\n" + "=" * 60)
    print("🎯 AI PROCESSING")
    print("=" * 60)
    
    # Build thumbnail → original mapping
    thumb_to_orig = {}
    
    print("🔍 Mapping thumbnails to originals...")
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
    
    print(f"📸 Mapped {len(thumb_to_orig):,} thumbnail↔original pairs")
    
    # Load existing scores
    db_path = source_dir / DB_FILENAME
    score_data = {}
    
    if not force_rescan and db_path.exists():
        try:
            with open(db_path, 'r') as f:
                score_data = json.load(f)
            print(f"💾 Loaded {len(score_data):,} existing scores")
        except:
            print("⚠️  Database corrupted, starting fresh")
    
    # Find new thumbnails
    new_thumbs = [t for t in thumb_to_orig.keys() if t not in score_data]
    
    if not new_thumbs:
        print("✅ All thumbnails already processed!")
        return score_data, thumb_to_orig
    
    print(f"🎯 Processing {len(new_thumbs):,} new images")
    
    # Load model
    model, processor, device = load_clip_model()
    all_prompts, section_lengths, offsets = get_prompt_config()
    
    # Pre-compute text embeddings
    print("\n🔍 Pre-computing text embeddings...")
    with torch.no_grad():
        text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True).to(device)
        
        if device == "cuda":
            with autocast():
                text_outputs = model.get_text_features(**text_inputs)
        else:
            text_outputs = model.get_text_features(**text_inputs)
        
        text_embeds = text_outputs / text_outputs.norm(p=2, dim=-1, keepdim=True)
    
    # Setup DataLoader
    dataset = ImageDataset(new_thumbs, processor)
    batch_size = get_optimal_batch_size(device)
    
    # Use num_workers=0 on Windows to avoid multiprocessing issues
    num_workers = 0 if sys.platform == 'win32' else 4
    
    print(f"⚙️  Batch size: {batch_size}")
    
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        shuffle=False,
        pin_memory=(device == "cuda" and num_workers > 0),
        persistent_workers=False  # Disable for Windows compatibility
    )
    
    print(f"\n🚀 Processing images...\n")
    
    processed = 0
    start_time = time.time()
    
    try:
        with torch.no_grad():
            pbar = tqdm(loader, desc="Processing", unit="batch")
            
            for images, paths in pbar:
                # Filter corrupt images
                valid_mask = [p != "CORRUPT" for p in paths]
                if not any(valid_mask):
                    continue
                
                images = images[valid_mask].to(device)
                current_paths = [p for p, m in zip(paths, valid_mask) if m]
                
                # Get image features
                if device == "cuda":
                    with autocast():
                        image_outputs = model.get_image_features(pixel_values=images)
                else:
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
                    'done': f'{processed:,}/{len(new_thumbs):,}'
                })
                
                # Auto-save every 500 images
                if processed % 500 == 0:
                    with open(db_path, 'w') as f:
                        json.dump(score_data, f, indent=2)
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted! Saving progress...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Final save
    with open(db_path, 'w') as f:
        json.dump(score_data, f, indent=2)
    
    elapsed = time.time() - start_time
    print(f"\n✅ Processed {processed:,} images in {elapsed:.1f}s")
    print(f"   Speed: {processed/elapsed:.1f} imgs/sec")
    print(f"💾 Scores saved: {db_path}")
    
    return score_data, thumb_to_orig


# ============= SORTING & MOVING =============

def apply_thresholds(score_data, thumb_to_orig, content_thresh, neg_thresh):
    """Filter images based on thresholds"""
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


def interactive_sorting(score_data, thumb_to_orig, source_dir):
    """Interactive threshold adjustment and file moving"""
    c_thresh = DEFAULT_CONTENT_THRESH
    n_thresh = DEFAULT_NEGATIVE_THRESH
    
    while True:
        print("\n" + "=" * 60)
        print("⚙️  SORTING CONFIGURATION")
        print("=" * 60)
        print(f"   Content Threshold (Real/CGI): {c_thresh}")
        print(f"   Negative Threshold (Trash):   {n_thresh}")
        print("=" * 60)
        
        keep_files, discard_files = apply_thresholds(
            score_data, thumb_to_orig, c_thresh, n_thresh
        )
        
        total = len(keep_files) + len(discard_files)
        keep_pct = (len(keep_files) / total * 100) if total > 0 else 0
        
        print(f"\n📊 PREVIEW:")
        print(f"   ✅ KEEP:    {len(keep_files):,} ({keep_pct:.1f}%)")
        print(f"   ❌ DISCARD: {len(discard_files):,} ({100-keep_pct:.1f}%)")
        print(f"   📦 TOTAL:   {total:,}")
        
        print("\n🎯 OPTIONS:")
        print("  [1] Adjust Content Threshold")
        print("  [2] Adjust Negative Threshold")
        print("  [3] 🚀 EXECUTE MOVE")
        print("  [4] Exit without moving")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            try:
                new_val = float(input("New Content Threshold (0.0-1.0): "))
                if 0.0 <= new_val <= 1.0:
                    c_thresh = new_val
                else:
                    print("⚠️  Value must be between 0.0 and 1.0")
            except:
                print("⚠️  Invalid input")
        
        elif choice == '2':
            try:
                new_val = float(input("New Negative Threshold (0.0-1.0): "))
                if 0.0 <= new_val <= 1.0:
                    n_thresh = new_val
                else:
                    print("⚠️  Value must be between 0.0 and 1.0")
            except:
                print("⚠️  Invalid input")
        
        elif choice == '3':
            print(f"\n⚠️  WARNING: About to move {total:,} files")
            print(f"   Keep:    {len(keep_files):,} → {source_dir}/Keep/")
            print(f"   Discard: {len(discard_files):,} → {source_dir}/Discard/")
            
            confirm = input("\nType 'YES' to confirm: ").strip()
            
            if confirm == 'YES':
                keep_dir = source_dir / "Keep"
                discard_dir = source_dir / "Discard"
                keep_dir.mkdir(exist_ok=True)
                discard_dir.mkdir(exist_ok=True)
                
                print("\n📦 Moving files...")
                for f in tqdm(keep_files, desc="Keep", unit="file"):
                    safe_move(f, keep_dir)
                for f in tqdm(discard_files, desc="Discard", unit="file"):
                    safe_move(f, discard_dir)
                
                print("\n✅ Complete!")
                print("💡 Thumbnails preserved - you can re-run to re-sort")
                break
            else:
                print("❌ Cancelled")
        
        elif choice == '4':
            print("👋 Exiting without changes")
            break


# ============= MAIN FLOW =============

def main():
    print("\n" + "=" * 60)
    print("🤖 UNIFIED AI IMAGE SORTER")
    print("=" * 60)
    print("Features: Auto-setup | Thumbnail generation | AI processing | Smart sorting")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Step 1: Select directory
    source_dir = prompt_directory()
    
    # Step 2: Find or generate thumbnails
    thumb_dir = find_thumbnails(source_dir)
    
    if thumb_dir is None:
        # Generate thumbnails
        confirm = input("\nGenerate thumbnails now? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Cannot proceed without thumbnails")
            sys.exit(1)
        
        thumb_dir = generate_thumbnails(source_dir, THUMBNAIL_SIZE, THUMBNAIL_QUALITY)
        if thumb_dir is None:
            print("❌ Thumbnail generation failed")
            sys.exit(1)
    
    # Step 3: Validate structure
    if not validate_thumbnail_structure(thumb_dir, source_dir):
        print("❌ Structure validation failed")
        sys.exit(1)
    
    # Step 4: Process with AI
    force_rescan = False
    if (source_dir / DB_FILENAME).exists():
        print("\n💾 Existing scores database found")
        rescan = input("Force re-scan all images? (y/n): ").strip().lower()
        force_rescan = (rescan == 'y')
    
    score_data, thumb_to_orig = process_images(thumb_dir, source_dir, force_rescan)
    
    if not score_data:
        print("❌ No scores generated")
        sys.exit(1)
    
    # Step 5: Interactive sorting
    print("\n" + "=" * 60)
    print("🎯 SORTING PHASE")
    print("=" * 60)
    print("Adjust thresholds to preview which files will be kept/discarded")
    print("Original files will be moved when you execute")
    
    interactive_sorting(score_data, thumb_to_orig, source_dir)
    
    print("\n" + "=" * 60)
    print("✅ ALL DONE!")
    print("=" * 60)


if __name__ == "__main__":
    main()