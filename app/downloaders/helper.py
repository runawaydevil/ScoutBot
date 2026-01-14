"""Helper functions for downloads"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

import ffmpeg
import filetype

from app.config import settings
from app.utils.logger import get_logger
from app.utils.download_utils import sizeof_fmt, shorten_url
from app.utils.html_sanitizer import sanitize_html_for_telegram

logger = get_logger(__name__)

# Verify required tools at module level
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None
if not FFMPEG_AVAILABLE:
    logger.warning("FFmpeg not found in PATH - file splitting and processing will not work")


def get_metadata(video_path: Path) -> Dict[str, Any]:
    """Get video metadata using ffmpeg"""
    width = height = duration = 0
    try:
        if not video_path.exists():
            logger.warning(f"Video path does not exist: {video_path}")
            return {"width": width, "height": height, "duration": duration}
        
        video_streams = ffmpeg.probe(str(video_path), select_streams="v")
        streams = video_streams.get("streams", [])
        for item in streams:
            height = item.get("height", 0)
            width = item.get("width", 0)
            if height and width:  # Use first valid stream
                break
        
        # Get duration from format if available
        format_info = video_streams.get("format", {})
        if "duration" in format_info:
            duration = int(float(format_info["duration"]))
    except Exception as e:
        logger.error(f"Error while getting metadata: {e}")

    return {
        "width": width,
        "height": height,
        "duration": duration,
    }


def get_caption(url: str, video_path: Path) -> str:
    """Generate caption for video"""
    meta = get_metadata(video_path)
    file_name = video_path.name
    file_size = sizeof_fmt(os.stat(video_path).st_size)

    # Generate caption without URL (user requested)
    # Format: filename + metadata (width x height, size, duration)
    cap = f"{file_name}\n\nInfo: {meta['width']}x{meta['height']} {file_size}\t{meta['duration']}s\n"
    return sanitize_html_for_telegram(cap)


def convert_audio_format(video_paths: List[Path], bot_msg) -> List[Path]:
    """Convert audio format if needed"""
    if not settings.enable_ffmpeg:
        return video_paths

    converted_paths = []
    for path in video_paths:
        try:
            streams = ffmpeg.probe(str(path))["streams"]
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            
            if not has_audio:
                logger.warning(f"No audio stream found in {path}, skipping conversion")
                converted_paths.append(path)
                continue
            
            current_extension = path.suffix.lstrip(".").lower()
            valid_audio_extensions = {"mp3", "m4a", "opus", "flac", "ogg", "wav", "aac", "webm"}
            
            # If audio_format is set (e.g., "mp3"), check if conversion is needed
            if settings.audio_format:
                target_format = settings.audio_format.lower()
                
                # Priority 1: File is already in target format and is pure audio
                if current_extension == target_format and not has_video:
                    logger.info(f"Audio file {path} is already in {target_format} format (pure audio), skipping conversion.")
                    converted_paths.append(path)
                    continue
                
                # Priority 2: File is pure audio in a valid format, but different from target
                # Only convert if target format is different
                if not has_video and current_extension in valid_audio_extensions:
                    if current_extension != target_format:
                        # Need to convert format
                        logger.info(f"Converting pure audio file {path} from {current_extension} to {target_format}")
                        new_path = path.with_suffix(f".{target_format}")
                        
                        # Build FFmpeg command for audio-only conversion (always use -vn)
                        output_args = {"vn": None}  # No video stream
                        
                        if target_format == "mp3":
                            output_args["acodec"] = "libmp3lame"
                            output_args["audio_bitrate"] = "192k"
                        elif target_format == "m4a":
                            output_args["acodec"] = "aac"
                        elif target_format == "opus":
                            output_args["acodec"] = "libopus"
                        elif target_format == "flac":
                            output_args["acodec"] = "flac"
                        else:
                            # For other formats, try to copy if compatible
                            output_args["acodec"] = "copy"
                        
                        try:
                            ffmpeg.input(str(path)).output(str(new_path), **output_args).run(
                                overwrite_output=True, quiet=True
                            )
                            
                            if new_path.exists() and new_path.stat().st_size > 0:
                                if path != new_path:
                                    path.unlink()
                                converted_paths.append(new_path)
                            else:
                                logger.warning(f"Conversion failed for {path}, keeping original")
                                converted_paths.append(path)
                        except Exception as e:
                            logger.error(f"FFmpeg error converting {path} to {target_format}: {e}")
                            converted_paths.append(path)
                    else:
                        # Same format, no conversion needed
                        logger.info(f"Audio file {path} is already in target format {target_format}, skipping conversion.")
                        converted_paths.append(path)
                    continue
                
                # Priority 3: File has video, extract audio and convert
                if has_video:
                    logger.info(f"Extracting audio from video {path} and converting to {target_format}")
                    new_path = path.with_suffix(f".{target_format}")
                    
                    # Build FFmpeg command for video extraction + conversion
                    output_args = {"vn": None}  # No video stream
                    
                    if target_format == "mp3":
                        output_args["acodec"] = "libmp3lame"
                        output_args["audio_bitrate"] = "192k"
                    elif target_format == "m4a":
                        output_args["acodec"] = "aac"
                    elif target_format == "opus":
                        output_args["acodec"] = "libopus"
                    elif target_format == "flac":
                        output_args["acodec"] = "flac"
                    else:
                        output_args["acodec"] = "copy"
                    
                    try:
                        ffmpeg.input(str(path)).output(str(new_path), **output_args).run(
                            overwrite_output=True, quiet=True
                        )
                        
                        if new_path.exists() and new_path.stat().st_size > 0:
                            if path != new_path:
                                path.unlink()
                            converted_paths.append(new_path)
                        else:
                            logger.warning(f"Conversion failed for {path}, keeping original")
                            converted_paths.append(path)
                    except Exception as e:
                        logger.error(f"FFmpeg error extracting/converting {path}: {e}")
                        converted_paths.append(path)
                    continue
            
            # If audio_format is None, handle default behavior
            elif settings.audio_format is None:
                if not has_video:
                    # Pure audio, no conversion needed
                    logger.info(f"{path} is pure audio, default format, no need to convert")
                    converted_paths.append(path)
                else:
                    # Video with audio, extract audio without re-encoding
                    logger.info(f"{path} is video, default format, extracting audio")
                    audio_stream = None
                    for stream in streams:
                        if stream.get("codec_type") == "audio":
                            audio_stream = stream
                            break
                    
                    if audio_stream:
                        # Try to determine extension from codec
                        codec_name = audio_stream.get("codec_name", "m4a")
                        ext_map = {
                            "mp3": "mp3",
                            "aac": "m4a",
                            "opus": "opus",
                            "flac": "flac",
                            "vorbis": "ogg",
                        }
                        ext = ext_map.get(codec_name, "m4a")
                        new_path = path.with_suffix(f".{ext}")
                        
                        try:
                            # Extract audio without re-encoding
                            ffmpeg.input(str(path)).output(
                                str(new_path), vn=None, acodec="copy"
                            ).run(overwrite_output=True, quiet=True)
                            
                            if new_path.exists() and new_path.stat().st_size > 0:
                                path.unlink()
                                converted_paths.append(new_path)
                            else:
                                converted_paths.append(path)
                        except Exception as e:
                            logger.error(f"FFmpeg error extracting audio from {path}: {e}")
                            converted_paths.append(path)
                    else:
                        converted_paths.append(path)
            else:
                # No conversion needed
                converted_paths.append(path)
                
        except Exception as e:
            logger.error(f"Error converting audio format for {path}: {e}", exc_info=True)
            converted_paths.append(path)

    return converted_paths


def generate_thumbnail(video_path: Path) -> Optional[Path]:
    """Generate thumbnail from video"""
    if not settings.enable_ffmpeg:
        return None

    try:
        meta = get_metadata(video_path)
        duration = meta.get("duration", 0)
        if duration == 0:
            duration = 1

        thumb_path = video_path.parent / f"{video_path.stem}-thumbnail.png"
        # A thumbnail's width and height should not exceed 320 pixels
        ffmpeg.input(str(video_path), ss=duration / 2).filter(
            "scale", "if(gt(iw,ih),300,-1)", "if(gt(iw,ih),-1,300)"
        ).output(str(thumb_path), vframes=1).run(overwrite_output=True, quiet=True)

        return thumb_path if thumb_path.exists() else None
    except Exception as e:
        logger.error(f"Error generating thumbnail: {e}")
        return None


def split_video_into_chunks(video_path: Path, max_size_mb: int = 45) -> List[Path]:
    """
    Split video into chunks smaller than max_size_mb using ffmpeg.
    Uses time-based segmentation and adjusts based on actual chunk sizes.
    Returns list of chunk file paths.
    """
    if not FFMPEG_AVAILABLE:
        raise ValueError("FFmpeg is required to split videos but was not found in PATH")
    
    max_size_bytes = max_size_mb * 1024 * 1024
    file_size = video_path.stat().st_size
    
    if file_size <= max_size_bytes:
        return [video_path]  # No need to split
    
    chunks = []
    chunk_index = 1
    start_time = 0
    
    # Get video duration
    meta = get_metadata(video_path)
    duration = meta.get("duration", 0)
    
    if duration == 0:
        raise ValueError("Cannot determine video duration for splitting")
    
    # Start with a conservative estimate (e.g., 30 seconds per chunk)
    # Then adjust based on actual chunk size
    segment_duration = 30  # Start with 30 seconds
    bytes_per_second = file_size / duration
    
    logger.info(f"Splitting video {video_path.name} ({sizeof_fmt(file_size)}) into chunks...")
    
    while start_time < duration:
        chunk_path = video_path.parent / f"{video_path.stem}_part{chunk_index:03d}{video_path.suffix}"
        end_time = min(start_time + segment_duration, duration)
        
        try:
            # Extract segment using copy codec to avoid re-encoding
            (
                ffmpeg
                .input(str(video_path), ss=start_time, t=end_time - start_time)
                .output(str(chunk_path), c="copy", avoid_negative_ts="make_zero")
                .run(overwrite_output=True, quiet=True)
            )
            
            if not chunk_path.exists() or chunk_path.stat().st_size == 0:
                if chunk_path.exists():
                    chunk_path.unlink()
                break
            
            chunk_size = chunk_path.stat().st_size
            
            if chunk_size > max_size_bytes:
                # Chunk too large, delete and try with smaller duration
                logger.warning(f"Chunk {chunk_index} too large ({sizeof_fmt(chunk_size)}), reducing segment duration")
                chunk_path.unlink()
                segment_duration = segment_duration * 0.7  # Reduce by 30%
                continue
            
            chunks.append(chunk_path)
            logger.info(f"Created chunk {chunk_index}: {chunk_path.name} ({sizeof_fmt(chunk_size)})")
            start_time = end_time
            chunk_index += 1
            
            # Adjust segment duration based on actual chunk size
            if chunk_size > 0:
                estimated_duration_for_max = (max_size_bytes / chunk_size) * segment_duration
                segment_duration = min(estimated_duration_for_max * 0.9, duration - start_time)
            
            # Ensure we don't stop too early - continue if there's still video left
            if start_time >= duration:
                break
            
        except Exception as e:
            logger.error(f"Error creating chunk {chunk_index}: {e}")
            if chunk_path.exists():
                chunk_path.unlink()
            # Don't break on error if we haven't processed much - try to continue
            if start_time < duration * 0.1:  # If we've processed less than 10%, break
                break
            # Otherwise, try to continue with next segment
            start_time = end_time
            chunk_index += 1
            continue
    
    if chunks:
        logger.info(f"Successfully split video into {len(chunks)} chunks")
        # Delete original file after successful split
        try:
            video_path.unlink()
            logger.info(f"Deleted original file: {video_path.name}")
        except Exception as e:
            logger.warning(f"Could not delete original file: {e}")
    
    return chunks if chunks else [video_path]
