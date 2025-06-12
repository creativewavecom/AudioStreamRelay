import numpy as np
import base64
import io
import wave
import logging
from collections import deque
import time

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, record_duration=5.0, playback_duration=5.0):
        """
        Initialize audio processor with timed recording and playback
        
        Args:
            record_duration: Duration to record audio in seconds
            playback_duration: Duration to play back audio in seconds
        """
        self.record_duration = record_duration
        self.playback_duration = playback_duration
        
        # Audio storage for playback
        self.audio_chunks = deque()
        
        # Timing for record/playback cycle
        self.cycle_start_time = time.time()
        self.is_recording = True  # Start with recording
        self.playback_triggered = False
        
    def decode_audio_data(self, base64_audio):
        """Decode base64 audio data to numpy array"""
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(base64_audio)
            
            # Convert to numpy array of bytes
            byte_array = np.frombuffer(audio_bytes, dtype=np.uint8)
            
            # Convert to signed values centered around 0
            signed_array = byte_array.astype(np.float32) - 128.0
            
            return signed_array
            
        except Exception as e:
            logger.error(f"Error decoding audio data: {e}")
            return None
    
    def calculate_volume(self, audio_data):
        """Calculate volume using variance"""
        if audio_data is None or len(audio_data) == 0:
            return 0.0
        
        # Calculate variance to detect signal changes
        variance = float(np.var(audio_data))
        
        # Normalize variance to a 0-1 range
        normalized_volume = min(variance / 1000.0, 1.0)
        
        return float(normalized_volume)
    
    def process_audio(self, base64_audio):
        """
        Process incoming audio data and determine if playback should be triggered
        
        Returns:
            bool: True if playback should be triggered, False otherwise
        """
        current_time = time.time()
        elapsed_time = current_time - self.cycle_start_time
        
        if self.is_recording:
            # Recording phase
            if elapsed_time < self.record_duration:
                # Store audio chunk during recording
                self.store_audio_chunk(base64_audio)
                return False
            else:
                # Switch to playback phase
                self.is_recording = False
                self.cycle_start_time = current_time
                self.playback_triggered = True
                logger.info(f"Switching to playback phase. Stored {len(self.audio_chunks)} audio chunks")
                return True
        else:
            # Playback phase
            if elapsed_time < self.playback_duration:
                # Continue playback (don't store new audio during playback)
                return False
            else:
                # Switch back to recording phase
                self.is_recording = True
                self.cycle_start_time = current_time
                self.playback_triggered = False
                # Clear stored audio for next cycle
                self.clear_stored_audio()
                logger.info("Switching to recording phase")
                return False
    
    def store_audio_chunk(self, base64_audio):
        """Store audio chunk for potential playback"""
        self.audio_chunks.append(base64_audio)
    
    def get_stored_audio(self):
        """Get stored audio chunks for playback"""
        return list(self.audio_chunks)
    
    def clear_stored_audio(self):
        """Clear stored audio chunks"""
        self.audio_chunks.clear()
        logger.info("Stored audio cleared")
    
    def get_current_volume(self):
        """Get current volume (simplified for new implementation)"""
        return 1.0 if self.is_recording else 0.0
    
    def reset_voice_activity(self):
        """Reset the recording/playback cycle"""
        self.cycle_start_time = time.time()
        self.is_recording = True
        self.playback_triggered = False
        self.clear_stored_audio()
        logger.info("Audio processing cycle reset")