"""
Video generation service using MoviePy - Low Memory Version
"""
import logging
from typing import List, Optional, Tuple
from PIL import Image

# Pillow >=10 compatibility for MoviePy
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS # type: ignore

from moviepy.editor import (
    ImageClip,
    concatenate_videoclips,
    CompositeVideoClip,
    ColorClip,
    AudioFileClip
)

log = logging.getLogger(__name__)
SOUNDTRACK_PATH = "data/templates/sound/soundtrack.mp3"

class VideoGenerator:
    """Generates slideshow videos from images - Low Memory Version"""
    
    def __init__(
        self,
        resolution: Tuple[int, int] = (1080, 1920),
        duration_per_image: float = 3.0,
        fps: int = 24,
        background_color: Tuple[int, int, int] = (255, 255, 255)  # White background
    ):
        self.resolution = resolution
        self.duration_per_image = duration_per_image
        self.fps = fps
        self.background_color = background_color
    
    def generate(self, image_paths: List[str], output_path: str) -> bool:
        """
        Generate slideshow video from images
        
        Args:
            image_paths: List of paths to image files
            output_path: Path where video should be saved
            
        Returns:
            bool: True if successful, False otherwise
        """
        clips = []
        final_clip = None
        audio_clip = None
        
        try:
            for img_path in image_paths:
                clip = self._create_composite_clip(img_path)
                if clip:
                    clips.append(clip)
            
            if not clips:
                log.error("[ VIDEO ] No clips created")
                return False
            
            # Concatenate all clips
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # Add audio if soundtrack exists
            try:
                import os
                if os.path.exists(SOUNDTRACK_PATH):
                    audio_clip = AudioFileClip(SOUNDTRACK_PATH)
                    
                    # Loop audio to match video duration
                    video_duration = final_clip.duration
                    if audio_clip.duration < video_duration:
                        loops = int(video_duration / audio_clip.duration) + 1
                        audio_clip = audio_clip.audio_loop(n=loops) # type: ignore
                    
                    # Trim audio to exact video duration
                    audio_clip = audio_clip.subclip(0, video_duration)
                    
                    # Set audio to video
                    final_clip = final_clip.set_audio(audio_clip)
                    log.info(f"[ VIDEO ] Audio added from {SOUNDTRACK_PATH}")
                else:
                    log.warning(f"[ VIDEO ] Soundtrack not found: {SOUNDTRACK_PATH}")
            except Exception as e:
                log.warning(f"[ VIDEO ] Failed to add audio: {e}")
            
            # Write video file
            final_clip.write_videofile(
                output_path,
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                threads=2,
                preset="medium",
                logger=None  # Suppress MoviePy's verbose output
            )
            
            log.info(f"[ VIDEO ] Video generated: {output_path}")
            return True
            
        except Exception as e:
            log.error(f"[ VIDEO ] Failed to generate video: {e}", exc_info=True)
            return False
            
        finally:
            # Clean up clips
            for clip in clips:
                try:
                    clip.close()
                except Exception as e:
                    log.warning(f"[ VIDEO ] Failed to close clip: {e}")
            
            if audio_clip:
                try:
                    audio_clip.close()
                except Exception as e:
                    log.warning(f"[ VIDEO ] Failed to close audio clip: {e}")
            
            if final_clip:
                try:
                    final_clip.close()
                except Exception as e:
                    log.warning(f"[ VIDEO ] Failed to close final clip: {e}")
    
    def _create_composite_clip(self, img_path: str) -> Optional[CompositeVideoClip]:
        """
        Create composite clip with solid color background and centered foreground
        
        Args:
            img_path: Path to image file
            
        Returns:
            CompositeVideoClip or None if failed
        """
        try:
            # Create solid color background (no processing needed - very light on memory)
            bg_clip = ColorClip(
                size=self.resolution,
                color=self.background_color,
                duration=self.duration_per_image
            )
            
            # Create foreground (maintains aspect ratio)
            fg_clip = self._create_foreground_clip(img_path)
            
            # Composite both layers
            composite = CompositeVideoClip(
                [
                    bg_clip,
                    fg_clip.set_position("center")
                ],
                size=self.resolution
            )
            
            return composite
            
        except Exception as e:
            log.error(f"[ VIDEO ] Failed to create clip for {img_path}: {e}")
            return None
    
    def _create_foreground_clip(self, img_path: str) -> ImageClip:
        """
        Create foreground clip that fits within resolution without stretching
        
        Args:
            img_path: Path to image file
            
        Returns:
            ImageClip: Properly sized foreground clip
        """
        clip = ImageClip(img_path)
        
        # Get original dimensions
        original_width, original_height = clip.size
        target_width, target_height = self.resolution
        
        # Calculate scaling factor to fit within target resolution
        width_ratio = target_width / original_width
        height_ratio = target_height / original_height
        scale_factor = min(width_ratio, height_ratio)
        
        # Calculate new dimensions
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # Resize maintaining aspect ratio using tuple (width, height)
        resized_clip = clip.resize((new_width, new_height)) # type: ignore
        
        return resized_clip.set_duration(self.duration_per_image)



