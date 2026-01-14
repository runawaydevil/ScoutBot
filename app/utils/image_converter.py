"""Image format conversion utilities"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Literal

from PIL import Image
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Supported formats
SUPPORTED_FORMATS = {
    "png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "ico"
}

FORMAT_ALIASES = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
}


def check_imagemagick_available() -> bool:
    """Check if ImageMagick is available"""
    return shutil.which("convert") is not None or shutil.which("magick") is not None


def normalize_format(format_str: str) -> str:
    """Normalize format string to standard format"""
    format_lower = format_str.lower()
    return FORMAT_ALIASES.get(format_lower, format_lower)


def is_format_supported(format_str: str) -> bool:
    """Check if format is supported"""
    normalized = normalize_format(format_str)
    return normalized in SUPPORTED_FORMATS


def convert_image_format(
    input_path: Path,
    output_format: str,
    output_path: Optional[Path] = None,
    quality: int = 95
) -> Optional[Path]:
    """
    Convert image to specified format
    
    Args:
        input_path: Path to input image
        output_format: Target format (png, jpg, webp, etc.)
        output_path: Optional output path (auto-generated if None)
        quality: Quality for lossy formats (1-100, default: 95)
    
    Returns:
        Path to converted image or None if conversion failed
    """
    try:
        normalized_format = normalize_format(output_format)
        
        if not is_format_supported(normalized_format):
            logger.error(f"Unsupported format: {output_format}")
            return None
        
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return None
        
        # Generate output path if not provided
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}.{normalized_format}"
        
        # Try ImageMagick first (better quality and format support)
        if check_imagemagick_available():
            return _convert_with_imagemagick(input_path, output_path, normalized_format, quality)
        else:
            # Fallback to Pillow
            return _convert_with_pillow(input_path, output_path, normalized_format, quality)
            
    except Exception as e:
        logger.error(f"Failed to convert image: {e}", exc_info=True)
        return None


def _convert_with_imagemagick(
    input_path: Path,
    output_path: Path,
    format_str: str,
    quality: int
) -> Optional[Path]:
    """Convert image using ImageMagick"""
    try:
        magick_cmd = shutil.which("magick") or shutil.which("convert")
        if not magick_cmd:
            return None
        
        cmd = [magick_cmd, str(input_path)]
        
        # Add quality for lossy formats
        if format_str in ["jpg", "jpeg", "webp"]:
            cmd.extend(["-quality", str(quality)])
        
        # Output format and path
        cmd.append(f"{format_str}:{output_path}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        
        logger.error(f"ImageMagick conversion failed: {result.stderr}")
        return None
        
    except Exception as e:
        logger.error(f"ImageMagick conversion error: {e}", exc_info=True)
        return None


def _convert_with_pillow(
    input_path: Path,
    output_path: Path,
    format_str: str,
    quality: int
) -> Optional[Path]:
    """Convert image using Pillow (fallback)"""
    try:
        # Open image
        img = Image.open(input_path)
        
        # Convert RGBA to RGB for formats that don't support transparency
        if format_str in ["jpg", "jpeg"] and img.mode in ("RGBA", "LA", "P"):
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        
        # Save with appropriate options
        save_kwargs = {}
        if format_str in ["jpg", "jpeg", "webp"]:
            save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        
        if format_str == "webp":
            save_kwargs["method"] = 6  # Best quality, slower
        
        # Convert format name for Pillow
        pillow_format = format_str.upper() if format_str in ["JPEG", "TIFF"] else format_str.upper()
        if pillow_format == "JPG":
            pillow_format = "JPEG"
        
        img.save(output_path, format=pillow_format, **save_kwargs)
        
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        
        return None
        
    except Exception as e:
        logger.error(f"Pillow conversion error: {e}", exc_info=True)
        return None
