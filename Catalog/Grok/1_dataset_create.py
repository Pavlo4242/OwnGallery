"""
thumbnail_generator.py — Ultra-fast GPU thumbnail creation
Creates 512px thumbnails in parallel folder structure for CLIP processing
while preserving originals for web gallery viewing.

Usage:
    python thumbnail_generator.py /path/to/images
    python thumbnail_generator.py  # Uses current directory
"""

import os
import sys
from pathlib import Path
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from tqdm import tqdm
import argparse

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"🚀 Running on: {device}")

class ThumbnailDataset(Dataset):
    def __init__(self, file_paths, thumb_size=512):
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
            print(f"⚠️  Failed to load {path}: {e}")
            return None, path


def collate_fn(batch):
    """Custom collate function to handle PIL Images and paths"""
    return batch

def process_batch(batch, source_root, thumb_root, quality=85):
    """Save thumbnails maintaining folder structure"""
    imgs, paths = zip(*[(b[0], b[1]) for b in batch if b[0] is not None])
    if not imgs:
        return 0
    
    saved = 0
    for img, src_path in zip(imgs, paths):
        # Calculate relative path and create mirror structure
        rel_path = Path(src_path).relative_to(source_root)
        thumb_path = thumb_root / rel_path
        
        # Change extension to .jpg for consistency
        thumb_path = thumb_path.with_suffix('.jpg')
        
        # Create parent directories
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save thumbnail (skip if already exists and is newer than source)
        if thumb_path.exists():
            if thumb_path.stat().st_mtime > Path(src_path).stat().st_mtime:
                continue  # Thumbnail is up to date
        
        try:
            img.save(thumb_path, "JPEG", quality=quality, optimize=True, subsampling="4:2:0")
            saved += 1
        except Exception as e:
            print(f"⚠️  Save failed {thumb_path}: {e}")
    
    return saved


def create_thumbnails(source_dir, thumb_size=512, quality=85, batch_size=64):
    """Main thumbnail generation function"""
    source_root = Path(source_dir).resolve()
    thumb_root = source_root / "thumbnails"
    
    print("="*60)
    print("THUMBNAIL GENERATOR FOR CLIP")
    print("="*60)
    print(f"📁 Source: {source_root}")
    print(f"📦 Output: {thumb_root}")
    print(f"🎯 Size: {thumb_size}x{thumb_size}px")
    print(f"💾 Quality: {quality}")
    print(f"⚡ Batch: {batch_size}")
    print("="*60)
    
    # Gather all image files
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    image_paths = []
    
    for root, dirs, files in os.walk(source_root):
        # Skip the thumbnails folder itself
        if 'thumbnails' in Path(root).parts:
            continue
        
        for f in files:
            if Path(f).suffix.lower() in valid_exts:
                image_paths.append(Path(root) / f)
    
    if not image_paths:
        print("❌ No images found!")
        return
    
    print(f"📸 Found {len(image_paths):,} images\n")
    
    # Create dataset and dataloader
    dataset = ThumbnailDataset(image_paths, thumb_size)
    loader = DataLoader(
        dataset, 
        batch_size=batch_size, 
        num_workers=min(8, os.cpu_count() or 4),
        pin_memory=(device.type == 'cuda'),
        collate_fn=collate_fn  # Use custom collate to handle PIL Images
    )
    
    # Process batches with progress bar
    total_saved = 0
    for batch in tqdm(loader, desc="🎨 Creating thumbnails", unit="batch", colour="#00ff00"):
        saved = process_batch(batch, source_root, thumb_root, quality)
        total_saved += saved
    
    print("\n" + "="*60)
    print("✅ COMPLETE!")
    print("="*60)
    print(f"📊 Total images: {len(image_paths):,}")
    print(f"💾 New thumbnails: {total_saved:,}")
    print(f"⏭️  Skipped (up-to-date): {len(image_paths) - total_saved:,}")
    print(f"\n📂 Thumbnails ready at: {thumb_root}")
    print("\n💡 Next steps:")
    print(f"   python sorter.py {thumb_root}  # Run CLIP on thumbnails")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate CLIP-optimized thumbnails in parallel folder structure"
    )
    parser.add_argument(
        "folder", 
        nargs="?", 
        default=os.getcwd(),
        help="Source folder containing images (default: current directory)"
    )
    parser.add_argument(
        "--size", 
        type=int, 
        default=512,
        help="Thumbnail size in pixels (default: 512)"
    )
    parser.add_argument(
        "--quality", 
        type=int, 
        default=85,
        help="JPEG quality 1-100 (default: 85)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Batch size for GPU processing (default: 64)"
    )
    
    args = parser.parse_args()
    create_thumbnails(args.folder, args.size, args.quality, args.batch_size)


if __name__ == "__main__":
    main()
