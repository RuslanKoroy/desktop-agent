import base64
import os
import threading
import time
from PIL import Image
import io

# Cache for base64 encoded images to avoid repeated encoding
_base64_cache = {}
_cache_lock = threading.Lock()
_cache_ttl = 0.5  # 500ms cache TTL

def convert_to_base64(path):
    """
    Convert an image file to base64 string with caching for performance
    """
    # Check if file exists
    if not os.path.exists(path):
        print(f"Warning: Image file not found: {path}")
        return ""
    
    # Get file modification time for cache validation
    file_mtime = os.path.getmtime(path)
    
    # Check if we have a valid cached version
    with _cache_lock:
        if path in _base64_cache:
            cache_entry = _base64_cache[path]
            cache_time, cache_mtime, cached_string = cache_entry
            
            # If file hasn't been modified and cache is fresh, use cached version
            if file_mtime == cache_mtime and time.time() - cache_time < _cache_ttl:
                return cached_string
    
    try:
        # Optimize image before encoding
        with Image.open(path) as img:
            # Use an in-memory buffer instead of temporary files
            buffer = io.BytesIO()
            
            # Determine format from path
            format = os.path.splitext(path)[1].lower().replace('.', '')
            if format not in ['jpeg', 'jpg', 'png']:
                format = 'jpeg'
            
            # Save with optimized settings
            if format in ['jpeg', 'jpg']:
                img.save(buffer, format='JPEG', quality=85, optimize=True)
            else:
                img.save(buffer, format='PNG', optimize=True)
            
            # Get binary data and encode
            image_data = buffer.getvalue()
            base64_encoded = base64.b64encode(image_data)
            base64_string = base64_encoded.decode('utf-8')
            
            # Update cache
            with _cache_lock:
                _base64_cache[path] = (time.time(), file_mtime, base64_string)
            
            return base64_string
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        
        # Fallback to original method if optimization fails
        try:
            with open(path, "rb") as image_file:
                image_data = image_file.read()
                base64_encoded = base64.b64encode(image_data)
                base64_string = base64_encoded.decode('utf-8')
                return base64_string
        except Exception as e2:
            print(f"Fallback encoding also failed: {e2}")
            return ""