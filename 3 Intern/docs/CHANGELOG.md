# Changelog

All notable changes to PeakCut are documented here.

## [v1.2.0] - 2025-02-02

### Added
- Config system: All parameters now configurable via `config.json`
  - threshold_factor, min_gap_ms, preview_duration_ms, context_duration_ms, fps, tts_voice
- Documentation folder `docs/` with ARCHITECTURE, README, SETUP, CHANGELOG, TODO, COMMANDS

### Fixed
- **Critical:** Export now always uses mic audio tracks, regardless of UI playback mode
  - Previously, export incorrectly used keyboard audio when UI was in keyboard mode
  - Keyboard mode is now preview-only; export always contains interview audio

### Changed
- Removed hardcoded parameters from peaks.py, export.py, utils.py
- Export no longer depends on UI mode state

## [v1.1.0] - 2025-02-01

### Added
- Screenshots feature: Extract 100 random frames per video with Kodak LUT
- UI improvements and better status display
- GitHub documentation

### Changed
- Reorganized folder structure for better UX
- Consolidated format_peak_time in utils.py

## [v1.0-stable] - 2025-01-31

### Added
- TTS for unlimited peak numbers (no more 49 limit)
- English UI labels
- Double-click scripts for easy setup and start
- Portable paths based on script location

### Changed
- Switched from pre-recorded MP3 numbers to macOS TTS
- Made app fully portable (no hardcoded paths)

## Initial Development

### 2025-01-30
- Initial commit - PeakCut V1
- Basic peak detection and export
- Requirements.txt added
- CLAUDE.md documentation

### Core Features (v1.0)
- Peak detection via amplitude threshold
- Keyboard/Mic playback modes
- Video sync via cross-correlation
- MP3 export with spoken numbers
- TXT export with timecodes
