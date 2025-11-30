import os
import sys
import shutil
import json
import time
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image

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
    print("Loading AI Model...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Running on: {device.upper()}")

    model_name = "laion/CLIP-ViT-L-14-laion2B-s32B-b82K"
    try:
        model = CLIPModel.from_pretrained(model_name).to(device)
        processor = CLIPProcessor.from_pretrained(model_name)
    except:
        print("Falling back to OpenAI model...")
        model_name = "openai/clip-vit-large-patch14"
        model = CLIPModel.from_pretrained(model_name).to(device)
        processor = CLIPProcessor.from_pretrained(model_name)
    
    # Optimization: Use Half Precision on GPU (2x Speed)
    if device == "cuda":
        model = model.half()
        
    return model, processor, device

def get_prompt_config():
    """Defines categories and prompts, returns the flattened list and lengths."""
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

    # ===================================================================
    # INSTANT-ADD THEME / FETISH PACKS (just uncomment or add your own)
    # Each pack gives you a new clean score in image_scores.json
    # ===================================================================

    # High-demand fetish packs
    prompts_bdsm       = ["bdsm", "bondage", "shibari", "rope bondage", "leather", "latex", "gimp suit", "ballgag"]
    prompts_feet       = ["feet", "foot fetish", "barefoot", "soles", "toes", "foot worship"]
    prompts_bbW        = ["bbw", "chubby", "curvy", "thick", "plump", "ss(bbw)"]
    prompts_cosplay    = ["cosplay", "costume", "maid outfit", "bunny girl", "catgirl", "school uniform"]
    prompts_monster    = ["monster girl", "tentacles", "slime girl", "demon girl", "succubus", "lamia"]
    prompts_futa       = ["futanari", "dickgirl", "trap", "newhalf"]
    prompts_pegging    = ["pegging", "strapon", "female domination", "femdom"]
    prompts_gay        = ["gay", "yaoi", "male x male", "bara", "muscular male"]
    prompts_lesbian    = ["lesbian", "yuri", "girl on girl", "tribadism"]
    prompts_pov        = ["pov", "point of view", "first person view"]
    prompts_closeup    = ["closeup", "macro", "extreme closeup", "spread pussy", "spread anus"]
    prompts_cum        = ["cum", "bukkake", "cumshot", "facial", "creampie", "ahegao cum"]
    prompts_anal       = ["anal", "buttsex", "anal sex", "ass fucking"]
    prompts_group      = ["group sex", "orgy", "gangbang", "foursome", "threesome"]
    prompts_outdoor    = ["outdoor", "public sex", "exhibitionism", "forest", "beach sex"]

    # Artistic / aesthetic extras
    prompts_oil        = ["oil painting style", "greg rutkowski", "artgerm", "ross tran"]
    prompts_dark       = ["dark fantasy", "gothic", "horror", "macabre"]
    prompts_cyberpunk  = ["cyberpunk", "neon", "blade runner", "synthwave"]

    # ===================================================================
    # ADD NEW CATEGORIES HERE — just follow the pattern above
    # Example: prompts_milf = ["milf", "mature female", "older woman"]
    # ===================================================================

    # === FINAL SECTION ORDER (add new packs to this list to activate them!) ===
    prompt_sections = [
        ("real",      prompts_real),      ("cgi",       prompts_cgi),
        ("neg",       prompts_neg),       ("aesthetic", prompts_aesthetic),
        ("porn",      prompts_porn),      ("hentai",    prompts_hentai),
        ("art",       prompts_art),       ("censored",  prompts_censored),
        ("loli",      prompts_loli),      ("guro",      prompts_guro),
        ("furry",     prompts_furry),

        # NEW THEME PACKS — comment/uncomment as needed
        ("bdsm",      prompts_bdsm),      ("feet",      prompts_feet),
        ("bbw",       prompts_bbW),       ("cosplay",   prompts_cosplay),
        ("monster",   prompts_monster),   ("futa",      prompts_futa),
        ("pegging",   prompts_pegging),   ("gay",       prompts_gay),
        ("lesbian",   prompts_lesbian),   ("pov",       prompts_pov),
        ("closeup",   prompts_closeup),   ("cum",       prompts_cum),
        ("anal",      prompts_anal),      ("group",     prompts_group),
        ("outdoor",   prompts_outdoor),
        # ("oil",       prompts_oil),     # ← uncomment to enable
        # ("dark",      prompts_dark),
        # ("cyberpunk", prompts_cyberpunk),
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
    """Helper to load images for the GPU in batches"""
    def __init__(self, image_paths, processor):
        self.image_paths = image_paths
        self.processor = processor

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        path = self.image_paths[idx]
        try:
            image = Image.open(path).convert("RGB")
            # Return the processed tensor directly
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values.squeeze(0)
            return pixel_values, path
        except Exception:
            # Return a dummy tensor if image is corrupt
            return torch.zeros((3, 224, 224)), "CORRUPT"

def scan_thumbnails(source_root, custom_thumb_dir=None):
    """Scan thumbnails folder and map back to originals using Batch Processing"""
    source_root = Path(source_root).resolve()
    
    # --- PATH DISCOVERY ---
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
    
    if not check_setup(): return {}, {}
    
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    thumb_to_orig = {}
    
    print("🔍 Mapping thumbnails to originals...")
    for thumb_path in thumb_dir.rglob('*'):
        if thumb_path.suffix.lower() not in valid_exts: continue
        rel_path = thumb_path.relative_to(thumb_dir)
        orig_stem = source_root / rel_path.parent / rel_path.stem
        for ext in valid_exts:
            candidate = orig_stem.with_suffix(ext)
            if candidate.exists():
                thumb_to_orig[str(thumb_path)] = str(candidate)
                break
    
    print(f"📸 Found {len(thumb_to_orig):,} thumbnail↔original pairs")
    
    # --- LOAD DATABASE ---
    db_path = source_root / DB_FILENAME
    score_data = {}
    if db_path.exists():
        try:
            with open(db_path, 'r') as f: score_data = json.load(f)
            print(f"💾 Loaded {len(score_data)} existing scores")
        except:
            print("⚠️  Database corrupted, starting fresh")
    
    new_thumbs = [t for t in thumb_to_orig.keys() if t not in score_data]
    
    if not new_thumbs:
        print("✅ All thumbnails already scored!")
        return score_data, thumb_to_orig
    
    # --- BATCH PROCESSING START ---
    print(f"🎯 Scanning {len(new_thumbs)} new thumbnails with Batch Processing...")

    model, processor, device = load_model()
    all_prompts, section_lengths, offsets = get_prompt_config()
    
    print("Pre-computing text embeddings (running text AI once)...")
    with torch.no_grad():
        # Move text to GPU
        text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True).to(device)
        text_outputs = model.get_text_features(**text_inputs)
        # Normalize text embeddings
        text_embeds = text_outputs / text_outputs.norm(p=2, dim=-1, keepdim=True)

    # 2. SETUP DATASET & LOADER
    dataset = ImageListDataset(new_thumbs, processor)
    # Batch size: 32 is a safe sweet spot for most GPUs
    batch_size = 32 
    loader = DataLoader(dataset, batch_size=batch_size, num_workers=0, shuffle=False)

    print(f"🚀 Processing in batches of {batch_size}...")
    
    count = 0
    start_time = time.time()

    try:
        with torch.no_grad():
            for images, paths in loader:
                # Filter out corrupt images
                valid_mask = [p != "CORRUPT" for p in paths]
                if not any(valid_mask): continue
                
                images = images[valid_mask].to(device)
                current_paths = [p for p, m in zip(paths, valid_mask) if m]

                # Run Vision Model (Half precision if CUDA)
                if device == "cuda": images = images.half()
                image_outputs = model.get_image_features(pixel_values=images)
                
                # Normalize Image Embeddings
                image_embeds = image_outputs / image_outputs.norm(p=2, dim=-1, keepdim=True)

                # CALCULATE SCORES (Matrix Multiplication)
                sims = image_embeds @ text_embeds.T
                
                # Move to CPU to save results
                sims = sims.float().cpu().numpy()

                # Map results back to file paths
                for i, path in enumerate(current_paths):
                    row = sims[i]
                    scores = {}
                    for name, length in section_lengths.items():
                        start = offsets[name]
                        end = start + length
                        scores[name] = float(row[start:end].max())
                    
                    score_data[path] = scores
                    count += 1

                # Progress Update
                if count % 100 == 0:
                    elapsed = time.time() - start_time
                    s_per_img = elapsed / count
                    print(f"📊 {count}/{len(new_thumbs)} done ({s_per_img:.3f}s/img)")
                    
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted. Saving...")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force full re-scan of ALL thumbnails (ignores existing image_scores.json)"
    )

    args = parser.parse_args()

    
    source_dir = Path(args.folder).resolve()
    db_path = source_dir / DB_FILENAME
    
    # FORCE RE-SCAN: delete old DB if --force is used
    if args.force and db_path.exists():
        print("FORCE MODE: Deleting old image_scores.json → full re-scan")
        try:
            db_path.unlink()
        except:
            pass
    
    print("="*60)

    print("AI IMAGE SORTER (Thumbnail Mode)")
    if args.force:
        print("FORCE RE-SCAN ENABLED")
    print("="*60)
    
    
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