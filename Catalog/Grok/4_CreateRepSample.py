import os
import json
import time
import argparse
import sys
from pathlib import Path
from tqdm import tqdm
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import open_clip

# ========================= CONFIG =========================
DEFAULT_ORIGINALS = r"Q:\Collection Zprion"  # Full-res images (any folder structure)
DEFAULT_THUMBS    = r"Q:\Collection Zprion\thumbnails"            # Corresponding thumbnails
OUTPUT_JSON       = r"Q:\Collection Zprion\representative_gallery.json"
CACHE_FILE        = r"Q:\Collection Zprion\embeddings_cache.pt"

# 2. MODEL (ViT-B-32 for GTX 1650)
MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 64

# 3. SETTINGS (Tweak these to control how many pictures are saved)
SIMILARITY_THRESHOLD = 0.15   # Try 0.15 (strict) or 0.25 (loose)
ONE_OFF_MAX = 2               # Clusters with ≤5 images: keep ALL images
SMALL_MAX   = 6               # Clusters with 6-14 images: keep ALL images  
MIN_REPS    = 5              # For larger clusters: minimum to sample
MAX_REPS    = 50              # For larger clusters: maximum to sample
# =========================================================

# Check for sklearn
try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics.pairwise import cosine_distances
except ImportError:
    print("[ERROR] pip install scikit-learn")
    sys.exit(1)

class ThumbDataset(Dataset):
    def __init__(self, paths, preprocess_fn): 
        self.paths = paths
        self.preprocess = preprocess_fn
    def __len__(self): return len(self.paths)
    def __getitem__(self, i):
        try:
            image = Image.open(self.paths[i]).convert("RGB")
            return self.preprocess(image), str(self.paths[i])
        except:
            return torch.zeros(3, 224, 224), ""

def load_or_compute_embeddings(model, preprocess, thumb_paths_list):
    """
    Smart function that loads existing embeddings from disk
    and only computes the ones that are missing.
    """
    # 1. Load Cache if exists
    cache = {}
    if os.path.exists(CACHE_FILE):
        print(f"Loading cache from {CACHE_FILE}...")
        try:
            cache = torch.load(CACHE_FILE)
            print(f"  - Loaded {len(cache)} existing embeddings.")
        except Exception as e:
            print(f"  - Cache corrupted or unreadable, starting fresh. ({e})")
            cache = {}
    
    # 2. Identify missing
    missing_paths = [p for p in thumb_paths_list if p not in cache]
    
    if len(missing_paths) == 0:
        print("All embeddings found in cache! Skipping GPU compute.")
    else:
        print(f"Computing {len(missing_paths)} new embeddings on GPU...")
        
        ds = ThumbDataset(missing_paths, preprocess)
        dl = DataLoader(ds, batch_size=BATCH_SIZE, num_workers=0, pin_memory=True)
        
        for img, paths_batch in tqdm(dl, desc="Embedding", leave=False):
            img = img.to(DEVICE)
            with torch.no_grad():
                batch_embs = model.encode_image(img)
                batch_embs /= batch_embs.norm(dim=-1, keepdim=True)
                batch_embs = batch_embs.half().cpu().numpy()
            
            for i, p in enumerate(paths_batch):
                if p:
                    cache[p] = batch_embs[i]
        
        # 3. Save Cache
        print(f"Saving updated cache to {CACHE_FILE}...")
        torch.save(cache, CACHE_FILE)

    # 4. Construct Final Matrix for Clustering
    valid_paths = []
    embs_list = []
    
    for p in thumb_paths_list:
        if p in cache:
            valid_paths.append(p)
            embs_list.append(cache[p])
            
    if not embs_list:
        return [], np.array([])
        
    return valid_paths, np.vstack(embs_list)

def farthest_point_sampling(cluster_indices, all_embs, n):
    if len(cluster_indices) <= n: return cluster_indices
    sub_embs = all_embs[cluster_indices]
    selected_sub = [0]
    dists = np.full(len(sub_embs), np.inf)
    for _ in range(1, n):
        last = sub_embs[selected_sub[-1]]
        cosine_dist = cosine_distances(last[None, :], sub_embs)[0]
        dists = np.minimum(dists, cosine_dist)
        selected_sub.append(int(np.argmax(dists)))
    return [cluster_indices[i] for i in selected_sub]

