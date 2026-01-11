# main.py

import logging
import asyncio
import signal

from core import redis
from config.logger import setup_logging
from config.settings import config

from services import (
    RedisPublisher,
    RedisSubscriber,
    MediaService
)

setup_logging()

log = logging.getLogger(__name__)

class VideoMaker:
    def __init__(self):
        
        self.shutdown_event = asyncio.Event()
        self.shutdown_lock = asyncio.Lock()
        self.stopped = False
        self.redis = None
        self.upload = None
        self.media  = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()
   
    async def start(self):
        log.info("[ VIDEO MAKER ] Starting up...")

        self.redis = await redis.init_redis()
        self.media = MediaService(min_images=10, duration_per_image=4.0)
        
        self.publisher = RedisPublisher(
            self.redis,
            config.REDIS_CHANNEL
            )
    
        self.subscriber = RedisSubscriber(
            redis_client=self.redis,
            channel=config.REDIS_CHANNEL,
            message_handler=self._handle_payload,
            shutdown_event=self.shutdown_event,
        )
        await self.subscriber.start()
        
        log.info("[ VIDEO MAKER ] Startup complete")

    async def stop(self):
        async with self.shutdown_lock:
            if self.stopped:
                return
            self.stopped = True
            
            log.info("[ VIDEO MAKER ] Shutting down...")
            self.shutdown_event.set()
            
            if self.subscriber:
                await self.subscriber.stop()
                
            if self.media: 
                await self.media.cleanup()
            
            await redis.close_redis()
            
        log.info("[ VIDEO MAKER ] Shutdown complete")

    async def _handle_payload(self, payload: dict):
        """
        Handle incoming job vacancy payload from Redis
        """
        try:
            
            if payload.get("type") != "job_vacancy":
                return

            extracted = payload.get("extracted_data")
            if not extracted or not extracted.get("is_job_vacancy"):
                return

            image_base64 = payload.get("image")
            if not image_base64:
                log.warning("[ VIDEO MAKER ] No image in payload")
                return
            
            if self.media:

                saved = await self.media.save_image(image_base64)
                if saved:
                    log.debug(f"[ VIDEO MAKER ] Image saved successfully")

                if not self.media.should_generate_video():
                    log.debug("[ VIDEO MAKER ] Not enough images yet")
                    return

                log.info("[ VIDEO MAKER ] Generating slideshow video...")

                video_url = await self.media.generate_and_upload_video()
                if not video_url:
                    return

            log.debug(f"[ VIDEO MAKER ] Video generated: {video_url}")

            video_payload = {
                "type": "video_ready",
                "source": "video_worker",
                "timestamp": payload.get("timestamp"),
                "video": {
                    "path": video_url,
                    "format": "mp4",
                },
            }

            await self.publisher.publish(video_payload)

            log.info("[ VIDEO MAKER ] video_ready event published")

        except Exception as e:
            log.error(
                "[ VIDEO MAKER ] Failed to process payload",
                exc_info=e,
            )
    
async def main():
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig):
        log.info(f"[ VIDEO MAKER ] Received signal {sig}, initiating shutdown...")
        shutdown_event.set()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    try:
        async with VideoMaker():
            log.info("[ VIDEO MAKER ] Running...")
            await shutdown_event.wait()
            log.info("[ VIDEO MAKER ] Shutdown signal received")
    except Exception as e:
        log.error(f"[ VIDEO MAKER ] Error: {e}", exc_info=True)
    finally:
        log.info("[ VIDEO MAKER ] Exiting...")

if __name__ == "__main__":
    asyncio.run(main())