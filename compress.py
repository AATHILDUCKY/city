from PIL import Image
import io
import os
from datetime import datetime

def compress_image_to_webp(upload_file, quality: int = 80) -> str:
    """
    Compress an uploaded image to WebP format
    
    Args:
        upload_file: FastAPI UploadFile object
        quality: Quality of the output image (1-100)
    
    Returns:
        str: Path to the saved WebP image
    """
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    webp_filename = f"{timestamp}_{upload_file.filename.split('.')[0]}.webp"
    webp_path = f"uploads/{webp_filename}"
    
    try:
        # Read the uploaded image
        image = Image.open(upload_file.file)
        
        # Convert to RGB if it's RGBA (WebP doesn't support alpha channel well)
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        
        # Save as WebP
        image.save(webp_path, 'webp', quality=quality)
        
        return webp_path
    except Exception as e:
        raise RuntimeError(f"Image compression failed: {str(e)}")