def main():
    args = parse_args()
    start_time = time.time()
    
    # --- Load Model ---
    print(f"Loading {MODEL_NAME} on {DEVICE}...")
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED, device=DEVICE)
    model.eval()
    
    orig_root = Path(args.originals)
    thumb_root = Path(args.thumbs)
    
    # --- Scan Files ---
    print(f"Scanning '{orig_root}'...")
    original_files = sorted(list(orig_root.rglob("*.*")))
    entries = [] 
    
    for p in tqdm(original_files, desc="Pairing"):
        if not p.is_file(): continue

        # Exclude the thumbnails folder from being scanned as "originals"
        if thumb_root in p.parents: 
            continue

        try:
            rel = p.relative_to(orig_root)
        except: continue

        thumb_cand = thumb_root / rel
        found_thumb = None
        
        candidates = [thumb_cand] + [thumb_cand.with_suffix(x) for x in ['.jpg', '.jpeg', '.webp', '.png']]
        for cand in candidates:
            if cand.exists():
                found_thumb = cand
                break
        
        if found_thumb:
            entries.append({
                "original": str(p),
                "thumbnail": str(found_thumb),
                "filename": p.name
            })

    if not entries:
        print("No paired images found.")
        return

    # --- Get Embeddings (CACHED) ---
    print(f"Processing {len(entries)} images...")
    thumb_paths = [e['thumbnail'] for e in entries]
    
    # This function now handles loading/saving internally
    valid_paths, embs_matrix = load_or_compute_embeddings(model, preprocess, thumb_paths)
    
    # Map back to entries
    path_to_entry = {e['thumbnail']: e for e in entries}
    valid_entries = [path_to_entry[p] for p in valid_paths]
    
    # --- Clustering ---
    print(f"Clustering (Threshold: {SIMILARITY_THRESHOLD})...")
    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric='cosine',
        linkage='average',
        distance_threshold=SIMILARITY_THRESHOLD
    )
    cluster_labels = clustering.fit_predict(embs_matrix)
    
    # --- Sampling ---
    cluster_map = {}
    for idx, label in enumerate(cluster_labels):
        cluster_map.setdefault(label, []).append(idx)
        
    gallery_items = []
    stats = {"unique": 0, "collection": 0, "sampled": 0}

    print("Sampling...")
    for label, indices in tqdm(cluster_map.items()):
        n = len(indices)
        
        # FIXED: For flat directory, use cluster-based naming instead of parent folder
        first_file = Path(valid_entries[indices[0]]['filename'])
        group_name = f"Cluster_{label}_{first_file.stem}"

        if n <= ONE_OFF_MAX:
            sel = indices
            tag = "visual_unique"
            stats["unique"] += 1
        elif n <= SMALL_MAX:
            sel = indices
            tag = "visual_collection"
            stats["collection"] += 1
        else:
            target = min(MAX_REPS, max(MIN_REPS, n // 8))
            sel = farthest_point_sampling(indices, embs_matrix, target)
            tag = "visual_representative"
            stats["sampled"] += 1
            
        for idx in sel:
            item = valid_entries[idx]
            gallery_items.append({
                "group_id": int(label),
                "group_name": group_name,
                "path": item['original'],
                "thumb": item['thumbnail'],
                "filename": item['filename'],
                "type": tag
            })

    # --- Save JSON ---
    output_data = {
        "generated_at": time.ctime(),
        "stats": stats,
        "gallery": gallery_items
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    mins = (time.time() - start_time) / 60
    print("\n" + "="*50)
    print(f"DONE. Runtime: {mins:.1f}m")
    print(f"Total images in gallery: {len(gallery_items)}")
    print(f"Cache File: {CACHE_FILE}")
    print(f"JSON saved to: {args.output}")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--originals", type=str, default=DEFAULT_ORIGINALS)
    parser.add_argument("--thumbs", type=str, default=DEFAULT_THUMBS)
    parser.add_argument("--output", type=str, default=OUTPUT_JSON)
    return parser.parse_args()

if __name__ == "__main__":
    main()