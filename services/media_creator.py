## services/media_creator.py

from PIL import Image
# Pillow >=10 compatibility for MoviePy
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS # type: ignore

import os
import base64
import uuid
import time
import logging
import aiofiles
import asyncio
import threading
import io

from config.settings import config
from typing import List, Optional, Union
from .r2_service import R2UploaderService
from concurrent.futures import ThreadPoolExecutor


from moviepy.editor import ImageClip, concatenate_videoclips

log = logging.getLogger(__name__)

class MediaService:
    """ Create video and upload url to redis """
    def __init__(
        self,
        image_dir: str = "data/images",
        video_dir: str = "data/videos",
        min_images: int = 5,
        resolution: tuple = (1080, 1080),
        duration_per_image: float = 2.5,
        fps: int = 24,
    ):
        self.image_dir = image_dir
        self.video_dir = video_dir
        self.min_images = min_images
        self.resolution = resolution
        self.duration_per_image = duration_per_image
        self.fps = fps
        
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.video_generation_lock = threading.Lock()
        
        self.upload = R2UploaderService(
            config.R2_ACCOUNT_ID,
            config.R2_ACCESS_KEY,
            config.R2_SECRET_KEY
        )

        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
            log.info("[ MEDIA ] ThreadPoolExecutor shut down")
                
    def _validate_image(self, image_base64: str) -> Optional[bytes]:
        """
        Validate base64 image and return decoded bytes if valid.
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            bytes: Decoded image bytes if valid
            None: If validation fails
        """
        MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
        
        # Decode base64
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            log.error(f"[ MEDIA ] Invalid base64 image: {e}")
            return None
        
        # Check file size
        if len(image_bytes) > MAX_IMAGE_SIZE:
            log.error(f"[ MEDIA ] Image too large: {len(image_bytes)} bytes")
            return None
        
        # Validate image format and dimensions
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            
            # Re-open for format/dimension check (verify() closes the file)
            img = Image.open(io.BytesIO(image_bytes))
            
            # Check dimensions
            if img.size[0] > 5000 or img.size[1] > 5000:
                log.error(f"[ MEDIA ] Image dimensions too large: {img.size}")
                return None
                            
        except Exception as e:
            log.error(f"[ MEDIA ] Invalid image data: {e}")
            return None
        
        return image_bytes


    async def save_image(self, image_base64: str) -> bool:
        """
        Save base64 image to disk (.jpg)
        Validates image format and size before saving.
        """
        # Remove base64 prefix if exists
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
        
        # Validate and get image bytes
        image_bytes = self._validate_image(image_base64)
        
        if not image_bytes:
            return False
        
        # Save to disk
        filename = f"{int(time.time())}_{uuid.uuid4().hex}.jpg"
        file_path = os.path.join(self.image_dir, filename)

        if image_bytes:
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(image_bytes)

        log.debug(f"[ MEDIA ] Image saved: {file_path}")

        return True

    def get_images(self) -> List[str]:
        """
        Get sorted list of images
        """
        files = [
            os.path.join(self.image_dir, f)
            for f in os.listdir(self.image_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        files.sort()
        return files


    def should_generate_video(self) -> bool:
        count = len(self.get_images())
        log.debug(f"[ MEDIA ] Image count: {count}")
        return count >= self.min_images
    
        
    async def generate_and_upload_video(self) -> Optional[str]:
        video_path = await self._generate_video_file_async()
        if not video_path:
            return None

        try:
           
            loop = asyncio.get_event_loop()
            video_url = await loop.run_in_executor(
                self.executor,
                self.upload.upload_video,
                video_path
            )
            log.info(f"[ MEDIA ] Video uploaded to R2: {video_url}")
            
            if not video_url:  
                log.error("[ MEDIA ] Upload failed: no URL returned")
                return None

            
            log.info(f"[ MEDIA ] Video uploaded to R2: {video_url}")
            return video_url

        finally:
            self._cleanup_videos(video_path)
            
    async def _generate_video_file_async(self) -> Optional[str]:
        """
        Wrapper async - menjalankan video generation di thread pool
        """
        loop = asyncio.get_event_loop()
        
        # run_in_executor = jalankan fungsi sync di thread terpisah
        return await loop.run_in_executor(
            self.executor,
            self._generate_video_sync  # Function yang akan dijalankan
        )

    def _generate_video_sync(self) -> Optional[str]:
        with self.video_generation_lock:
            images = self.get_images()
            
            if len(images) < self.min_images:
                return None
            
            clips = []
            final_clip = None
            
            try:
                for img in images:
                    clip = (
                        ImageClip(img)
                        .set_duration(self.duration_per_image)  
                        .resize(newsize=self.resolution)  
                    )
                    clips.append(clip)
                
                final_clip = concatenate_videoclips(clips, method="compose")
                
                filename = f"slideshow_{int(time.time())}_{uuid.uuid4().hex}.mp4"
                output_path = os.path.join(self.video_dir, filename)
                
                final_clip.write_videofile(
                    output_path,
                    fps=self.fps,
                    codec="libx264",
                    audio=False,
                    threads=4,
                    preset="medium",
                )
                
                self._cleanup_images(images)
                
                log.info(f"[ MEDIA ] Video generated: {output_path}")
                return output_path
                
            finally:
                for clip in clips:
                    try:
                        clip.close()
                    except Exception as e:
                        log.warning(f"Failed to close clip: {e}")
                
                if final_clip:
                    try:
                        final_clip.close()
                    except Exception as e:
                        log.warning(f"Failed to close final clip: {e}")


    def _cleanup_images(self, images: List[str]):
        for img in images:
            try:
                os.remove(img)
            except Exception as e:
                log.warning(f"[ MEDIA ] Failed to remove {img}: {e}")
                
                
    def _cleanup_videos(self, videos: Union[List[str], str]):
        """
        Remove video file(s) after successful upload

        Args:
            videos: single video path or list of video paths
        """
        if not videos:
            return

        if isinstance(videos, str):
            videos = [videos]

        for video in videos:
            try:
                if os.path.exists(video):
                    os.remove(video)
                    log.info(f"[ MEDIA ] Video removed: {video}")
            except Exception as e:
                log.warning(f"[ MEDIA ] Failed to remove video {video}: {e}")