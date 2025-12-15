# Audio Module Skills Documentation

This folder contains the audio processing and playback modules that provide professional DJ-quality audio functionality. These modules handle everything from basic audio playback to advanced visualization and crossfading capabilities.

## Module Overview

### 🎵 `audio-manager.js`
**Purpose**: Core audio playback and Web Audio API management
- Centralized audio file handling with blob URL management
- Web Audio API integration for real-time audio analysis
- Race condition prevention for smooth audio operations
- Memory-optimized audio processing with automatic cleanup

**Key Features**:
- **File Management**: Secure audio file loading with validation
- **Web Audio API**: Audio context, analyser nodes, and source management
- **Blob URL Lifecycle**: Automatic memory management and cleanup
- **Preview System**: Queue-based audio preview with race condition protection
- **Crossfade Support**: Volume control and fading capabilities for DJ mixing
- **Error Handling**: Comprehensive audio error management and recovery

**Core Capabilities**:
```javascript
// Audio file management
loadAudioFile(file, filename)
previewTrack(track, filename)
stopAudio()

// Web Audio API integration
initializeAudioContext()
connectVisualizer(audioElement)
getAudioAnalyser()

// Memory management
cleanupUnusedBlobUrls()
cleanup()
```

**Advanced Features**:
- Automatic audio context initialization on user gesture
- CORS-friendly audio loading with security validation
- Progressive audio loading with user feedback
- Integration with visualizer for real-time spectrum analysis

---

### 🎛️ `play-queue.js`
**Purpose**: Professional playlist management with DJ-style features
- Auto-play functionality for seamless track progression
- Professional auto-mix with customizable crossfade durations
- Queue management with previous/next navigation
- Real-time playback status and progress tracking

**Key Features**:
- **Auto-Play Queue**: Seamless progression through playlists
- **Auto-Mix Crossfading**: Professional DJ-style transitions (1-15 seconds)
- **Dual Audio Players**: Simultaneous audio streams during crossfade
- **Queue Controls**: Previous, pause/resume, next, stop functionality
- **Progress Tracking**: Real-time track position and queue status
- **Visual Feedback**: Fading player indicators during transitions

**DJ Features**:
- **Crossfade Engine**: Smooth volume transitions between tracks
- **Timing Control**: Adjustable crossfade duration via slider
- **Manual Controls**: Skip to next track with auto-mix enabled
- **Queue Navigation**: Jump to any position in the playlist
- **State Management**: Persistent playback state across interactions

**Queue Operations**:
```javascript
// Queue management
initializeQueue(tracks)
playQueue()
playNext() / playPrevious()
stopQueue()

// Auto-mix controls
setAutoMixEnabled(enabled)
setCrossfadeDuration(seconds)
toggleAutoMix()

// Status tracking
getCurrentTrack()
getQueuePosition()
isPlaying()
```

---

### 🌊 `audio-visualizer.js`
**Purpose**: Advanced audio visualization with multiple waveform styles
- 6 different professional waveform visualization styles
- Real-time audio analysis and spectrum display
- Zoom and pan functionality for detailed waveform inspection
- Full track overview with playback position tracking

**Visualization Styles**:
1. **Default (Cyan)**: High-resolution waveform with glow effects
2. **Orange**: SoundCloud-style peaks with playback progress
3. **Green**: Spotify-style bar visualization with gradients
4. **Blue Stereo**: Audacity-style dual-channel waveforms
5. **Colored**: Logic Pro-style frequency-based color mapping
6. **Overview**: Complete song visualization with progress tracking

**Key Features**:
- **Multiple Canvas Support**: Render to different popup windows
- **Real-time Analysis**: Live frequency spectrum during playback
- **Zoom Controls**: 0.5x to 10x zoom levels with pan functionality
- **Auto-scroll**: Follow playback position automatically
- **Memory Management**: Canvas pooling and efficient rendering
- **Style Switching**: Change visualization styles during playback

**Visualization Capabilities**:
```javascript
// Waveform control
showWaveform(canvasId, audioElement)
hideWaveform()
setWaveformStyle(style)

// Zoom and navigation
setZoom(level)
panWaveform(offset)
resetZoom()
toggleAutoScroll()

// Analysis
analyzeFullTrack(audioElement)
getCurrentPosition()
updatePlaybackProgress(progress)
```

