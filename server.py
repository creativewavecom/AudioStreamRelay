import asyncio
import websockets
import json
import wave
import io
import threading
import time
import numpy as np
from audio_processor import AudioProcessor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioServer:
    def __init__(self):
        self.clients = set()
        self.audio_processor = AudioProcessor()
        self.is_processing = False
        
    async def register_client(self, websocket):
        """Register a new client connection"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
    async def unregister_client(self, websocket):
        """Unregister a client connection"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
        
    async def broadcast_audio(self, audio_data, sender_websocket):
        """Broadcast audio data to all clients except sender"""
        if not self.clients:
            return
            
        # Convert audio data to base64 for transmission
        message = {
            "type": "audio",
            "data": audio_data
        }
        
        disconnected_clients = set()
        for client in self.clients:
            if client != sender_websocket:
                try:
                    await client.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.add(client)
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")
                    disconnected_clients.add(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            await self.unregister_client(client)
    
    async def broadcast_playback(self, playback_message, sender_websocket):
        """Broadcast playback message to all clients including sender"""
        if not self.clients:
            return
            
        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(json.dumps(playback_message))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error broadcasting playback to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            await self.unregister_client(client)
    
    async def handle_client(self, websocket):
        """Handle individual client connections"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "audio":
                        audio_data = data.get("data")
                        logger.info(f"Received audio data of length: {len(audio_data) if audio_data else 0}")
                        
                        # Process audio for timed recording/playback cycle
                        should_trigger_playback = self.audio_processor.process_audio(audio_data)
                        
                        # Log current phase (recording/playback)
                        phase = "Recording" if self.audio_processor.is_recording else "Playback"
                        logger.info(f"Current phase: {phase}")
                        
                        # If switching to playback phase, broadcast stored audio
                        if should_trigger_playback and not self.is_processing:
                            self.is_processing = True
                            logger.info("TRIGGERING PLAYBACK - 5 second recording period ended")
                            
                            # Get all stored audio chunks and broadcast them as one message
                            stored_audio_chunks = self.audio_processor.get_stored_audio()
                            if stored_audio_chunks:
                                logger.info(f"Broadcasting {len(stored_audio_chunks)} stored audio chunks as single playback")
                                # Send all chunks as a single playback message
                                playback_message = {
                                    "type": "playback",
                                    "chunks": stored_audio_chunks
                                }
                                await self.broadcast_playback(playback_message, websocket)
                            else:
                                logger.warning("No stored audio to broadcast")
                            
                            # Reset processing flag after playback duration
                            threading.Timer(5.0, self.reset_processing_flag).start()
                        
                    elif data.get("type") == "ping":
                        # Respond to ping with pong
                        await websocket.send(json.dumps({"type": "pong"}))
                        
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received from client")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error in client handler: {e}")
        finally:
            await self.unregister_client(websocket)
    
    def reset_processing_flag(self):
        """Reset the processing flag to allow new triggers"""
        self.is_processing = False
        logger.info("Processing flag reset - ready for new triggers")
    
    def start_server(self, host="0.0.0.0", port=8000):
        """Start the WebSocket server"""
        logger.info(f"Starting audio server on {host}:{port}")
        return websockets.serve(self.handle_client, host, port)

async def main():
    """Main server entry point"""
    server = AudioServer()
    
    # Start the WebSocket server
    start_server = server.start_server()
    
    # Start HTTP server for serving static files in a separate thread
    import http.server
    import socketserver
    import os
    
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
            super().end_headers()
    
    def run_http_server():
        port = 5000
        try:
            httpd = socketserver.TCPServer(("0.0.0.0", port), CustomHTTPRequestHandler)
            httpd.allow_reuse_address = True
            logger.info(f"HTTP server started on http://0.0.0.0:{port}")
            httpd.serve_forever()
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(f"Port {port} is already in use. Please free the port and restart.")
                raise
            else:
                logger.error(f"Failed to start HTTP server: {e}")
                raise
    
    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Start WebSocket server
    await start_server
    
    # Keep the server running
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
