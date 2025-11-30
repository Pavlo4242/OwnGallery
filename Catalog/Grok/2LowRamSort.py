"""
LOW VRAM SORTER 2025 – FULLY SEPARATE THUMBS / ORIGINALS SUPPORT
Works on GTX 1650 / 4GB VRAM | All fetishes | Redpioneer killer | Yuri/Yaoi/etc.
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

# === CONFIG ===
DB_FILENAME = "image_scores.json"
VALID_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tiff'}

def clear_gpu_memory():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()

def load_clip_model():
    from transformers import CLIPModel, CLIPProcessor
    print("\nLOADING LOW-VRAM CLIP (GTX 1650 READY)")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_name = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
    
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.to(device).eval()
    
    print(f"Model loaded on {device.upper()}")
    return model, processor, device

def get_prompt_config():
    prompts = {
        "real": ["photograph", "photorealistic", "raw photo", "dslr", "detailed skin", "nude photo", "uncensored"],
        "cgi": ["3d render", "blender", "octane", "digital art", "3d anime", "hyper-realistic"],
        "neg": ["sketch", "low quality", "watermark", "text", "blur", "bad anatomy", "censored", "mosaic"],
        "aesthetic": ["masterpiece", "best quality", "extremely detailed"],
        "porn": ["porn", "explicit sex", "hardcore", "xxx", "penetration"],
        "hentai": ["hentai", "anime nsfw", "ecchi", "oppai", "ahegao"],
        "censored": ["censored", "mosaic censor", "bars", "black bars"],
        "loli": ["loli", "shota", "flat chest", "childlike", "toddlercon"],
        "guro": ["guro", "gore", "ryona", "dismemberment", "bloodbath"],
        "furry": ["furry", "anthro", "yiff", "fursona"],
        "redpioneer": ["redpioneer", "thick outline", "plastic shine", "flat cel shading", "drooling cum"],
        "yuri": ["yuri", "lesbian", "girl on girl", "tribadism", "scissoring"],
        "yaoi": ["yaoi", "gay", "boy x boy", "bara", "male x male"],
        "cuck": ["cuckold", "netorare", "ntr", "cheating wife", "hotwife"],
        "futa": ["futanari", "dickgirl", "trap", "newhalf"],
        "feet": ["feet", "foot fetish", "soles", "toes", "foot worship"],
        "bdsm": ["bdsm", "bondage", "shibari", "latex", "ballgag"],
        "anal": ["anal", "buttsex", "ass fucking"],
        "cum": ["cum", "bukkake", "cumshot", "facial", "creampie"],
        "ahegao": ["ahegao", "mind break", "rolling eyes", "tongue out"],
        "group": ["group sex", "orgy", "gangbang"],
        "bbw": ["bbw", "chubby", "thick"],
        "cosplay": ["cosplay", "maid", "bunny girl", "catgirl"],
        "tentacle": ["tentacles", "tentacle sex", "monster girl"],
    }

    all_prompts = []
    offsets = {}
    lengths = {}
    idx = 0
    for name, plist in prompts.items():
        offsets[name] = idx
        lengths[name] = len(plist)
        all_prompts.extend(plist)
        idx += len(plist)
    return all_prompts, lengths, offsets

class ImageDataset(Dataset):
    def __init__(self, paths, processor):
        self.paths = paths
        self.processor = processor
    def __len__(self): return len(self.paths)
    def __getitem__(self, idx):
        try:
            img = Image.open(self.paths[idx]).convert("RGB").resize((224, 224), Image.LANCZOS)
            pv = self.processor(images=img, return_tensors="pt").pixel_values.squeeze(0)
            return pv, str(self.paths[idx])
        except:
            return torch.zeros((3, 224, 224)), "ERROR"

def process_thumbnails(thumb_dir, orig_dir):
    thumb_dir = Path(thumb_dir).resolve()
    orig_dir = Path(orig_dir).resolve()
    db_path = orig_dir / DB_FILENAME

    print(f"\nThumbnails folder: {thumb_dir}")
    print(f"Originals folder: {orig_dir}")

    # Build mapping: thumbnail → original
    print("Mapping thumbnails → originals...")
    thumb_to_orig = {}
    for thumb_path in thumb_dir.rglob("*.*"):
        if thumb_path.suffix.lower() not in VALID_EXTS: continue
        rel = thumb_path.relative_to(thumb_dir)
        for ext in VALID_EXTS:
            candidate = (orig_dir / rel.parent / rel.stem).with_suffix(ext)
            if candidate.exists():
                thumb_to_orig[str(thumb_path)] = str(candidate)
                break

    print(f"Found {len(thumb_to_orig):,} valid pairs")

    # Load existing DB
    score_data = {}
    if db_path.exists():
        try:
            score_data = json.load(open(db_path))
            print(f"Loaded {len(score_data):,} existing scores")
        except:
            print("DB corrupted, starting fresh")

    new_thumbs = [t for t in thumb_to_orig if t not in score_data]
    if not new_thumbs:
        print("All images already scored!")
        return score_data, thumb_to_orig

    print(f"Scoring {len(new_thumbs):,} new images")

    model, processor, device = load_clip_model()
    all_prompts, lengths, offsets = get_prompt_config()

    # Pre-compute text embeddings
    print("Pre-computing text features...")
    with torch.no_grad():
        text_inputs = processor(text=all_prompts, return_tensors="pt", padding=True).to(device)
        text_feats = model.get_text_features(**text_inputs)
        text_embeds = text_feats / text_feats.norm(p=2, dim=-1, keepdim=True)
    clear_gpu_memory()

    # Process
    loader = DataLoader(ImageDataset(new_thumbs, processor), batch_size=32, num_workers=0)
    processed = 0
    start = time.time()

    try:
        with torch.no_grad():
            for imgs, paths in tqdm(loader, desc="Scoring", unit="batch"):
                valid = [p != "ERROR" for p in paths]
                if not any(valid): continue
                imgs = imgs[valid].to(device)
                paths = [p for p, v in zip(paths, valid) if v]

                img_feats = model.get_image_features(pixel_values=imgs)
                img_embeds = img_feats / img_feats.norm(p=2, dim=-1, keepdim=True)
                sims = (img_embeds @ text_embeds.T).cpu().numpy()

                for i, path in enumerate(paths):
                    row = sims[i]
                    scores = {}
                    for name in lengths:
                        s = offsets[name]
                        e = s + lengths[name]
                        scores[name] = float(row[s:e].max())
                    score_data[path] = scores
                    processed += 1

                if processed % 500 == 0:
                    json.dump(score_data, open(db_path, 'w'), indent=2)

    except KeyboardInterrupt:
        print("\nSaving progress...")
    finally:
        json.dump(score_data, open(db_path, 'w'), indent=2)
        print(f"\nFinished! {processed} images @ {processed/(time.time()-start):.1f} img/s")
        clear_gpu_memory()

    return score_data, thumb_to_orig

# === THRESHOLD & MOVE (unchanged but simplified) ===
def apply_thresholds(score_data, thumb_to_orig, c_thresh=0.25, n_thresh=0.22):
    keep, discard = [], []
    for thumb, scores in score_data.items():
        orig = thumb_to_orig.get(thumb)
        if not orig or not Path(orig).exists(): continue
        good = (scores.get('real',0) > c_thresh) or (scores.get('cgi',0) > c_thresh)
        clean = scores.get('neg',0) < n_thresh
        banned = any(scores.get(b,0) > 0.30 for b in ['loli','guro','redpioneer'])
        if good and clean and not banned:
            keep.append(orig)
        else:
            discard.append(orig)
    return keep, discard

def safe_move(src, dest_dir):
    src, dest_dir = Path(src), Path(dest_dir)
    dest = dest_dir / src.name
    i = 1
    while dest.exists():
        dest = dest_dir / f"{src.stem}_{i}{src.suffix}"
        i += 1
    shutil.move(str(src), str(dest))

def interactive_sorting(score_data, thumb_to_orig, orig_dir):
    c, n = 0.25, 0.22
    while True:
        keep, discard = apply_thresholds(score_data, thumb_to_orig, c, n)
        total = len(keep) + len(discard)
        print(f"\nContent ≥ {c} | Neg < {n} → KEEP: {len(keep):,} ({len(keep)/total*100:5.1f}%)")
        print("[1] Content [2] Negative [3] EXECUTE [4] Exit")
        ch = input("→ ").strip()
        if ch == '1': c = float(input(f"New content thresh (current {c}): ") or c)
        if ch == '2': n = float(input(f"New negative thresh (current {n}): ") or n)
        if ch == '3':
            if input("Type YES to move: ") == "YES":
                (orig_dir/"Keep").mkdir(exist_ok=True)
                (orig_dir/"Discard").mkdir(exist_ok=True)
                for f in tqdm(keep, desc="Keep"): safe_move(f, orig_dir/"Keep")
                for f in tqdm(discard, desc="Discard"): safe_move(f, orig_dir/"Discard")
                print("DONE")
                break
        if ch == '4': break

def main():
    print("\nLOW-VRAM HENTAI SORTER 2025 – SEPARATE FOLDERS EDITION")
    print("="*70)
    
    orig = input("Original images folder (or Enter for current): ").strip() or "."
    thumb = input("Thumbnails folder: ").strip()
    
    orig_dir = Path(orig).resolve()
    thumb_dir = Path(thumb).resolve()
    
    if not orig_dir.exists() or not thumb_dir.exists():
        print("One or both folders not found!")
        return
    
    scores, mapping = process_thumbnails(thumb_dir, orig_dir)
    interactive_sorting(scores, mapping, orig_dir)

if __name__ == "__main__":
    main()