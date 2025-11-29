# representative_sampler_FINAL_2025.py
# Zero duplicates. Zero clutter. Pure enlightenment.

import os, shutil, random, json, time
from pathlib import Path
from tqdm import tqdm
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics.pairwise import cosine_distances
import open_clip

# ========================= CONFIG =========================
ROOT = r"D:\Anime"
DEDUPED = Path(ROOT) / "_PERFECT_2025_THUMBS"          # your deduped full-res files
THUMBS = Path(ROOT) / "thumbnails"

MODEL_NAME = "ViT-L-14"
PRETRAINED = "laion2B-s32B-b82K"
DEVICE = "cuda"
BATCH_SIZE = 256

# Per-artist rules
ONE_OFF_MAX = 5                     # ≤5 images  → go to _ONE_OFFS
SMALL_MAX   = 14                    # 6–14      → keep ALL
MIN_REPS    = 15                    # 15–99     → at least this many
MAX_REPS    = 50                    # 100+      → cap here

OUTPUT       = Path(ROOT) / "_ICONIC_REPRESENTATIVES_2025"
ONE_OFFS     = Path(ROOT) / "_ONE_OFFS_PRECIOUS_RARE_IMAGES"
GLOBAL_CLEAN = Path(ROOT) / "_FINAL_MASTERPIECE_COLLECTION"

for p in [OUTPUT, ONE_OFFS, GLOBAL_CLEAN]:
    p.mkdir(exist_ok=True)
# =========================================================

print("Loading LAION 2B CLIP (cached)...")
model, _, preprocess = open_clip.create_model_and_transforms(
    MODEL_NAME, pretrained=PRETRAINED, device=DEVICE
)
model.eval()

# Global duplicate guard
already_copied = set()

class ThumbDataset(Dataset):
    def __len__(self): return len(self.paths)
    def __init__(self, paths): self.paths = paths
    def __getitem__(self, i):
        try:
            return preprocess(Image.open(self.paths[i]).convert("RGB")), str(self.paths[i])
        except:
            return torch.zeros(3, 224, 224), ""

@torch.no_grad()
def get_embeddings(thumb_paths):
    if not thumb_paths: return np.array([])
    ds = ThumbDataset(thumb_paths)
    dl = DataLoader(ds, batch_size=BATCH_SIZE, num_workers=8, pin_memory=True)
    embs = []
    for img, _ in tqdm(dl, desc="Embedding", leave=False):
        emb = model.encode_image(img.to(DEVICE))
        emb /= emb.norm(dim=-1, keepdim=True)
        embs.append(emb.half().cpu().numpy())
    return np.concatenate(embs)

def farthest_point_sampling(embs, n):
    if len(embs) <= n: return list(range(len(embs)))
    selected = [0]
    dists = np.full(len(embs), np.inf)
    for _ in range(1, n):
        last = embs[selected[-1]]
        cosine_dist = cosine_distances(last[None, :], embs)[0]
        dists = np.minimum(dists, cosine_dist)
        selected.append(int(np.argmax(dists)))
    return selected

# ======================= MAIN =======================
start = time.time()

by_artist = {}
for p in DEDUPED.rglob("*.*"):
    if not p.is_file(): continue
    artist = p.relative_to(DEDUPED).parts[0]
    by_artist.setdefault(artist, []).append(str(p))

print(f"Found {len(by_artist)} artists in deduped collection")

stats = {"one_offs": 0, "small": 0, "sampled": 0, "total_images": 0}

for artist, full_paths in tqdm(by_artist.items(), desc="Processing artists"):
    n = len(full_paths)
    
    # Find matching thumbnails
    thumb_paths = []
    for fp in full_paths:
        rel = Path(fp).relative_to(DEDUPED)
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            cand = THUMBS / rel.parent / f"{rel.stem}{ext}"
            if cand.exists():
                thumb_paths.append(str(cand))
                break
    
    # Decide fate
    if n <= ONE_OFF_MAX:
        dest_folder = ONE_OFFS / artist
        dest_folder.mkdir(parents=True, exist_ok=True)
        for src in full_paths:
            if src not in already_copied:
                shutil.copy2(src, dest_folder / Path(src).name)
                already_copied.add(src)
        stats["one_offs"] += n
        
    elif n <= SMALL_MAX:
        dest_folder = OUTPUT / artist
        dest_folder.mkdir(parents=True, exist_ok=True)
        for src in full_paths:
            if src not in already_copied:
                shutil.copy2(src, dest_folder / Path(src).name)
                already_copied.add(src)
        stats["small"] += n
        
    else:
        # Diversity sampling
        embs = get_embeddings(thumb_paths)
        target = min(MAX_REPS, max(MIN_REPS, n // 8))   # e.g. 200 imgs → ~25 reps
        indices = farthest_point_sampling(embs, target)
        chosen = [full_paths[i] for i in indices]
        
        dest_folder = OUTPUT / artist
        dest_folder.mkdir(parents=True, exist_ok=True)
        for src in chosen:
            if src not in already_copied:
                shutil.copy2(src, dest_folder / Path(src).name)
                already_copied.add(src)
        stats["sampled"] += len(chosen)

# Final flat masterpiece collection (no duplicates ever)
for src in tqdm(already_copied, desc="Building final flat set"):
    dst = GLOBAL_CLEAN / Path(src).name
    if dst.exists():
        stem = dst.stem
        ext = dst.suffix
        counter = 1
        while (GLOBAL_CLEAN / f"{stem}_{counter}{ext}").exists():
            counter += 1
        dst = GLOBAL_CLEAN / f"{stem}_{counter}{ext}"
    shutil.copy2(src, dst)

mins = (time.time() - start) / 60
print("\n" + "="*80)
print("REPRESENTATIVE SAMPLING COMPLETE — ZERO DUPLICATES, ZERO CLUTTER")
print("="*80)
print(f"Artists processed          : {len(by_artist)}")
print(f"One-offs (≤5 images)       : {stats['one_offs']:,} images  → _ONE_OFFS_PRECIOUS_RARE_IMAGES")
print(f"Small artists (6–14)       : {stats['small']:,} images  → kept in full")
print(f"Sampled artists (≥15)     : {stats['sampled']:,} iconic images")
print(f"Final masterpiece set      : {len(already_copied):,} images")
print(f"Runtime                    : {mins:.1f} minutes")
print(f"\nMain gallery               → {OUTPUT}")
print(f"Precious rare images       → {ONE_OFFS}")
print(f"Final flat collection      → {GLOBAL_CLEAN}")
print("\nYou now have three perfect folders:")
print("   • _ICONIC_REPRESENTATIVES_2025      ← browse & decide")
print("   • _ONE_OFFS_PRECIOUS_RARE_IMAGES    ← never lose these gems")
print("   • _FINAL_MASTERPIECE_COLLECTION     ← your eternal gallery")
print("\nYou have reached the end. There is nothing left to optimize.")
print("Go forth and enjoy your flawless collection.")