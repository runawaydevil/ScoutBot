"""Unit tests for resource optimization features"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import gc

from app.services.resource_monitor_service import ResourceMonitorService
from app.config import settings


class TestResourceMonitorService:
    """Test resource monitoring service"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test that service initializes correctly"""
        service = ResourceMonitorService()
        assert service._running is False
        assert service._throttled is False
        assert service._current_cpu_usage == 0.0
        assert service._current_memory_usage == 0.0
    
    @pytest.mark.asyncio
    async def test_get_cpu_usage(self):
        """Test getting CPU usage"""
        service = ResourceMonitorService()
        service._current_cpu_usage = 45.5
        
        cpu_usage = service.get_cpu_usage()
        assert cpu_usage == 45.5
    
    @pytest.mark.asyncio
    async def test_get_memory_usage(self):
        """Test getting memory usage"""
        service = ResourceMonitorService()
        service._current_memory_usage = 60.2
        
        memory_usage = service.get_memory_usage()
        assert memory_usage == 60.2
    
    @pytest.mark.asyncio
    async def test_is_throttled_false(self):
        """Test throttled status when resources are normal"""
        service = ResourceMonitorService()
        service._throttled = False
        
        assert service.is_throttled() is False
    
    @pytest.mark.asyncio
    async def test_is_throttled_true(self):
        """Test throttled status when resources are high"""
        service = ResourceMonitorService()
        service._throttled = True
        
        assert service.is_throttled() is True
    
    @pytest.mark.asyncio
    @patch('app.services.resource_monitor_service.psutil.cpu_percent')
    @patch('app.services.resource_monitor_service.psutil.virtual_memory')
    async def test_update_resource_usage_normal(self, mock_memory, mock_cpu):
        """Test updating resource usage with normal values"""
        # Mock normal resource usage
        mock_cpu.return_value = 30.0
        mock_memory.return_value = MagicMock(percent=40.0)
        
        service = ResourceMonitorService()
        await service._update_resource_usage()
        
        assert service._current_cpu_usage == 30.0
        assert service._current_memory_usage == 40.0
        assert service._throttled is False
    
    @pytest.mark.asyncio
    @patch('app.services.resource_monitor_service.psutil.cpu_percent')
    @patch('app.services.resource_monitor_service.psutil.virtual_memory')
    async def test_update_resource_usage_high_cpu(self, mock_memory, mock_cpu):
        """Test updating resource usage with high CPU"""
        # Mock high CPU usage
        mock_cpu.return_value = 85.0
        mock_memory.return_value = MagicMock(percent=40.0)
        
        service = ResourceMonitorService()
        await service._update_resource_usage()
        
        assert service._current_cpu_usage == 85.0
        assert service._current_memory_usage == 40.0
        assert service._throttled is True
    
    @pytest.mark.asyncio
    @patch('app.services.resource_monitor_service.psutil.cpu_percent')
    @patch('app.services.resource_monitor_service.psutil.virtual_memory')
    async def test_update_resource_usage_high_memory(self, mock_memory, mock_cpu):
        """Test updating resource usage with high memory"""
        # Mock high memory usage
        mock_cpu.return_value = 30.0
        mock_memory.return_value = MagicMock(percent=85.0)
        
        service = ResourceMonitorService()
        await service._update_resource_usage()
        
        assert service._current_cpu_usage == 30.0
        assert service._current_memory_usage == 85.0
        assert service._throttled is True
    
    @pytest.mark.asyncio
    @patch('app.services.resource_monitor_service.psutil.cpu_percent')
    @patch('app.services.resource_monitor_service.psutil.virtual_memory')
    async def test_check_resources(self, mock_memory, mock_cpu):
        """Test checking resources returns correct status"""
        # Mock resource usage
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MagicMock(percent=60.0)
        
        service = ResourceMonitorService()
        status = await service.check_resources()
        
        assert status['cpu_usage'] == 50.0
        assert status['memory_usage'] == 60.0
        assert status['throttled'] is False
        assert 'cpu_threshold' in status
        assert 'memory_threshold' in status
    
    @pytest.mark.asyncio
    @patch('app.services.resource_monitor_service.psutil.cpu_percent')
    @patch('app.services.resource_monitor_service.psutil.virtual_memory')
    async def test_wait_if_throttled_not_throttled(self, mock_memory, mock_cpu):
        """Test wait_if_throttled returns immediately when not throttled"""
        # Mock normal resource usage
        mock_cpu.return_value = 30.0
        mock_memory.return_value = MagicMock(percent=40.0)
        
        service = ResourceMonitorService()
        
        # Should return immediately
        start_time = asyncio.get_event_loop().time()
        await service.wait_if_throttled("test operation")
        end_time = asyncio.get_event_loop().time()
        
        # Should take less than 1 second
        assert (end_time - start_time) < 1.0
    
    @pytest.mark.asyncio
    async def test_start_service(self):
        """Test starting the service"""
        service = ResourceMonitorService()
        
        # Mock settings to enable monitoring
        with patch.object(settings, 'resource_monitoring_enabled', True):
            await service.start()
            
            assert service._running is True
            assert service._monitor_task is not None
            
            # Clean up
            await service.stop()
    
    @pytest.mark.asyncio
    async def test_stop_service(self):
        """Test stopping the service"""
        service = ResourceMonitorService()
        
        # Mock settings to enable monitoring
        with patch.object(settings, 'resource_monitoring_enabled', True):
            await service.start()
            assert service._running is True
            
            await service.stop()
            assert service._running is False


