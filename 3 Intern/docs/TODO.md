# TODO

## Known Bugs

- [ ] Screenshots LUT differs from Adobe Premiere (uses nearest-neighbor instead of trilinear interpolation)
- [ ] Multiple instances can be started simultaneously
- [ ] No graceful handling if audio playback device is unavailable

## Planned Features

- [ ] Config file for parameters (threshold, gap, preview duration)
- [ ] Save/Load session state
- [ ] Undo for "Ignore" action
- [ ] Keyboard shortcuts (Space=Play, Arrow keys=Navigate)
- [ ] Progress bar for long operations (export, screenshots)
- [ ] Windows support (replace macOS `say` with cross-platform TTS)

## Technical Improvements

- [ ] Refactor global state to classes
- [ ] Add unit tests
- [ ] Proper error recovery for partial failures
- [ ] Make LUT path configurable
- [ ] Trilinear interpolation for LUT application
- [ ] Consistent language (all English or all German)

## Open Questions

- Should peaks be editable (move time, split, merge)?
- Export format: MP3 only or also WAV option?
- Should video sync be optional toggle in UI?
