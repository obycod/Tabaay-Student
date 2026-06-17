import os
from PIL import Image

def compress_images(directory, max_size=(600, 600)):
    total_original_size = 0
    total_compressed_size = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(root, file)
                try:
                    original_size = os.path.getsize(filepath)
                    total_original_size += original_size
                    
                    with Image.open(filepath) as img:
                        # Resize if larger than max_size
                        if img.width > max_size[0] or img.height > max_size[1]:
                            img.thumbnail(max_size, Image.Resampling.LANCZOS)
                            
                        # Save with optimization
                        img.save(filepath, optimize=True, quality=85)
                        
                    compressed_size = os.path.getsize(filepath)
                    total_compressed_size += compressed_size
                    
                    saved_mb = (original_size - compressed_size) / (1024 * 1024)
                    if saved_mb > 0.1:
                        print(f"Compressed {file}: saved {saved_mb:.2f} MB")
                        
                except Exception as e:
                    print(f"Failed to compress {file}: {e}")
                    
    print("\n--- Compression Summary ---")
    print(f"Original Total Size: {total_original_size / (1024 * 1024):.2f} MB")
    print(f"Compressed Total Size: {total_compressed_size / (1024 * 1024):.2f} MB")
    print(f"Total Space Saved: {(total_original_size - total_compressed_size) / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "assets")
    print(f"Starting compression in {assets_dir}...")
    compress_images(assets_dir)
