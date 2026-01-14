"""Utility functions for creating ZIP archives"""

import zipfile
from pathlib import Path
from typing import List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_zip_file(source_path: Path, zip_path: Path, internal_filename: Optional[str] = None) -> bool:
    """
    Compacta um arquivo em ZIP.
    
    Args:
        source_path: Caminho do arquivo a ser compactado
        zip_path: Caminho do arquivo ZIP a ser criado
        internal_filename: Nome opcional do arquivo dentro do ZIP (se None, usa o nome original)
    
    Returns:
        True se bem-sucedido, False caso contrário
    """
    try:
        if not source_path.exists():
            logger.error(f"Source file does not exist: {source_path}")
            return False
        
        # Ensure zip directory exists
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use custom internal filename if provided, otherwise use original name
        filename_in_zip = internal_filename if internal_filename else source_path.name
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(source_path, filename_in_zip)
        
        if zip_path.exists() and zip_path.stat().st_size > 0:
            logger.debug(f"Successfully created ZIP file: {zip_path} ({zip_path.stat().st_size} bytes)")
            return True
        else:
            logger.error(f"ZIP file was not created or is empty: {zip_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to create ZIP file: {e}", exc_info=True)
        return False


def create_zip_from_files(
    file_paths: List[Path], 
    zip_path: Path, 
    internal_names: Optional[List[str]] = None
) -> bool:
    """
    Compacta múltiplos arquivos em um único ZIP.
    
    Args:
        file_paths: Lista de caminhos dos arquivos a serem compactados
        zip_path: Caminho do arquivo ZIP a ser criado
        internal_names: Lista opcional de nomes para os arquivos dentro do ZIP (se None, usa nomes originais)
    
    Returns:
        True se bem-sucedido, False caso contrário
    """
    try:
        if not file_paths:
            logger.error("No files provided for ZIP creation")
            return False
        
        # Filter out non-existent files
        existing_files = [f for f in file_paths if f.exists()]
        if not existing_files:
            logger.error("None of the provided files exist")
            return False
        
        # Validate internal_names if provided
        if internal_names and len(internal_names) != len(existing_files):
            logger.warning(
                f"internal_names length ({len(internal_names)}) doesn't match "
                f"existing_files length ({len(existing_files)}). Using original names."
            )
            internal_names = None
        
        # Ensure zip directory exists
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, file_path in enumerate(existing_files):
                # Use custom name if provided, otherwise use original name
                filename_in_zip = internal_names[idx] if internal_names else file_path.name
                zipf.write(file_path, filename_in_zip)
        
        if zip_path.exists() and zip_path.stat().st_size > 0:
            logger.debug(
                f"Successfully created ZIP file with {len(existing_files)} files: "
                f"{zip_path} ({zip_path.stat().st_size} bytes)"
            )
            return True
        else:
            logger.error(f"ZIP file was not created or is empty: {zip_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to create ZIP from files: {e}", exc_info=True)
        return False
