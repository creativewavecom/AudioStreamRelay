class AudioClient {
    constructor() {
        this.websocket = null;
        this.mediaStream = null;
        this.audioContext = null;
        this.mediaRecorder = null;
        this.isRecording = false;
        this.analyser = null;
        this.dataArray = null;
        
        // UI elements
        this.connectionStatus = document.getElementById('connection-status');
        this.micStatus = document.getElementById('mic-status');
        this.audioLevel = document.getElementById('audio-level');
        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.logContent = document.getElementById('log-content');
        
        // Initialize event listeners
        this.initializeEventListeners();
        
        // Connect to WebSocket server
        this.connectWebSocket();
    }
    
    initializeEventListeners() {
        this.startBtn.addEventListener('click', () => this.startAudio());
        this.stopBtn.addEventListener('click', () => this.stopAudio());
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8000`;
        
        this.log('Connecting to WebSocket server...', 'info');
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            this.log('Connected to server', 'success');
            this.updateConnectionStatus(true);
        };
        
        this.websocket.onmessage = (event) => {
            this.handleWebSocketMessage(event);
        };
        
        this.websocket.onclose = () => {
            this.log('Disconnected from server', 'error');
            this.updateConnectionStatus(false);
            
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                this.log('Attempting to reconnect...', 'info');
                this.connectWebSocket();
            }, 3000);
        };
        
        this.websocket.onerror = (error) => {
            this.log('WebSocket error occurred', 'error');
            console.error('WebSocket error:', error);
        };
    }
    
    handleWebSocketMessage(event) {
        try {
            const message = JSON.parse(event.data);
            
            if (message.type === 'audio') {
                this.playReceivedAudio(message.data);
            } else if (message.type === 'pong') {
                this.log('Received pong from server', 'info');
            }
        } catch (error) {
            this.log('Error parsing WebSocket message', 'error');
            console.error('Message parsing error:', error);
        }
    }
    
    async playReceivedAudio(base64AudioData) {
        try {
            this.log(`Received audio data for playback, length: ${base64AudioData.length}`, 'info');
            
            // Decode base64 audio data
            const audioData = atob(base64AudioData);
            const arrayBuffer = new ArrayBuffer(audioData.length);
            const uint8Array = new Uint8Array(arrayBuffer);
            
            for (let i = 0; i < audioData.length; i++) {
                uint8Array[i] = audioData.charCodeAt(i);
            }
            
            this.log('Audio data decoded, attempting playback...', 'info');
            
            // Create audio context if not exists
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // Decode audio data
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            
            // Create and play audio source
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            source.start();
            
            this.log('Audio playback started successfully', 'success');
            
        } catch (error) {
            this.log(`Audio playback error: ${error.message}`, 'error');
            console.error('Audio playback error:', error);
        }
    }
    
    async startAudio() {
        try {
            this.log('Requesting microphone access...', 'info');
            
            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 44100
                }
            });
            
            this.log('Microphone access granted', 'success');
            this.updateMicrophoneStatus(true);
            
            // Initialize audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Set up audio analysis
            this.setupAudioAnalysis();
            
            // Start recording
            this.startRecording();
            
            // Update UI
            this.startBtn.disabled = true;
            this.stopBtn.disabled = false;
            
        } catch (error) {
            this.log('Error accessing microphone', 'error');
            console.error('Microphone access error:', error);
            alert('Could not access microphone. Please check permissions.');
        }
    }
    
    setupAudioAnalysis() {
        // Create analyser node for audio level visualization
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        
        const source = this.audioContext.createMediaStreamSource(this.mediaStream);
        source.connect(this.analyser);
        
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        
        // Start audio level monitoring
        this.monitorAudioLevel();
    }
    
    monitorAudioLevel() {
        const updateLevel = () => {
            if (!this.isRecording) return;
            
            this.analyser.getByteFrequencyData(this.dataArray);
            
            // Calculate average volume
            let sum = 0;
            for (let i = 0; i < this.dataArray.length; i++) {
                sum += this.dataArray[i];
            }
            const average = sum / this.dataArray.length;
            
            // Update visual audio level (0-100%)
            const level = (average / 255) * 100;
            this.audioLevel.style.width = `${level}%`;
            
            // Add active class for animation when audio is detected
            if (level > 5) {
                this.audioLevel.classList.add('active');
            } else {
                this.audioLevel.classList.remove('active');
            }
            
            requestAnimationFrame(updateLevel);
        };
        
        updateLevel();
    }
    
    startRecording() {
        const options = {
            mimeType: 'audio/webm;codecs=opus',
            audioBitsPerSecond: 16000
        };
        
        // Fallback for browsers that don't support webm
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            options.mimeType = 'audio/wav';
        }
        
        this.mediaRecorder = new MediaRecorder(this.mediaStream, options);
        
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && this.websocket.readyState === WebSocket.OPEN) {
                this.sendAudioData(event.data);
            }
        };
        
        this.mediaRecorder.onerror = (error) => {
            this.log('MediaRecorder error', 'error');
            console.error('MediaRecorder error:', error);
        };
        
        // Start recording with small time slices for real-time streaming
        this.mediaRecorder.start(100); // 100ms chunks
        this.isRecording = true;
        
        this.log('Started audio recording and streaming', 'success');
    }
    
    async sendAudioData(audioBlob) {
        try {
            // Convert blob to base64
            const arrayBuffer = await audioBlob.arrayBuffer();
            const base64Audio = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
            
            this.log(`Sending audio chunk, size: ${audioBlob.size} bytes`, 'info');
            
            // Send audio data via WebSocket
            const message = {
                type: 'audio',
                data: base64Audio
            };
            
            this.websocket.send(JSON.stringify(message));
            
        } catch (error) {
            this.log('Error sending audio data', 'error');
            console.error('Audio sending error:', error);
        }
    }
    
    stopAudio() {
        this.log('Stopping audio recording...', 'info');
        
        // Stop recording
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
        
        // Stop media stream
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        // Close audio context
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        this.isRecording = false;
        
        // Update UI
        this.updateMicrophoneStatus(false);
        this.audioLevel.style.width = '0%';
        this.audioLevel.classList.remove('active');
        this.startBtn.disabled = false;
        this.stopBtn.disabled = true;
        
        this.log('Audio recording stopped', 'info');
    }
    
    updateConnectionStatus(connected) {
        this.connectionStatus.textContent = connected ? 'Connected' : 'Disconnected';
        this.connectionStatus.className = `status-value ${connected ? 'connected' : 'disconnected'}`;
    }
    
    updateMicrophoneStatus(active) {
        this.micStatus.textContent = active ? 'Active' : 'Inactive';
        this.micStatus.className = `status-value ${active ? 'active' : 'inactive'}`;
    }
    
    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        
        logEntry.innerHTML = `
            <span class="log-timestamp">[${timestamp}]</span>
            <span class="log-message log-${type}">${message}</span>
        `;
        
        this.logContent.appendChild(logEntry);
        this.logContent.scrollTop = this.logContent.scrollHeight;
        
        // Keep only last 50 log entries
        while (this.logContent.children.length > 50) {
            this.logContent.removeChild(this.logContent.firstChild);
        }
    }
    
    // Send periodic ping to keep connection alive
    startPingInterval() {
        setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // Ping every 30 seconds
    }
}

// Initialize the audio client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    const audioClient = new AudioClient();
    audioClient.startPingInterval();
});

// Handle page visibility changes to manage audio
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Page is hidden - could pause audio streaming
        console.log('Page hidden - audio streaming continues');
    } else {
        // Page is visible again
        console.log('Page visible - audio streaming active');
    }
});
