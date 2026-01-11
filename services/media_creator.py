"""
Main media service orchestrator
"""
import logging
import asyncio
import threading
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from config.settings import config
from services.media import FileStorage, ImageValidator, VideoGenerator

from .r2_service import R2UploaderService

log = logging.getLogger(__name__)

class MediaService:
    """
    Orchestrates media processing workflow:
    - Image validation and storage
    - Video generation
    - Cloud upload
    """
    
    def __init__(
        self,
        image_dir: str = "data/images",
        video_dir: str = "data/videos",
        min_images: int = 5,
        resolution: tuple = (1080, 1920),
        duration_per_image: float = 3.0,
        fps: int = 24,
    ):
        self.min_images = min_images
        
        # Initialize sub-services
        self.validator = ImageValidator()
        self.storage = FileStorage(image_dir, video_dir)
        self.video_gen = VideoGenerator(
            resolution=resolution,
            duration_per_image=duration_per_image,
            fps=fps
        )
        self.uploader = R2UploaderService(
            config.R2_ACCOUNT_ID,
            config.R2_ACCESS_KEY,
            config.R2_SECRET_KEY
        )
        
        # Thread management
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.video_generation_lock = threading.Lock()
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
            log.info("[ MEDIA ] ThreadPoolExecutor shut down")
    
    async def save_image(self, image_base64: str) -> bool:
        """
        Validate and save base64 image to disk
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        # Validate image
        image_bytes = self.validator.validate(image_base64)
        if not image_bytes:
            return False
        
        # Save to disk
        try:
            await self.storage.save_image(image_bytes)
            return True
        except Exception as e:
            log.error(f"[ MEDIA ] Failed to save image: {e}")
            return False
    
    def should_generate_video(self) -> bool:
        """
        Check if there are enough images to generate a video
        
        Returns:
            bool: True if video should be generated
        """
        count = len(self.storage.get_images())
        log.debug(f"[ MEDIA ] Image count: {count}/{self.min_images}")
        return count >= self.min_images
    
    async def generate_and_upload_video(self) -> Optional[str]:
        """
        Generate video from images and upload to cloud storage
        
        Returns:
            str: Video URL if successful, None otherwise
        """
        # Generate video file
        video_path = await self._generate_video_async()
        if not video_path:
            return None
        
        try:
            # Upload to cloud storage
            loop = asyncio.get_event_loop()
            video_url = await loop.run_in_executor(
                self.executor,
                self.uploader.upload_video,
                video_path
            )
            
            if not video_url:
                log.error("[ MEDIA ] Upload failed: no URL returned")
                return None
            
            log.info(f"[ MEDIA ] Video uploaded: {video_url}")
            return video_url
            
        except Exception as e:
            log.error(f"[ MEDIA ] Upload error: {e}", exc_info=True)
            return None
            
        finally:
            # Clean up video file
            self.storage.cleanup_videos(video_path)
    
    async def _generate_video_async(self) -> Optional[str]:
        """
        Generate video asynchronously in thread pool
        
        Returns:
            str: Path to generated video file, None if failed
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._generate_video_sync
        )
    
    def _generate_video_sync(self) -> Optional[str]:
        """
        Synchronous video generation (runs in thread pool)
        
        Returns:
            str: Path to generated video file, None if failed
        """
        with self.video_generation_lock:
            # Get images
            images = self.storage.get_images()
            
            if len(images) < self.min_images:
                log.warning(f"[ MEDIA ] Not enough images: {len(images)}/{self.min_images}")
                return None
            
            # Get output path
            output_path = self.storage.get_video_path()
            
            try:
                # Generate video
                success = self.video_gen.generate(images, output_path)
                
                if not success:
                    return None
                
                # Clean up source images
                self.storage.cleanup_images(images)
                
                return output_path
                
            except Exception as e:
                log.error(f"[ MEDIA ] Video generation failed: {e}", exc_info=True)
                return None