# """
# Video generation service using MoviePy
# """
# import logging
# import numpy as np
# from typing import List, Optional, Tuple
# from PIL import Image

# # Pillow >=10 compatibility for MoviePy
# if not hasattr(Image, "ANTIALIAS"):
#     Image.ANTIALIAS = Image.Resampling.LANCZOS # type: ignore

# from moviepy.editor import (
#     ImageClip,
#     concatenate_videoclips,
#     CompositeVideoClip,
#     AudioFileClip
# )

# log = logging.getLogger(__name__)
# SOUNDTRACK_PATH = "data/templates/sound/soundtrack.mp3"

# class VideoGenerator:
#     """Generates slideshow videos from images"""
    
#     def __init__(
#         self,
#         resolution: Tuple[int, int] = (1080, 1920),
#         duration_per_image: float = 3.0,
#         fps: int = 24,
#         blur_strength: int = 30
#     ):
#         self.resolution = resolution
#         self.duration_per_image = duration_per_image
#         self.fps = fps
#         self.blur_strength = blur_strength
    
#     def generate(self, image_paths: List[str], output_path: str) -> bool:
#         """
#         Generate slideshow video from images
        
#         Args:
#             image_paths: List of paths to image files
#             output_path: Path where video should be saved
            
#         Returns:
#             bool: True if successful, False otherwise
#         """
#         clips = []
#         final_clip = None
#         audio_clip = None
        
#         try:
#             for img_path in image_paths:
#                 clip = self._create_composite_clip(img_path)
#                 if clip:
#                     clips.append(clip)
            
#             if not clips:
#                 log.error("[ VIDEO ] No clips created")
#                 return False
            
#             # Concatenate all clips
#             final_clip = concatenate_videoclips(clips, method="compose")
            
#             # Add audio if soundtrack exists
#             try:
#                 import os
#                 if os.path.exists(SOUNDTRACK_PATH):
#                     audio_clip = AudioFileClip(SOUNDTRACK_PATH)
                    
#                     # Loop audio to match video duration
#                     video_duration = final_clip.duration
#                     if audio_clip.duration < video_duration:
#                         # Loop audio to fill video duration
#                         loops = int(video_duration / audio_clip.duration) + 1
#                         audio_clip = audio_clip.audio_loop(n=loops) # type: ignore
                    
#                     # Trim audio to exact video duration
#                     audio_clip = audio_clip.subclip(0, video_duration)
                    
#                     # Set audio to video
#                     final_clip = final_clip.set_audio(audio_clip)
#                     log.info(f"[ VIDEO ] Audio added from {SOUNDTRACK_PATH}")
#                 else:
#                     log.warning(f"[ VIDEO ] Soundtrack not found: {SOUNDTRACK_PATH}")
#             except Exception as e:
#                 log.warning(f"[ VIDEO ] Failed to add audio: {e}")
            
#             # Write video file
#             final_clip.write_videofile(
#                 output_path,
#                 fps=self.fps,
#                 codec="libx264",
#                 audio_codec="aac",
#                 threads=4,
#                 preset="medium",
#                 logger=None  # Suppress MoviePy's verbose output
#             )
            
#             log.info(f"[ VIDEO ] Video generated: {output_path}")
#             return True
            