class TestGarbageCollection:
    """Test garbage collection after uploads"""
    
    def test_gc_collect_called(self):
        """Test that gc.collect() can be called"""
        # This is a simple test to ensure gc module works
        initial_count = len(gc.get_objects())
        
        # Create some objects
        temp_list = [i for i in range(1000)]
        del temp_list
        
        # Call garbage collection
        collected = gc.collect()
        
        # Should have collected something
        assert collected >= 0
    
    def test_gc_after_upload_setting(self):
        """Test that gc_after_upload setting exists"""
        assert hasattr(settings, 'resource_gc_after_upload')
        assert isinstance(settings.resource_gc_after_upload, bool)


class TestStreamingConfiguration:
    """Test streaming configuration"""
    
    def test_streaming_chunk_size_setting(self):
        """Test that streaming chunk size setting exists"""
        assert hasattr(settings, 'resource_streaming_chunk_size')
        assert isinstance(settings.resource_streaming_chunk_size, int)
        assert settings.resource_streaming_chunk_size > 0
    
    def test_default_chunk_size(self):
        """Test default chunk size is 1MB"""
        # Default should be 1MB (1048576 bytes)
        assert settings.resource_streaming_chunk_size == 1048576


class TestResourceThresholds:
    """Test resource threshold configuration"""
    
    def test_cpu_threshold_setting(self):
        """Test CPU threshold setting exists"""
        assert hasattr(settings, 'resource_cpu_threshold')
        assert isinstance(settings.resource_cpu_threshold, float)
        assert 0 <= settings.resource_cpu_threshold <= 100
    
    def test_memory_threshold_setting(self):
        """Test memory threshold setting exists"""
        assert hasattr(settings, 'resource_memory_threshold')
        assert isinstance(settings.resource_memory_threshold, float)
        assert 0 <= settings.resource_memory_threshold <= 100
    
    def test_default_thresholds(self):
        """Test default thresholds are 80%"""
        assert settings.resource_cpu_threshold == 80.0
        assert settings.resource_memory_threshold == 80.0
    
    def test_max_memory_setting(self):
        """Test max memory per operation setting"""
        assert hasattr(settings, 'resource_max_memory_mb')
        assert isinstance(settings.resource_max_memory_mb, int)
        assert settings.resource_max_memory_mb > 0
    
    def test_monitoring_interval_setting(self):
        """Test monitoring interval setting"""
        assert hasattr(settings, 'resource_monitoring_interval')
        assert isinstance(settings.resource_monitoring_interval, int)
        assert settings.resource_monitoring_interval > 0