**Advanced Features**:
- **Full Track Analysis**: Complete waveform generation for overview mode
- **Synthetic Waveforms**: CORS-free waveform generation for reliable performance
- **Progressive Rendering**: Smooth animation with requestAnimationFrame
- **Canvas Optimization**: Efficient rendering with memory pooling
- **Position Tracking**: Real-time cursor showing playback position

## Technical Architecture

### Web Audio API Integration
```javascript
// Audio pipeline
AudioContext → MediaElementSource → AnalyserNode → Destination
                                        ↓
                                   Frequency Data
                                        ↓
                                   Visualizer Canvas
```

### Crossfade Engine
```javascript
// Dual player crossfade
Player A (fading out) ←→ Volume Control ←→ Player B (fading in)
        ↓                                           ↓
    Fade Timer                                 Fade Timer
        ↓                                           ↓
   Remove Player                              Main Player
```

### Memory Management
- **Blob URL Cleanup**: Automatic cleanup every 30 seconds
- **Canvas Pooling**: Reusable canvas contexts to prevent memory leaks
- **Audio Context Management**: Proper cleanup of Web Audio API resources
- **File Reference Tracking**: Prevent orphaned audio references

## Usage Patterns

### Basic Audio Playback
```javascript
// Initialize audio manager
const audioManager = new AudioManager(notificationSystem);

// Preview a track
await audioManager.previewTrack(track, filename);

// Connect visualizer
audioManager.connectVisualizer(audioElement);
```

### Playlist with Auto-Mix
```javascript
// Initialize queue manager
const playQueue = new PlayQueueManager(audioManager, appState, notifications);

// Set up auto-mix
playQueue.setAutoMixEnabled(true);
playQueue.setCrossfadeDuration(8); // 8-second crossfade

// Start playlist
playQueue.initializeQueue(tracks);
playQueue.playQueue();
```

### Advanced Visualization
```javascript
// Initialize visualizer
const visualizer = new AudioVisualizer(audioManager);

// Set up waveform style
visualizer.setWaveformStyle('colored');
visualizer.showWaveform('waveform-canvas', audioElement);

// Configure zoom
visualizer.setZoom(2.0);
visualizer.panWaveform(0.5);
```

## Professional DJ Features

### Auto-Mix Crossfading
- **Seamless Transitions**: Professional DJ-style crossfading between tracks
- **Customizable Duration**: 1-15 second crossfade timing
- **Visual Feedback**: Dual player display during transitions
- **Manual Override**: Skip to next track while maintaining crossfade

### Waveform Analysis
- **Real-time Spectrum**: Live frequency analysis during playback
- **Multiple Styles**: Choose from 6 professional visualization styles
- **Zoom Navigation**: Detailed waveform inspection with pan controls
- **Progress Tracking**: Visual playback position indicator

### Memory Optimization
- **Efficient Loading**: Progressive audio file loading with feedback
- **Automatic Cleanup**: Blob URL and canvas memory management
- **Pool Management**: Reusable resources to prevent memory leaks
- **CORS Handling**: Secure audio access with fallback strategies

## Development Guidelines

### Adding New Visualization Styles
1. **Define Style**: Add new style constant to visualizer
2. **Implement Renderer**: Create rendering function in `drawWaveform()`
3. **Add Controls**: Update UI style selector
4. **Test Performance**: Verify smooth animation at 60fps

### Extending Crossfade Features
1. **Timing Controls**: Add new fade curve algorithms
2. **EQ Integration**: Implement frequency-based crossfading
3. **Beat Matching**: Add BPM-aware transition timing
4. **Visual Effects**: Enhance crossfade visual indicators

### Performance Optimization
1. **Canvas Efficiency**: Optimize rendering loops for large waveforms
2. **Audio Buffering**: Implement progressive audio loading
3. **Memory Monitoring**: Add memory usage tracking and limits
4. **CPU Throttling**: Adaptive quality based on system performance

## Integration Points

- **Core Modules**: Uses security-utils, blob-manager, error-handler
- **UI System**: Integrates with audio popup windows and controls
- **Application State**: Connects to main app state for track data
- **Notification System**: Provides user feedback for audio operations

These audio modules transform Beatrove into a professional DJ tool with advanced audio processing capabilities, providing the foundation for professional music management and mixing workflows.