#         except Exception as e:
#             log.error(f"[ VIDEO ] Failed to generate video: {e}", exc_info=True)
#             return False
            
#         finally:
#             # Clean up clips
#             for clip in clips:
#                 try:
#                     clip.close()
#                 except Exception as e:
#                     log.warning(f"[ VIDEO ] Failed to close clip: {e}")
            
#             if audio_clip:
#                 try:
#                     audio_clip.close()
#                 except Exception as e:
#                     log.warning(f"[ VIDEO ] Failed to close audio clip: {e}")
            
#             if final_clip:
#                 try:
#                     final_clip.close()
#                 except Exception as e:
#                     log.warning(f"[ VIDEO ] Failed to close final clip: {e}")
    
#     def _create_composite_clip(self, img_path: str) -> Optional[CompositeVideoClip]:
#         """
#         Create composite clip with blurred background and centered foreground
        
#         Args:
#             img_path: Path to image file
            
#         Returns:
#             CompositeVideoClip or None if failed
#         """
#         try:
#             # Create blurred background (fills entire frame)
#             bg_clip = self._create_background_clip(img_path)
            
#             # Create foreground (maintains aspect ratio)
#             fg_clip = self._create_foreground_clip(img_path)
            
#             # Composite both layers
#             composite = CompositeVideoClip(
#                 [
#                     bg_clip,
#                     fg_clip.set_position("center")
#                 ],
#                 size=self.resolution
#             )
            
#             return composite
            
#         except Exception as e:
#             log.error(f"[ VIDEO ] Failed to create clip for {img_path}: {e}")
#             return None
    
#     def _create_background_clip(self, img_path: str) -> ImageClip:
#         """
#         Create blurred background clip that fills entire frame
        
#         Args:
#             img_path: Path to image file
            
#         Returns:
#             ImageClip: Blurred background clip
#         """
#         # Load image and resize to fill frame
#         clip = ImageClip(img_path)
        
#         # Resize to target resolution (may crop)
#         resized_clip = clip.resize(self.resolution) # type: ignore
        
#         # Apply blur effect
#         blurred_clip = resized_clip.fl_image(self._apply_blur)
        
#         # Set duration
#         return blurred_clip.set_duration(self.duration_per_image)
    
#     def _create_foreground_clip(self, img_path: str) -> ImageClip:
#         """
#         Create foreground clip that fits within resolution without stretching
        
#         Args:
#             img_path: Path to image file
            
#         Returns:
#             ImageClip: Properly sized foreground clip
#         """
#         clip = ImageClip(img_path)
        
#         # Get original dimensions
#         original_width, original_height = clip.size
#         target_width, target_height = self.resolution
        
#         # Calculate scaling factor to fit within target resolution
#         width_ratio = target_width / original_width
#         height_ratio = target_height / original_height
#         scale_factor = min(width_ratio, height_ratio)
        
#         # Calculate new dimensions
#         new_width = int(original_width * scale_factor)
#         new_height = int(original_height * scale_factor)
        
#         # Resize maintaining aspect ratio using tuple (width, height)
#         resized_clip = clip.resize((new_width, new_height)) # type: ignore
        
#         return resized_clip.set_duration(self.duration_per_image)
    
#     def _apply_blur(self, frame: np.ndarray) -> np.ndarray:
#         """
#         Apply Gaussian blur to a frame
        
#         Args:
#             frame: numpy array representing the frame
            
#         Returns:
#             np.ndarray: Blurred frame
#         """
#         try:
#             from scipy.ndimage import gaussian_filter
            
#             # Calculate sigma from blur strength
#             sigma = self.blur_strength / 3.0
            
#             # Apply Gaussian blur
#             # For RGB images, we need to blur each channel separately
#             if len(frame.shape) == 3:  # RGB image
#                 blurred = np.zeros_like(frame)
#                 for i in range(frame.shape[2]):
#                     blurred[:, :, i] = gaussian_filter(frame[:, :, i], sigma=sigma)
#                 return blurred
#             else:  # Grayscale
#                 return gaussian_filter(frame, sigma=sigma)
                
#         except Exception as e:
#             log.warning(f"[ VIDEO ] Blur effect failed: {e}, returning original frame")
#             return frame