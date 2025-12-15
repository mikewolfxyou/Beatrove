# Features Module Skills Documentation

This folder contains specialized feature modules that provide advanced functionality for DJ workflow enhancement. These modules implement complex features that go beyond basic track management.

## Module Overview

### 🔄 `tracklist-comparer.js`
**Purpose**: Smart DJ set comparison and analysis
- Compares DJ set tracklists against the main music library
- Identifies missing tracks that need to be acquired
- Provides fuzzy matching for track identification with confidence scores
- Supports multiple tracklist formats from various DJ software

**Key Features**:
- **Multi-Format Support**: Handles timestamped, numbered, and full format tracklists
- **Intelligent Parsing**: Extracts artist, title, label, BPM, and key information
- **Fuzzy Matching**: Uses Levenshtein distance for typo-tolerant matching
- **Confidence Scoring**: Provides match confidence percentages
- **Duplicate Detection**: Identifies duplicate entries in DJ sets
- **Label Extraction**: Parses record labels from bracket notation [Label Name]

**Supported Input Formats**:
```
[00:12] Artist - Title [Label]          # Timestamped format
1. Artist - Title                       # Numbered format
Artist - Title                          # Simple format
Artist - Title - Key - BPM.ext...       # Full library format
```

**Key Functions**:
- `parseDJSetTracklist()` - Parse various tracklist formats
- `compareWithLibrary()` - Match tracks against main library
- `calculateMatchStats()` - Generate comparison statistics
- `exportResults()` - Export missing/matched tracks

---

### 🎛️ `tracklist-compare-ui.js`
**Purpose**: User interface controller for tracklist comparison
- Manages all UI interactions for the comparison feature
- Handles file uploads via drag-and-drop or file selection
- Displays comparison results with visual indicators
- Provides export functionality for missing tracks and playlists

**Key Features**:
- **Drag & Drop Interface**: User-friendly file upload experience
- **Tabbed Results View**: Organized display of All/Matched/Missing tracks
- **Visual Match Indicators**: Color-coded results with confidence scores
  - ✅ Green: Perfect matches (100% confidence)
  - 🟡 Yellow: Good matches (70-99% confidence)
  - ❌ Red: Missing tracks (below 70% confidence)
- **Export Options**: Multiple export formats for different workflows
- **Real-time Statistics**: Live updates of match percentages and counts

**UI Components**:
- Modal dialog for comparison workflow
- Drag-and-drop file upload zone
- Tabbed results interface (All/Matched/Missing)
- Export buttons for CSV, TXT, and playlist formats
- Statistics dashboard with match percentages

**Export Capabilities**:
- **Missing Tracks CSV**: Shopping list for missing tracks
- **Missing Tracks TXT**: Simple text format for DJ software
- **Matched Playlist**: Create playlist from successfully matched tracks

## Usage Patterns

### DJ Set Comparison Workflow
1. **Upload DJ Set**: Drag and drop tracklist file or click to browse
2. **Automatic Parsing**: System detects format and extracts track information
3. **Library Matching**: Fuzzy search matches tracks against main library
4. **Review Results**: View matched and missing tracks with confidence scores
5. **Export Data**: Export missing tracks for shopping or matched tracks as playlist

### Integration Points
- Uses `FuzzySearchUtils` from core for intelligent matching
- Integrates with `SecurityUtils` for file validation
- Connects to main application state for library access
- Utilizes notification system for user feedback

## Advanced Features

### Smart Format Detection
The comparer automatically detects and handles:
- Timestamped tracklists from DJ software exports
- Numbered lists from manual DJ set documentation
- Mixed format files with inconsistent formatting
- Label information in bracket notation
- BPM and key information when available

### Fuzzy Matching Intelligence
- **Artist Name Variations**: Handles "Deadmau5" vs "deadmau5" vs "Dead Mau Five"
- **Collaboration Formats**: Matches "Artist feat. Guest" vs "Artist ft Guest"
- **Title Variations**: Handles "(Original Mix)" vs "- Original Mix" vs no suffix
- **Remix Matching**: Intelligent matching of remix versions and edits
- **Typo Tolerance**: Finds matches despite common typing errors

### Performance Optimization
- **Batch Processing**: Handles large tracklists efficiently
- **Caching**: Results cached for repeated comparisons
- **Progressive Loading**: UI updates in real-time during processing
- **Memory Management**: Proper cleanup of comparison data

## Technical Implementation

### File Processing Pipeline
1. **File Upload**: Secure file handling with type validation
2. **Content Extraction**: Text parsing with encoding detection
3. **Format Recognition**: Automatic detection of tracklist format
4. **Data Extraction**: Parse artist, title, and metadata
5. **Library Matching**: Fuzzy search against main collection
6. **Results Compilation**: Generate statistics and categorize matches

### Data Structure
```javascript
{
  totalTracks: Number,
  matchedTracks: Array,     // Tracks found in library
  missingTracks: Array,     // Tracks not found
  duplicates: Array,        // Duplicate entries in DJ set
  confidence: Object,       // Match confidence statistics
  exportData: Object        // Formatted for export
}
```

## Development Guidelines

### Adding New Tracklist Formats
1. **Update Parser**: Add new regex patterns in `parseDJSetTracklist()`
2. **Test Edge Cases**: Verify parsing with real DJ software exports
3. **Document Format**: Add format examples to documentation
4. **Update UI**: Add format hints to upload interface

### Improving Match Accuracy
1. **Tune Thresholds**: Adjust fuzzy match confidence thresholds
2. **Add Preprocessing**: Normalize text before matching
3. **Enhance Algorithms**: Improve artist/title separation logic
4. **Test Datasets**: Use real DJ sets for algorithm validation

### UI Enhancement
1. **Progress Indicators**: Show processing progress for large files
2. **Preview Mode**: Allow preview before full comparison
3. **Batch Operations**: Support multiple file uploads
4. **Advanced Filters**: Add confidence threshold controls

## Professional DJ Workflow Benefits

- **Set Planning**: Identify missing tracks before events
- **Library Gaps**: Discover which tracks to acquire next
- **Collection Analysis**: Understand library coverage for different genres/styles
- **Remix Tracking**: Find different versions of the same track
- **Label Coverage**: Analyze representation from specific record labels
- **Shopping Lists**: Generate organized lists for music purchasing

This feature module transforms Beatrove from a simple library manager into a professional DJ workflow tool, enabling DJs to analyze their collection completeness against real-world set requirements.