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

# === ADD THESE IMPORTS ===
try:
    import readline
    def tab_complete_path(text, state):
        """Tab completion for file paths"""
        try:
            # Expand user home directory
            if text.startswith('~'):
                text = os.path.expanduser(text)
            
            # Find matches
            if os.path.isdir(text):
                dir_path = text
                prefix = ''
            else:
                dir_path = os.path.dirname(text) or '.'
                prefix = os.path.basename(text)
            
            # Get files in directory
            matches = []
            for f in os.listdir(dir_path):
                if f.startswith(prefix):
                    full_path = os.path.join(dir_path, f)
                    if os.path.isdir(full_path):
                        matches.append(full_path + '/')
                    else:
                        matches.append(full_path + ' ')
            
            # Return the match
            if state < len(matches):
                return matches[state]
            else:
                return None
                
        except Exception:
            return None

    # Set up tab completion
    readline.set_completer(tab_complete_path)
    readline.parse_and_bind("tab: complete")
    
except ImportError:
    print("⚠️  readline not available (Windows). Tab completion disabled.")
    # Fallback function for Windows
    def tab_complete_path(text, state):
        return None

# ========================= CONFIG =========================
MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32

# TEST MODE SETTINGS
SIMILARITY_THRESHOLD = 0.35   # Recommended for scene/model grouping

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
# =========================================================

try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics.pairwise import cosine_similarity, cosine_distances
except ImportError:
    print("[ERROR] pip install scikit-learn")
    sys.exit(1)

class ImageDataset(Dataset):
    def __init__(self, paths, preprocess_fn): 
        self.paths = paths
        self.preprocess = preprocess_fn
    
    def __len__(self): 
        return len(self.paths)
    
    def __getitem__(self, i):
        try:
            image = Image.open(self.paths[i]).convert("RGB")
            return self.preprocess(image), str(self.paths[i])
        except Exception as e:
            return torch.zeros(3, 224, 224), ""

def get_image_embeddings_single(model, preprocess, image_paths):
    """Get embeddings for specific images (for testing)"""
    embeddings = {}
    
    for img_path in image_paths:
        try:
            image = Image.open(img_path).convert("RGB")
            image_tensor = preprocess(image).unsqueeze(0).to(DEVICE)
            
            with torch.no_grad():
                emb = model.encode_image(image_tensor)
                emb = emb / emb.norm(dim=-1, keepdim=True)
                embeddings[str(img_path)] = emb.cpu().numpy()[0]
                
        except Exception as e:
            print(f"❌ Error processing {img_path}: {e}")
            continue
            
    return embeddings


def test_similarity_between_images(model, preprocess):
    """Interactive mode to test similarity between specific images"""
    print("\n🎯 IMAGE SIMILARITY TESTER")
    print("=" * 50)
    print("💡 TIP: Use TAB completion for file paths!")
    print("=" * 50)
    
    while True:
        print("\nEnter paths to 2 images to compare (or 'quit' to exit):")
        
        # === MODIFY THESE INPUT LINES ===
        try:
            # These will now have tab completion
            image1 = input("Image 1 path: ").strip().strip('"')
            if image1.lower() == 'quit':
                return False
                
            image2 = input("Image 2 path: ").strip().strip('"') 
            if image2.lower() == 'quit':
                return False
        except KeyboardInterrupt:
            print("\n\nExiting test mode...")
            return False
			
			
        # Validate paths
        paths = [Path(image1), Path(image2)]
        valid_paths = []
        
        for p in paths:
            if not p.exists():
                print(f"❌ File not found: {p}")
            elif p.suffix.lower() not in IMAGE_EXTENSIONS:
                print(f"❌ Not a supported image: {p}")
            else:
                valid_paths.append(p)
        
        if len(valid_paths) != 2:
            print("Please provide two valid image paths.")
            continue
        
        # Compute embeddings and similarity
        print(f"\nComputing similarity between:")
        print(f"  A: {valid_paths[0].name}")
        print(f"  B: {valid_paths[1].name}")
        
        embeddings = get_image_embeddings_single(model, preprocess, valid_paths)
        
        if len(embeddings) == 2:
            emb1 = embeddings[str(valid_paths[0])]
            emb2 = embeddings[str(valid_paths[1])]
            
            similarity = cosine_similarity([emb1], [emb2])[0][0]
            distance = 1 - similarity  # Cosine distance
            
            print(f"\n📊 SIMILARITY RESULTS:")
            print(f"  Cosine Similarity: {similarity:.4f}")
            print(f"  Cosine Distance:   {distance:.4f}")
            print(f"  Threshold:         {SIMILARITY_THRESHOLD}")
            
            # Interpretation
            if similarity > 0.6:
                print("  🔥 VERY SIMILAR - Same scene/model, same composition")
            elif similarity > 0.4:
                print("  ✅ SIMILAR - Same scene/model, different pose/angle") 
            elif similarity > 0.25:
                print("  ⚠️  WEAKLY SIMILAR - Same model or similar composition")
            elif similarity > 0.1:
                print("  🔍 SLIGHTLY SIMILAR - Some shared elements")
            else:
                print("  ❌ NOT SIMILAR - Different scenes/models")
            
            # Cluster prediction
            if distance <= SIMILARITY_THRESHOLD:
                print(f"  🎯 WOULD CLUSTER TOGETHER (distance ≤ {SIMILARITY_THRESHOLD})")
            else:
                print(f"  💔 WOULD BE SEPARATE (distance > {SIMILARITY_THRESHOLD})")
                
        else:
            print("❌ Could not compute embeddings for both images.")
        
        print("\n" + "-" * 50)

