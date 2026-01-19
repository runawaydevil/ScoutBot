"""File security validation utilities"""

from pathlib import Path
from typing import Tuple
import mimetypes

from app.utils.logger import get_logger

logger = get_logger(__name__)


# Dangerous file extensions that should be blocked
DANGEROUS_EXTENSIONS = {
    # Executables
    '.exe', '.msi', '.bat', '.cmd', '.com', '.scr', '.pif',
    # Scripts
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.vbs', '.js', '.jse',
    # System files
    '.sys', '.dll', '.drv',
    # Shortcuts that can execute code
    '.lnk', '.url',
    # Installers
    '.deb', '.rpm', '.pkg', '.dmg', '.app',
    # Other dangerous
    '.jar', '.apk', '.ipa',
}

# Safe archive extensions (dangerous files are OK if inside these)
SAFE_ARCHIVE_EXTENSIONS = {
    '.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz',
    '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2',
}


def is_dangerous_file(filename: str) -> bool:
    """
    Check if a file is potentially dangerous
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if file is dangerous and should be blocked
    """
    file_path = Path(filename)
    
    # Get file extension (lowercase)
    ext = file_path.suffix.lower()
    
    # Check for double extensions (e.g., file.pdf.exe)
    if len(file_path.suffixes) > 1:
        # Check all extensions
        for suffix in file_path.suffixes:
            if suffix.lower() in DANGEROUS_EXTENSIONS:
                return True
    
    # Check single extension
    return ext in DANGEROUS_EXTENSIONS


def is_safe_archive(filename: str) -> bool:
    """
    Check if a file is a safe archive format
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if file is a safe archive
    """
    file_path = Path(filename)
    ext = file_path.suffix.lower()
    
    # Check for compound extensions like .tar.gz
    if len(file_path.suffixes) >= 2:
        compound_ext = ''.join(file_path.suffixes[-2:]).lower()
        if compound_ext in SAFE_ARCHIVE_EXTENSIONS:
            return True
    
    return ext in SAFE_ARCHIVE_EXTENSIONS


def validate_file_safety(filename: str) -> Tuple[bool, str]:
    """
    Validate if a file is safe to upload
    
    Args:
        filename: Name of the file to validate
        
    Returns:
        Tuple of (is_safe, reason)
        - is_safe: True if file is safe to upload
        - reason: Explanation if file is not safe
    """
    # Check if file is an archive (archives are always safe)
    if is_safe_archive(filename):
        logger.debug(f"File {filename} is a safe archive")
        return True, "Archive file"
    
    # Check if file is dangerous
    if is_dangerous_file(filename):
        file_path = Path(filename)
        ext = file_path.suffix.lower()
        logger.warning(f"Blocked dangerous file: {filename} (extension: {ext})")
        return False, (
            f"File type '{ext}' is not allowed for security reasons.\n"
            f"If you need to upload this file, please compress it in a ZIP archive first."
        )
    
    # File is safe
    logger.debug(f"File {filename} passed security validation")
    return True, "Safe file"


def get_safe_filename(filename: str) -> str:
    """
    Get a safe version of filename (remove dangerous characters)
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    # Remove path separators and other dangerous characters
    safe_name = filename.replace('/', '_').replace('\\', '_')
    safe_name = safe_name.replace('..', '_')
    
    # Remove leading/trailing spaces and dots
    safe_name = safe_name.strip('. ')
    
    return safe_name


def get_file_info(file_path: Path) -> dict:
    """
    Get information about a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dict with file information
    """
    if not file_path.exists():
        return {}
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "application/octet-stream"
    
    # Get extension
    ext = file_path.suffix.lower()
    
    # Check if dangerous
    is_dangerous = is_dangerous_file(file_path.name)
    is_archive = is_safe_archive(file_path.name)
    
    return {
        'filename': file_path.name,
        'size': file_size,
        'mime_type': mime_type,
        'extension': ext,
        'is_dangerous': is_dangerous,
        'is_archive': is_archive,
        'is_safe': is_archive or not is_dangerous,
    }
