"""Pentaract Storage Service - Integração com sistema de storage baseado em Telegram"""

import aiohttp
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Custom Exceptions
class PentaractUnavailableError(Exception):
    """Raised when Pentaract service is unavailable"""
    pass


class PentaractAuthenticationError(Exception):
    """Raised when authentication with Pentaract fails"""
    pass


class PentaractUploadError(Exception):
    """Raised when file upload to Pentaract fails"""
    pass


class PentaractStorageService:
    """
    Serviço para integração com Pentaract - Sistema de storage usando Telegram
    
    Pentaract divide arquivos em chunks e armazena no Telegram, permitindo
    armazenamento ilimitado sem usar disco local.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'pentaract_api_url', 'http://localhost:8547/api')
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.storage_id: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_available: bool = False
        self._last_health_check: Optional[datetime] = None
        self._health_check_interval: int = 300  # 5 minutes
    
    async def initialize(self) -> bool:
        """
        Inicializa sessão HTTP e autentica
        
        Returns:
            bool: True se inicialização bem-sucedida
        """
        try:
            if not self._session:
                timeout = aiohttp.ClientTimeout(total=settings.pentaract_timeout)
                self._session = aiohttp.ClientSession(timeout=timeout)
            
            # Autentica no Pentaract
            auth_success = await self._authenticate()
            if not auth_success:
                logger.error("Pentaract authentication failed during initialization")
                self._is_available = False
                return False
            
            # Obtém ou cria storage padrão
            await self._ensure_storage()
            
            self._is_available = True
            self._last_health_check = datetime.utcnow()
            logger.info("Pentaract Storage Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Pentaract Storage Service: {e}")
            self._is_available = False
            return False
    
    async def close(self):
        """Fecha sessão HTTP"""
        if self._session:
            await self._session.close()
            self._session = None
        self._is_available = False
    
    async def is_available(self) -> bool:
        """
        Verifica se o serviço Pentaract está disponível
        
        Executa health check periódico se necessário
        
        Returns:
            bool: True se serviço está disponível
        """
        # Check if we need to perform health check
        if self._last_health_check is None:
            return await self._health_check()
        
        time_since_last_check = (datetime.utcnow() - self._last_health_check).total_seconds()
        if time_since_last_check > self._health_check_interval:
            return await self._health_check()
        
        return self._is_available
    
    async def _health_check(self) -> bool:
        """
        Executa health check do serviço Pentaract
        
        Returns:
            bool: True se serviço está saudável
        """
        try:
            if not self._session:
                self._is_available = False
                return False
            
            # Try to list storages as a health check
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            async with self._session.get(
                f"{self.base_url}/storages",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    self._is_available = True
                    self._last_health_check = datetime.utcnow()
                    return True
                elif response.status == 401:
                    # Token expired, try to refresh
                    logger.info("Token expired during health check, attempting refresh")
                    if await self._refresh_token():
                        self._is_available = True
                        self._last_health_check = datetime.utcnow()
                        return True
                
                self._is_available = False
                return False
                
        except asyncio.TimeoutError:
            logger.warning("Pentaract health check timed out")
            self._is_available = False
            return False
        except Exception as e:
            logger.error(f"Pentaract health check failed: {e}")
            self._is_available = False
            return False
    
    async def _refresh_token(self) -> bool:
        """
        Renova o token de acesso usando refresh token
        
        Returns:
            bool: True se renovação bem-sucedida
        """
        try:
            if not self.refresh_token:
                logger.warning("No refresh token available, re-authenticating")
                return await self._authenticate()
            
            logger.info("Refreshing Pentaract access token")
            
            async with self._session.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get('access_token')
                    # Some APIs also return a new refresh token
                    if 'refresh_token' in data:
                        self.refresh_token = data.get('refresh_token')
                    logger.info("✅ Token refreshed successfully")
                    return True
                else:
                    logger.warning(f"Token refresh failed with status {response.status}, re-authenticating")
                    return await self._authenticate()
                    
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}, attempting re-authentication")
            return await self._authenticate()
    
    async def _authenticate(self) -> bool:
        """
        Autentica no Pentaract usando credenciais
        
        Returns:
            bool: True se autenticação bem-sucedida
            
        Raises:
            PentaractAuthenticationError: Se autenticação falhar
        """
        try:
            email = getattr(settings, 'pentaract_email', None)
            password = getattr(settings, 'pentaract_password', None)
            
            if not email or not password:
                logger.error("Pentaract credentials not configured")
                raise PentaractAuthenticationError("Pentaract credentials not configured")
            
            async with self._session.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get('access_token')
                    self.refresh_token = data.get('refresh_token')
                    logger.info("✅ Authenticated with Pentaract")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Pentaract authentication failed: {response.status} - {error_text}")
                    raise PentaractAuthenticationError(f"Authentication failed: {response.status}")
                    
        except PentaractAuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Failed to authenticate with Pentaract: {e}")
            raise PentaractAuthenticationError(f"Authentication error: {str(e)}")
    
    async def _ensure_storage(self):
        """Garante que existe um storage padrão para o ScoutBot"""
        try:
            # Lista storages existentes
            storages = await self._list_storages()
            logger.debug(f"Found {len(storages)} storages")
            
            # Procura storage do ScoutBot
            scoutbot_storage = next(
                (s for s in storages if s.get('name') == 'ScoutBot-Storage'),
                None
            )
            
            if scoutbot_storage:
                self.storage_id = scoutbot_storage['id']
                logger.info(f"Using existing storage: {self.storage_id}")
            else:
                # Cria novo storage
                logger.info("Creating new storage...")
                storage = await self._create_storage('ScoutBot-Storage')
                if storage:
                    self.storage_id = storage['id']
                    logger.info(f"Created new storage: {self.storage_id}")
                else:
                    logger.error("Failed to create storage - storage is None")
                    self.storage_id = "default"  # Fallback to default
                    logger.warning(f"Using fallback storage_id: {self.storage_id}")
            
            if not self.storage_id:
                logger.error("storage_id is still None after _ensure_storage")
                self.storage_id = "default"  # Fallback
                logger.warning(f"Using fallback storage_id: {self.storage_id}")
                
        except Exception as e:
            logger.error(f"Failed to ensure storage: {e}", exc_info=True)
            # Set fallback storage_id
            self.storage_id = "default"
            logger.warning(f"Using fallback storage_id due to error: {self.storage_id}")
    
    async def _list_storages(self) -> List[Dict[str, Any]]:
        """Lista todos os storages disponíveis"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        async with self._session.get(
            f"{self.base_url}/storages",
            headers=headers
        ) as response:
            if response.status == 200:
                return await response.json()
            return []
    
    async def _create_storage(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Cria um novo storage no Pentaract
        
        Args:
            name: Nome do storage
            
        Returns:
            Dict com informações do storage criado
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        async with self._session.post(
            f"{self.base_url}/storages",
            headers=headers,
            json={"name": name}
        ) as response:
            if response.status == 201:
                return await response.json()
            return None
    
    async def upload_file(
        self, 
        file_path: Path, 
        remote_path: str,
        folder: str = "downloads"
    ) -> Dict[str, Any]:
        """
        Faz upload de um arquivo para o Pentaract com retry logic
        
        Args:
            file_path: Caminho local do arquivo
            remote_path: Caminho remoto no storage (ex: "videos/video.mp4")
            folder: Pasta raiz no storage (padrão: "downloads")
            
        Returns:
            Dict com resultado do upload
            
        Raises:
            PentaractUploadError: Se upload falhar após todas as tentativas
            
        Example:
            >>> result = await storage.upload_file(
            ...     Path("/tmp/video.mp4"),
            ...     "youtube/video_123.mp4",
            ...     folder="downloads"
            ... )
            >>> print(result)
            {
                'success': True,
                'path': 'downloads/youtube/video_123.mp4',
                'size': 15728640,
                'uploaded_at': '2024-01-19T10:30:00Z'
            }
        """
        max_retries = settings.pentaract_retry_attempts
        
        for attempt in range(max_retries):
            try:
                result = await self._upload_file_once(file_path, remote_path, folder)
                if result['success']:
                    return result
                
                # If not successful and not last attempt, retry
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Upload attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {wait_time}s: {result.get('error', 'Unknown error')}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Last attempt failed
                    error_msg = result.get('error', 'Unknown error')
                    raise PentaractUploadError(f"Upload failed after {max_retries} attempts: {error_msg}")
                    
            except PentaractUploadError:
                raise
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Upload attempt {attempt + 1}/{max_retries} timed out, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise PentaractUploadError(f"Upload timed out after {max_retries} attempts")
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Upload attempt {attempt + 1}/{max_retries} failed with error: {e}, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise PentaractUploadError(f"Upload failed after {max_retries} attempts: {str(e)}")
        
        # Should not reach here, but just in case
        raise PentaractUploadError("Upload failed for unknown reason")
    
    async def _upload_file_once(
        self,
        file_path: Path,
        remote_path: str,
        folder: str = "downloads"
    ) -> Dict[str, Any]:
        """
        Executa uma única tentativa de upload com streaming para arquivos grandes
        
        Args:
            file_path: Caminho local do arquivo
            remote_path: Caminho remoto no storage
            folder: Pasta raiz no storage
            
        Returns:
            Dict com resultado do upload
        """
        try:
            if not file_path.exists():
                return {
                    'success': False,
                    'error': 'File not found'
                }
            
            # Check if service is available
            if not await self.is_available():
                raise PentaractUnavailableError("Pentaract service is not available")
            
            # Constrói caminho completo
            full_path = f"{folder}/{remote_path}" if folder else remote_path
            
            # Get file size
            file_size = file_path.stat().st_size
            
            logger.info(f"Uploading {file_path.name} ({file_size} bytes) to Pentaract: {full_path}")
            
            # Use streaming for large files (> 10MB)
            use_streaming = file_size > 10 * 1024 * 1024
            
            if use_streaming:
                logger.debug(f"Using streaming upload for large file ({file_size} bytes)")
                return await self._upload_file_streaming(file_path, full_path, file_size)
            else:
                # For small files, read into memory
                file_data = file_path.read_bytes()
                
                # Prepara multipart form data
                form_data = aiohttp.FormData()
                form_data.add_field(
                    'file',
                    file_data,
                    filename=file_path.name,
                    content_type='application/octet-stream'
                )
                form_data.add_field('path', full_path)
                form_data.add_field('storage_id', self.storage_id)
                
                headers = {"Authorization": f"Bearer {self.access_token}"}
                
                # Upload para Pentaract
                async with self._session.post(
                    f"{self.base_url}/files/upload",
                    headers=headers,
                    data=form_data
                ) as response:
                    if response.status == 201:
                        logger.info(f"✅ File uploaded successfully: {full_path}")
                        return {
                            'success': True,
                            'path': full_path,
                            'size': file_size,
                            'uploaded_at': datetime.utcnow().isoformat()
                        }
                    elif response.status == 401:
                        # Token expired, try to refresh
                        logger.info("Token expired during upload, attempting refresh")
                        if await self._refresh_token():
                            # Retry with new token
                            return await self._upload_file_once(file_path, remote_path, folder)
                        else:
                            return {
                                'success': False,
                                'error': 'Authentication failed'
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"Upload failed: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f"HTTP {response.status}: {error_text}"
                        }
        
        except PentaractUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file to Pentaract: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _upload_file_streaming(
        self,
        file_path: Path,
        full_path: str,
        file_size: int
    ) -> Dict[str, Any]:
        """
        Upload file using streaming to optimize memory usage
        
        Args:
            file_path: Local file path
            full_path: Full remote path
            file_size: File size in bytes
            
        Returns:
            Dict with upload result
        """
        try:
            from app.config import settings
            
            chunk_size = settings.resource_streaming_chunk_size  # Default: 1MB
            
            async def file_sender():
                """Generator to read file in chunks"""
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
            
            # Prepara multipart form data com streaming
            form_data = aiohttp.FormData()
            form_data.add_field(
                'file',
                file_sender(),
                filename=file_path.name,
                content_type='application/octet-stream'
            )
            form_data.add_field('path', full_path)
            form_data.add_field('storage_id', self.storage_id)
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            logger.debug(f"Streaming upload with {chunk_size} byte chunks")
            
            # Upload para Pentaract
            async with self._session.post(
                f"{self.base_url}/files/upload",
                headers=headers,
                data=form_data
            ) as response:
                if response.status == 201:
                    logger.info(f"✅ File uploaded successfully (streaming): {full_path}")
                    return {
                        'success': True,
                        'path': full_path,
                        'size': file_size,
                        'uploaded_at': datetime.utcnow().isoformat()
                    }
                elif response.status == 401:
                    # Token expired, try to refresh
                    logger.info("Token expired during streaming upload, attempting refresh")
                    if await self._refresh_token():
                        # Retry with new token
                        return await self._upload_file_streaming(file_path, full_path, file_size)
                    else:
                        return {
                            'success': False,
                            'error': 'Authentication failed'
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"Streaming upload failed: {response.status} - {error_text}")
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}: {error_text}"
                    }
        
        except Exception as e:
            logger.error(f"Failed to upload file with streaming: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def download_file(
        self,
        remote_path: str,
        local_path: Path
    ) -> Dict[str, Any]:
        """
        Baixa um arquivo do Pentaract com retry logic
        
        Args:
            remote_path: Caminho remoto no storage
            local_path: Caminho local para salvar
            
        Returns:
            Dict com resultado do download
        """
        max_retries = settings.pentaract_retry_attempts
        
        for attempt in range(max_retries):
            try:
                # Check if service is available
                if not await self.is_available():
                    raise PentaractUnavailableError("Pentaract service is not available")
                
                headers = {"Authorization": f"Bearer {self.access_token}"}
                
                params = {
                    'path': remote_path,
                    'storage_id': self.storage_id
                }
                
                logger.info(f"Downloading {remote_path} from Pentaract (attempt {attempt + 1}/{max_retries})")
                
                async with self._session.get(
                    f"{self.base_url}/files/download",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        # Salva arquivo
                        file_data = await response.read()
                        local_path.write_bytes(file_data)
                        
                        logger.info(f"✅ File downloaded successfully: {local_path}")
                        return {
                            'success': True,
                            'path': str(local_path),
                            'size': len(file_data)
                        }
                    elif response.status == 401:
                        # Token expired, try to refresh
                        logger.info("Token expired during download, attempting refresh")
                        if await self._refresh_token():
                            # Retry with new token
                            continue
                        else:
                            return {
                                'success': False,
                                'error': 'Authentication failed'
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"Download failed: {response.status} - {error_text}")
                        
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            logger.warning(f"Retrying in {wait_time}s")
                            await asyncio.sleep(wait_time)
                        else:
                            return {
                                'success': False,
                                'error': f"HTTP {response.status}: {error_text}"
                            }
            
            except PentaractUnavailableError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Service unavailable, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Download timed out, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    return {
                        'success': False,
                        'error': 'Download timed out'
                    }
            except Exception as e:
                logger.error(f"Failed to download file from Pentaract: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    return {
                        'success': False,
                        'error': str(e)
                    }
        
        return {
            'success': False,
            'error': f'Download failed after {max_retries} attempts'
        }
    
    async def list_files(self, folder: str = "", user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista arquivos em uma pasta do storage
        
        Args:
            folder: Pasta para listar (vazio = raiz)
            user_id: ID do usuário (opcional, para filtrar arquivos)
            
        Returns:
            Lista de arquivos e pastas
        """
        try:
            # Check if service is available
            if not await self.is_available():
                logger.warning("Pentaract service is not available")
                return []
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            params = {
                'storage_id': self.storage_id,
                'path': folder
            }
            
            async with self._session.get(
                f"{self.base_url}/files/list",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, try to refresh
                    logger.info("Token expired during list, attempting refresh")
                    if await self._refresh_token():
                        # Retry with new token
                        return await self.list_files(folder, user_id)
                return []
        
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    async def delete_file(self, remote_path: str) -> bool:
        """
        Deleta um arquivo do storage
        
        Args:
            remote_path: Caminho remoto do arquivo
            
        Returns:
            True se deletado com sucesso
        """
        try:
            # Check if service is available
            if not await self.is_available():
                logger.warning("Pentaract service is not available")
                return False
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            params = {
                'path': remote_path,
                'storage_id': self.storage_id
            }
            
            async with self._session.delete(
                f"{self.base_url}/files",
                headers=headers,
                params=params
            ) as response:
                if response.status == 204:
                    logger.info(f"✅ File deleted: {remote_path}")
                    return True
                elif response.status == 401:
                    # Token expired, try to refresh
                    logger.info("Token expired during delete, attempting refresh")
                    if await self._refresh_token():
                        # Retry with new token
                        return await self.delete_file(remote_path)
                    return False
                else:
                    logger.error(f"Failed to delete file: {response.status}")
                    return False
        
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    async def get_file_info(self, remote_path: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações de um arquivo específico
        
        Args:
            remote_path: Caminho remoto do arquivo
            
        Returns:
            Dict com informações do arquivo ou None se não encontrado
        """
        try:
            # Check if service is available
            if not await self.is_available():
                logger.warning("Pentaract service is not available")
                return None
            
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            params = {
                'path': remote_path,
                'storage_id': self.storage_id
            }
            
            async with self._session.get(
                f"{self.base_url}/files/info",
                headers=headers,
                params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, try to refresh
                    logger.info("Token expired during get_file_info, attempting refresh")
                    if await self._refresh_token():
                        # Retry with new token
                        return await self.get_file_info(remote_path)
                    return None
                elif response.status == 404:
                    logger.warning(f"File not found: {remote_path}")
                    return None
                else:
                    logger.error(f"Failed to get file info: {response.status}")
                    return None
        
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return None
    
    async def get_storage_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas do storage
        
        Args:
            user_id: ID do usuário (opcional, para filtrar estatísticas)
        
        Returns:
            Dict com estatísticas (total de arquivos, tamanho usado, etc)
        """
        try:
            files = await self.list_files()
            
            total_files = len([f for f in files if f.get('is_file')])
            total_folders = len([f for f in files if not f.get('is_file')])
            total_size = sum(f.get('size', 0) for f in files if f.get('is_file'))
            
            return {
                'total_files': total_files,
                'total_folders': total_folders,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'storage_id': self.storage_id
            }
        
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}


# Instância global
pentaract_storage = PentaractStorageService()