def get_target_directory():
    """Query user for directory to process"""
    while True:
        print("\n" + "="*50)
        print("CLIP-BASED IMAGE GALLERY GENERATOR")
        print("="*50)
        print("1. Test similarity between specific images")
        print("2. Process entire directory")
        print("3. Exit")
        
        choice = input("\nChoose option (1-3): ").strip()
        
        if choice == '1':
            return 'test_mode', []
        elif choice == '2':
            default_dir = str(Path.home() / "Pictures")
            if not os.path.exists(default_dir):
                default_dir = str(Path.cwd())
                
            print("💡 TIP: Use TAB completion for directory paths!")
            user_input = input(f"Enter directory path to process [default: {default_dir}]: ").strip()
            
            if not user_input:
                target_dir = Path(default_dir)
            else:
                target_dir = Path(user_input)
            
            if not target_dir.exists():
                print(f"❌ Directory does not exist: {target_dir}")
                continue
                
            image_files = list(target_dir.rglob("*.*"))
            image_files = [f for f in image_files if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file()]
            
            if not image_files:
                print(f"❌ No image files found in: {target_dir}")
                print(f"Supported extensions: {', '.join(IMAGE_EXTENSIONS)}")
                continue
                
            print(f"✅ Found {len(image_files)} image files in: {target_dir}")
            
            confirm = input(f"Process {len(image_files)} images? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                return target_dir, image_files
            else:
                print("Let's try another directory...")
                continue
        elif choice == '3':
            return 'exit', []
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")
            
            
def load_or_compute_embeddings(model, preprocess, image_paths, cache_dir):
    """Smart function that loads existing embeddings from disk"""
    cache_file = cache_dir / "embeddings_cache.pt"
    
    cache = {}
    if cache_file.exists():
        print(f"Loading cache from {cache_file}...")
        try:
            cache = torch.load(cache_file)
            print(f"  - Loaded {len(cache)} existing embeddings.")
        except Exception as e:
            print(f"  - Cache corrupted or unreadable, starting fresh. ({e})")
            cache = {}
    
    missing_paths = [str(p) for p in image_paths if str(p) not in cache]
    
    if len(missing_paths) == 0:
        print("All embeddings found in cache! Skipping GPU compute.")
    else:
        print(f"Computing {len(missing_paths)} new embeddings on GPU...")
        
        ds = ImageDataset(missing_paths, preprocess)
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
        
        print(f"Saving updated cache to {cache_file}...")
        torch.save(cache, cache_file)

    valid_paths = []
    embs_list = []
    
    for img_path in image_paths:
        path_str = str(img_path)
        if path_str in cache:
            valid_paths.append(img_path)
            embs_list.append(cache[path_str])
            
    if not embs_list:
        return [], np.array([])
        
    return valid_paths, np.vstack(embs_list)

def farthest_point_sampling(cluster_indices, all_embs, n):
    if len(cluster_indices) <= n: 
        return cluster_indices
        
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
    start_time = time.time()
    
    # --- Load Model First ---
    print(f"Loading {MODEL_NAME} on {DEVICE}...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL_NAME, 
        pretrained=PRETRAINED, 
        device=DEVICE
    )
    model.eval()
    
    # --- Get User Choice ---
    target_dir, image_files = get_target_directory()
    
    if target_dir == 'test_mode':
        test_similarity_between_images(model, preprocess)
        return
    elif target_dir == 'exit':
        return
    
    # --- Process Directory ---
    cache_dir = target_dir / ".clip_gallery_cache"
    cache_dir.mkdir(exist_ok=True)
    output_file = target_dir / "representative_gallery.json"
    
    # Show folder stats
    print(f"\n📁 FOLDER STATS:")
    print(f"  Directory: {target_dir}")
    print(f"  Total images: {len(image_files):,}")
    print(f"  Estimated size: {sum(f.stat().st_size for f in image_files) / (1024*1024):.1f} MB")
    
    # --- Get Embeddings ---
    print(f"\nProcessing {len(image_files)} images...")
    valid_paths, embs_matrix = load_or_compute_embeddings(model, preprocess, image_files, cache_dir)
    
    if len(valid_paths) == 0:
        print("❌ No valid embeddings could be computed.")
        return
    
    print(f"✅ Successfully processed {len(valid_paths)} images")
    
    # --- Clustering ---
    print(f"\nClustering (Threshold: {SIMILARITY_THRESHOLD})...")
    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric='cosine',
        linkage='average',
        distance_threshold=SIMILARITY_THRESHOLD
    )
    cluster_labels = clustering.fit_predict(embs_matrix)
    
    # --- Analyze Cluster Distribution ---
    from collections import Counter
    cluster_sizes = Counter(cluster_labels)
    
    print(f"\n📊 CLUSTER DISTRIBUTION:")
    size_groups = {
        "1 image": sum(1 for s in cluster_sizes.values() if s == 1),
        "2-3 images": sum(1 for s in cluster_sizes.values() if 2 <= s <= 3),
        "4-10 images": sum(1 for s in cluster_sizes.values() if 4 <= s <= 10),
        "11+ images": sum(1 for s in cluster_sizes.values() if s >= 11)
    }
    
    for group, count in size_groups.items():
        if count > 0:
            print(f"  {group}: {count} clusters")
    
    # Warn if threshold might be too strict
    if size_groups["1 image"] > len(cluster_sizes) * 0.6:
        print(f"\n⚠️  Warning: {size_groups['1 image']/len(cluster_sizes)*100:.1f}% of images are singletons!")
        print("   Consider increasing SIMILARITY_THRESHOLD to 0.45 for better grouping")
    
    # --- Sampling ---
    ONE_OFF_MAX = 1
    SMALL_MAX = 3  
    MIN_REPS = 3
    MAX_REPS = 12
    
    cluster_map = {}
    for idx, label in enumerate(cluster_labels):
        cluster_map.setdefault(label, []).append(idx)
    
    gallery_items = []
    stats = {
        "unique_clusters": 0,
        "small_clusters": 0,  
        "large_clusters": 0,
        "total_images": len(valid_paths),
        "selected_images": 0
    }

    print(f"\nSelecting representative images...")
    for label, indices in tqdm(cluster_map.items()):
        n = len(indices)
        first_file = valid_paths[indices[0]]
        group_name = f"Scene_{label}_{first_file.stem}"

        if n <= ONE_OFF_MAX:
            sel = indices
            tag = "unique_shot"
            stats["unique_clusters"] += 1
        elif n <= SMALL_MAX:
            sel = indices
            tag = "small_collection"
            stats["small_clusters"] += 1
        else:
            target = min(MAX_REPS, max(MIN_REPS, n // 8))
            sel = farthest_point_sampling(indices, embs_matrix, target)
            tag = "representative_sample"
            stats["large_clusters"] += 1
            
        for idx in sel:
            img_path = valid_paths[idx]
            gallery_items.append({
                "group_id": int(label),
                "group_name": group_name,
                "path": str(img_path),
                "filename": img_path.name,
                "type": tag,
                "cluster_size": n
            })
    
    stats["selected_images"] = len(gallery_items)
    
    # --- Save JSON ---
    output_data = {
        "generated_at": time.ctime(),
        "source_directory": str(target_dir),
        "clustering_threshold": SIMILARITY_THRESHOLD,
        "total_images_processed": len(valid_paths),
        "stats": stats,
        "gallery": gallery_items
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    # --- Final Summary ---
    mins = (time.time() - start_time) / 60
    reduction_pct = ((len(valid_paths) - len(gallery_items)) / len(valid_paths) * 100)
    
    print("\n" + "="*50)
    print("🎉 GALLERY GENERATION COMPLETE!")
    print("="*50)
    print(f"Source: {target_dir}")
    print(f"Runtime: {mins:.1f} minutes")
    print(f"Total images: {len(valid_paths):,}")
    print(f"Final gallery: {len(gallery_items):,}")
    print(f"Space reduction: {reduction_pct:.1f}%")
    print(f"Unique scenes: {len(cluster_map):,}")
    print(f"Output: {output_file}")
    
    
if __name__ == "__main__":
    main()