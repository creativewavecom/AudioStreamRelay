import numpy as np
import base64
import io
import wave
import logging
from collections import deque
import time

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, threshold=0.1, window_size=10, silence_duration=1.0):
        """
        Initialize audio processor with voice activity detection
        
        Args:
            threshold: Volume threshold for voice activity detection
            window_size: Number of audio chunks to analyze for average volume
            silence_duration: Duration of silence required to trigger playback (seconds)
        """
        self.threshold = threshold
        self.window_size = window_size
        self.silence_duration = silence_duration
        
        # Circular buffer for volume measurements
        self.volume_buffer = deque(maxlen=window_size)
        
        # Audio storage for playback
        self.audio_chunks = deque(maxlen=100)  # Store last 100 chunks
        
        # Timing for silence detection
        self.last_voice_activity_time = time.time()
        self.silence_triggered = False
        
    def decode_audio_data(self, base64_audio):
        """Decode base64 audio data to numpy array"""
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(base64_audio)
            
            # For WebM/Opus or WAV data, we can't directly convert to numpy
            # Instead, we'll calculate volume based on the raw byte data
            # This is a simplified approach for voice activity detection
            
            # Convert to numpy array of bytes for volume calculation
            byte_array = np.frombuffer(audio_bytes, dtype=np.uint8)
            
            # Convert to signed values for RMS calculation
            signed_array = byte_array.astype(np.float32) - 128.0
            
            return signed_array
            
        except Exception as e:
            logger.error(f"Error decoding audio data: {e}")
            return None
    
    def calculate_volume(self, audio_data):
        """Calculate RMS volume of audio data"""
        if audio_data is None or len(audio_data) == 0:
            return 0.0
        
        # Calculate RMS (Root Mean Square) volume
        rms = np.sqrt(np.mean(audio_data ** 2))
        
        # Normalize the volume to a reasonable range (0-1)
        normalized_volume = min(rms / 128.0, 1.0)
        
        return float(normalized_volume)
    
    def is_voice_active(self, volume):
        """Determine if voice is currently active based on volume"""
        return volume > self.threshold
    
    def process_audio(self, base64_audio):
        """
        Process incoming audio data and determine if playback should be triggered
        
        Returns:
            bool: True if playback should be triggered, False otherwise
        """
        # Decode audio data
        audio_data = self.decode_audio_data(base64_audio)
        if audio_data is None:
            return False
        
        # Calculate volume
        volume = self.calculate_volume(audio_data)
        
        # Add to volume buffer
        self.volume_buffer.append(volume)
        
        # Calculate average volume over the window
        if len(self.volume_buffer) >= self.window_size:
            avg_volume = np.mean(list(self.volume_buffer))
            
            current_time = time.time()
            
            # Check if voice is currently active
            if self.is_voice_active(avg_volume):
                self.last_voice_activity_time = current_time
                self.silence_triggered = False
                logger.debug(f"Voice activity detected - Volume: {avg_volume:.4f}")
                
            else:
                # Check if enough silence has passed to trigger playback
                silence_duration = current_time - self.last_voice_activity_time
                
                if (silence_duration >= self.silence_duration and 
                    not self.silence_triggered and 
                    len(self.audio_chunks) > 0):
                    
                    self.silence_triggered = True
                    logger.info(f"Voice activity ended - Triggering playback after {silence_duration:.2f}s silence")
                    return True
        
        return False
    
    def store_audio_chunk(self, base64_audio):
        """Store audio chunk for potential playback"""
        self.audio_chunks.append(base64_audio)
    
    def get_stored_audio(self):
        """Get stored audio chunks for playback"""
        if not self.audio_chunks:
            return None
        
        # Return the most recent audio chunk
        # In a more sophisticated implementation, you might concatenate multiple chunks
        return list(self.audio_chunks)[-1] if self.audio_chunks else None
    
    def clear_stored_audio(self):
        """Clear stored audio chunks"""
        self.audio_chunks.clear()
        logger.info("Stored audio cleared")
    
    def get_current_volume(self):
        """Get current average volume"""
        if self.volume_buffer:
            return np.mean(list(self.volume_buffer))
        return 0.0
    
    def reset_voice_activity(self):
        """Reset voice activity detection state"""
        self.volume_buffer.clear()
        self.last_voice_activity_time = time.time()
        self.silence_triggered = False
        logger.info("Voice activity detection reset")
