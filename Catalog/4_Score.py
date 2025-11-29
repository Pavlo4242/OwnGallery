"""
scanner.py — AI Image Scorer (NO FILE MOVING)
Only scans images and creates image_scores.json

Workflow:
1. Generate thumbnails: python thumbnail_generator.py /images
2. Scan with AI: python scanner.py /images/thumbnails
3. Copy thumbnails + image_scores.json to another machine
4. Adjust thresholds, preview results
5. Copy image_scores.json back to original machine
6. Execute move: python mover.py /images

Usage:
    python scanner.py /path/to/thumbnails
    python scanner.py /path/to/thumbnails --force  # Re-scan everything
"""

import os
import sys
import json
from pathlib import Path
import argparse

def check_setup():
    try:
        import torch
        from PIL import Image
        from transformers import CLIPProcessor, CLIPModel
        return True
    except ImportError:
        print("❌ Missing dependencies!")
        print("Install: pip install torch torchvision transformers pillow")
        return False

def load_model():
    from transformers import CLIPProcessor, CLIPModel
    print("🤖 Loading AI Model (LAION Uncensored)...")
    model_name = "laion/CLIP-ViT-L-14-laion2B-s32B-b82K"
    try:
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        print("✅ Model loaded: LAION CLIP")
        return model, processor
    except:
        print("⚠️  LAION model failed, falling back to OpenAI...")
        model_name = "openai/clip-vit-large-patch14"
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        print("✅ Model loaded: OpenAI CLIP")
        return model, processor

def get_image_scores(model, processor, image_path):
    import torch
    from PIL import Image
    try:
        image = Image.open(image_path).convert("RGB")
        
        prompts_real = ["photograph", "photorealistic", "raw photo", "dslr", "4k", "8k", 
                       "detailed skin texture", "masterpiece", "nude", "erotic photography", 
                       "nsfw", "uncensored"]
        prompts_cgi = ["3d render", "unreal engine 5", "octane render", "blender", 
                      "digital art", "3d anime", "highly detailed cg", "3d hentai", 
                      "nsfw anime", "explicit", "detailed anatomy"]
        prompts_neg = ["sketch", "pencil drawing", "doodle", "flat color", "cel shading", 
                      "vector art", "monochrome", "low quality", "text", "watermark", 
                      "censored", "mosaic", "blur", "bad anatomy"]

        all_prompts = prompts_real + prompts_cgi + prompts_neg
        inputs = processor(text=all_prompts, images=image, return_tensors="pt", 
                          padding=True, truncation=True)

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
        print(f"⚠️  Error scanning {image_path}: {e}")
        return None

def scan_images(target_dir, force_rescan=False, skip_folders=None):
    """Scan all images and save scores to JSON"""
    target_dir = Path(target_dir).resolve()
    
    if not check_setup():
        return
    
    # Default folders to skip
    if skip_folders is None:
        skip_folders = {'Keep', 'Discard', 'webP-OG'}
    
    # Find all images
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
    image_paths = []
    
    print(f"📂 Scanning directory: {target_dir}")
    for root, dirs, files in os.walk(target_dir):
        # Skip certain folders
        dirs[:] = [d for d in dirs if d not in skip_folders]
        
        for f in files:
            if Path(f).suffix.lower() in valid_exts:
                image_paths.append(Path(root) / f)
    
    if not image_paths:
        print("❌ No images found!")
        return
    
    print(f"📸 Found {len(image_paths):,} images")
    
    # Load existing database
    db_path = target_dir / "image_scores.json"
    score_data = {}
    
    if db_path.exists() and not force_rescan:
        try:
            with open(db_path, 'r') as f:
                score_data = json.load(f)
            print(f"💾 Loaded {len(score_data):,} existing scores")
        except:
            print("⚠️  Database corrupted, starting fresh")
    
    # Determine what needs scanning
    if force_rescan:
        to_scan = image_paths
        print("🔄 Force rescan enabled - scanning all images")
    else:
        to_scan = [p for p in image_paths if str(p) not in score_data]
        if not to_scan:
            print("✅ All images already scored!")
            print(f"💡 Use --force to re-scan everything")
            return
    
    print(f"🎯 Scanning {len(to_scan):,} images with AI...")
    print("="*60)
    
    # Load model and scan
    model, processor = load_model()
    
    count = 0
    errors = 0
    
    try:
        for i, img_path in enumerate(to_scan, 1):
            scores = get_image_scores(model, processor, img_path)
            
            if scores:
                score_data[str(img_path)] = scores
                count += 1
                
                # Progress update
                if count % 10 == 0:
                    pct = (i / len(to_scan)) * 100
                    print(f"📊 Progress: {count}/{len(to_scan)} ({pct:.1f}%)")
                
                # Auto-save every 50 images
                if count % 50 == 0:
                    with open(db_path, 'w') as f:
                        json.dump(score_data, f, indent=2)
                    print(f"💾 Auto-saved at {count} images")
            else:
                errors += 1
                
    except KeyboardInterrupt:
        print("\n⚠️  Scan interrupted by user!")
        print("💾 Saving progress...")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        print("💾 Saving what we have...")
    
    # Final save
    with open(db_path, 'w') as f:
        json.dump(score_data, f, indent=2)
    
    print("\n" + "="*60)
    print("✅ SCAN COMPLETE")
    print("="*60)
    print(f"📊 Total images found: {len(image_paths):,}")
    print(f"✅ Successfully scored: {count:,}")
    print(f"❌ Errors: {errors:,}")
    print(f"💾 Database saved: {db_path}")
    print("\n📋 Next steps:")
    print(f"   1. Review scores with: python previewer.py {target_dir}")
    print(f"   2. Or copy to another machine for review")
    print(f"   3. Move files with: python mover.py <original_images_dir>")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(
        description="AI Image Scanner - Creates score database without moving files"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=os.getcwd(),
        help="Folder to scan (default: current directory)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-scan all images (ignore existing scores)"
    )
    parser.add_argument(
        "--skip-folders",
        type=str,
        nargs="+",
        default=['Keep', 'Discard', 'webP-OG'],
        help="Folders to skip during scan (default: Keep Discard webP-OG)"
    )
    
    args = parser.parse_args()
    scan_images(args.folder, args.force, set(args.skip_folders))

if __name__ == "__main__":
    main()