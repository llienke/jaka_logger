# Changelog

## [1.1.0] - 2025

### Fixed
- File write and directory creation now share a single lock, closing a TOCTOU race condition.
- Silent file write failures now emit a warning to `stderr` instead of being swallowed.
- `_get_source()` now handles decorators, lambdas, and frames where `inspect.getmodule()` returns `None`.
- `_LazySingleton` now uses double-checked locking, making singleton creation thread-safe.
- `set_level()` now mutates `_min_level` under the instance lock.

### Added
- `context` is now included in the formatted log line (`| context=...`), not forwarded to callbacks only.
- `log_path` is always a valid string from construction onward (directory creation still deferred).
- `close()` method for clean shutdown and test isolation.
- `flush()` no-op method for API symmetry.
- `__repr__` on `Logger` showing path, level, console flag, and closed state.
- Full unit test suite (42 tests) with coloured aligned output, compatible with Python 3.5+.

### Changed
- `bcolors` class replaced with internal `_COLORS` dict (no longer leaks into the module namespace).

## [1.0.0] - 2025

### Added
- Initial release.
- Thread-safe `Logger` class with file and console output.
- Level filtering (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- Callback system for SSE / GUI / metrics pipelines.
- Lazy singleton `logger` for drop-in use.
- Deferred log directory creation (no side effects on import).