# Core Module Skills Documentation

This folder contains the core utility modules that provide fundamental functionality across the Beatrove application. These modules handle critical system operations, data processing, and security.

## Module Overview

### 🔍 `fuzzy-search.js`
**Purpose**: Intelligent search with typo tolerance
- Implements Levenshtein distance algorithm for fuzzy string matching
- Provides typo-tolerant search for DJ names and track information
- Handles common artist name variations and spelling mistakes
- Optimized thresholds for short vs long search terms

**Key Functions**:
- `levenshteinDistance()` - Calculate string similarity
- `fuzzyMatch()` - Smart matching with configurable thresholds
- `searchTracks()` - Apply fuzzy search across track metadata

---

### 🛡️ `security-utils.js`
**Purpose**: Input validation, sanitization, and security
- Comprehensive input validation for all user data
- XSS prevention through proper sanitization
- File type validation and security checks
- Configuration constants for app limits and allowed formats

**Key Features**:
- Input sanitization for track metadata
- File extension validation
- BPM, year, and tag length validation
- Demo mode security restrictions
- CORS and file access safety

---

### 🧹 `blob-manager.js`
**Purpose**: Memory management for blob URLs
- Automatic cleanup of unused blob URLs
- Prevents memory leaks from audio/image blob objects
- Reference counting and lifecycle management
- Periodic cleanup with configurable intervals

**Key Features**:
- Automatic blob URL cleanup every 30 seconds
- Reference counting to prevent premature cleanup
- Memory usage optimization for large audio libraries
- Graceful cleanup on page unload

---

### 🎯 `filter-manager.js`
**Purpose**: Centralized filter state management
- Manages all search and filter states across the application
- Handles A-Z navigation filtering
- Coordinates between multiple filter types
- Maintains filter state consistency

**Key Features**:
- Multi-criteria filter coordination
- A-Z artist navigation
- Filter state persistence
- Integration with pagination system

---

### ⚠️ `error-handler.js`
**Purpose**: Centralized error management and logging
- Rate-limited error reporting to prevent spam
- User-friendly error notifications
- Error queue management and categorization
- Integration with logging system

**Key Features**:
- Rate limiting (max 3 errors per 5 seconds)
- Error categorization and queuing
- User notification system integration
- Development vs production error handling

---

### 📝 `logger.js`
**Purpose**: Development and production logging
- Conditional logging based on environment detection
- Debug mode support for development
- Performance logging and monitoring
- Production-safe logging controls

**Key Features**:
- Automatic development environment detection
- Debug flag support via localStorage or URL params
- Performance timing utilities
- Production logging controls

## Usage Patterns

### Security First
All user inputs should be validated through `security-utils.js` before processing:
```javascript
import { SecurityUtils } from './security-utils.js';
const cleanInput = SecurityUtils.sanitizeInput(userInput);
```

### Memory Management
Use `blob-manager.js` for all blob URL operations to prevent memory leaks:
```javascript
import { BlobManager } from './blob-manager.js';
const blobUrl = blobManager.createBlobUrl(file, 'audio');
```

### Error Handling
Centralize error handling through the error handler:
```javascript
import { ErrorHandler } from './error-handler.js';
errorHandler.handle(error, 'User-friendly message', 'ERROR');
```

### Search Enhancement
Implement fuzzy search for better user experience:
```javascript
import { FuzzySearchUtils } from './fuzzy-search.js';
const matches = FuzzySearchUtils.searchTracks(query, tracks, true);
```

## Development Guidelines

1. **Always use security validation** for user inputs
2. **Implement proper error handling** with user feedback
3. **Use blob manager** for all file operations
4. **Add logging** for debugging and performance monitoring
5. **Leverage fuzzy search** for forgiving user experience
6. **Maintain filter state** through the filter manager

## Dependencies

These modules are designed to work together and may have interdependencies:
- `error-handler.js` uses `logger.js`
- `filter-manager.js` integrates with UI renderer
- `security-utils.js` provides validation for all other modules
- `blob-manager.js` is used by audio and image handling modules

## Performance Considerations

- **Blob Manager**: Automatic cleanup prevents memory bloat
- **Fuzzy Search**: Optimized algorithms for large track collections
- **Error Handler**: Rate limiting prevents performance degradation
- **Filter Manager**: Efficient state management for real-time filtering
- **Logger**: Conditional logging minimizes production overhead