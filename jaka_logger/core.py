import os
import sys
import inspect
import traceback
from datetime import datetime
from threading import Lock

# ---------------------------------------------------------------------------
# ANSI colour helpers (internal — not exported)
# ---------------------------------------------------------------------------
_COLORS = {
    "HEADER":    "\033[95m",
    "OKBLUE":    "\033[94m",
    "OKCYAN":    "\033[96m",
    "OKGREEN":   "\033[92m",
    "WARNING":   "\033[93m",
    "FAIL":      "\033[91m",
    "ENDC":      "\033[0m",
    "BOLD":      "\033[1m",
    "UNDERLINE": "\033[4m",
}

_LEVEL_COLORS = {
    "DEBUG":    _COLORS["OKCYAN"],
    "INFO":     _COLORS["OKGREEN"],
    "WARNING":  _COLORS["WARNING"],
    "ERROR":    _COLORS["FAIL"],
    "CRITICAL": _COLORS["BOLD"] + _COLORS["FAIL"],
}

# ---------------------------------------------------------------------------
# Public level map
# ---------------------------------------------------------------------------
LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}

# Module-level lock for singleton creation
_singleton_lock = Lock()


class Logger:
    """
    Thread-safe logger with optional callbacks for log entries.
    Supports console printing, file logging, level filtering,
    and callbacks for SSE / GUI / metrics pipelines.

    Improvements over v1.0:
      - File write and directory creation share a single lock (no TOCTOU).
      - Silent file-write failures emit a stderr fallback message.
      - _get_source() handles decorators, lambdas, and bare-module callers.
      - context is included in the formatted log line (not callback-only).
      - log_path is always a string from construction onward.
      - close() method for clean shutdown and test isolation.
      - set_level() is protected by the instance lock.
      - Double-checked locking on the module-level singleton.
    """

    def __init__(self, log_dir="logs", log_filename=None, console=True, min_level="DEBUG"):
        self._lock = Lock()
        self.console = console
        self._callbacks = []
        self._closed = False

        if min_level.upper() not in LEVELS:
            raise ValueError(
                "Invalid min_level '{}'. Choose from: {}".format(
                    min_level, ", ".join(LEVELS)
                )
            )
        self._min_level = min_level.upper()

        # Resolve the full path eagerly so log_path is always a string,
        # but defer directory creation until the first actual write.
        self._log_dir = log_dir
        if log_filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            log_filename = "jaka_{}.log".format(timestamp)
        self._log_filename = log_filename
        self._log_path = os.path.join(log_dir, log_filename)
        self._dir_created = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self):
        """Create the log directory on first write. Must be called under lock."""
        if not self._dir_created:
            os.makedirs(self._log_dir, exist_ok=True)
            self._dir_created = True

    def _get_source(self):
        """
        Walk the call stack (skipping Logger's own frames) and return the
        best available caller label:
          - Class name if called from an instance method.
          - Module name otherwise.
          - '__main__' if the stack is exhausted or all frames are internal.
        """
        own_module = __name__
        for frame_info in inspect.stack()[2:]:
            try:
                module = inspect.getmodule(frame_info.frame)
            except Exception:
                continue
            if module is None:
                continue
            if module.__name__ == own_module:
                continue
            self_obj = frame_info.frame.f_locals.get("self")
            if self_obj is not None and not isinstance(self_obj, Logger):
                return type(self_obj).__name__
            return module.__name__
        return "__main__"

    def _format(self, level_upper, message, exc=None, context=None):
        """Build the plain-text log line (no ANSI codes)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source = self._get_source()
        line = "[{}][{}][{}] {}".format(timestamp, level_upper, source, message)

        if context is not None:
            line += " | context={}".format(context)

        if exc is not None:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            line += "\n" + tb.rstrip()

        return line

    def _write_file(self, formatted):
        """Append a formatted line to the log file, with stderr fallback on error."""
        try:
            with self._lock:
                self._ensure_dir()
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(formatted + "\n")
        except Exception as e:
            sys.stderr.write(
                "[jaka_logger] File write failed ({}): {}\n".format(self._log_path, e)
            )

    # ------------------------------------------------------------------
    # Core log dispatcher
    # ------------------------------------------------------------------

    def _log(self, level, message, exc=None, context=None):
        if self._closed:
            return

        level_upper = level.upper()
        if LEVELS.get(level_upper, 0) < LEVELS.get(self._min_level, 0):
            return

        formatted = self._format(level_upper, message, exc, context)

        self._write_file(formatted)

        if self.console:
            color = _LEVEL_COLORS.get(level_upper, _COLORS["ENDC"])
            print(color + formatted + _COLORS["ENDC"])

        # Snapshot callbacks outside file-write lock to prevent re-entrant deadlocks.
        with self._lock:
            callbacks = list(self._callbacks)

        for cb in callbacks:
            try:
                cb(level_upper, message, exc, context)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API — log methods
    # ------------------------------------------------------------------

    def debug(self, message, exc=None, context=None):
        self._log("DEBUG", message, exc, context)

    def info(self, message, exc=None, context=None):
        self._log("INFO", message, exc, context)

    def warning(self, message, exc=None, context=None):
        self._log("WARNING", message, exc, context)

    def error(self, message, exc=None, context=None):
        self._log("ERROR", message, exc, context)

    def critical(self, message, exc=None, context=None):
        self._log("CRITICAL", message, exc, context)

    # ------------------------------------------------------------------
    # Public API — configuration
    # ------------------------------------------------------------------

    def set_level(self, level):
        level = level.upper()
        if level not in LEVELS:
            raise ValueError("Invalid level '{}'.".format(level))
        with self._lock:
            self._min_level = level

    @property
    def min_level(self):
        return self._min_level

    @min_level.setter
    def min_level(self, value):
        self.set_level(value)

    # ------------------------------------------------------------------
    # Public API — callbacks
    # ------------------------------------------------------------------

    def register_callback(self, callback):
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_callback(self, callback):
        with self._lock:
            self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    # ------------------------------------------------------------------
    # Public API — lifecycle
    # ------------------------------------------------------------------

    def close(self):
        """Mark the logger as closed. Subsequent log calls are silently ignored."""
        with self._lock:
            self._closed = True
            self._callbacks.clear()

    def flush(self):
        """No-op — file is opened/closed per write. Provided for API symmetry."""
        pass

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def log_path(self):
        """Always returns the resolved log file path (dir may not exist yet)."""
        return self._log_path

    def __repr__(self):
        return (
            "Logger(log_path={!r}, min_level={!r}, console={!r}, closed={!r})".format(
                self._log_path, self._min_level, self.console, self._closed
            )
        )


# ---------------------------------------------------------------------------
# Thread-safe lazy singleton
# ---------------------------------------------------------------------------

class _LazySingleton:
    """
    Module-level singleton that creates a default Logger on first access.
    Uses double-checked locking to be thread-safe without paying lock cost
    on every attribute access after initialisation.
    """
    _instance = None

    def _get(self):
        if self._instance is not None:
            return self._instance
        with _singleton_lock:
            if _LazySingleton._instance is None:
                _LazySingleton._instance = Logger()
        return _LazySingleton._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)

    def __repr__(self):
        return repr(self._get())


logger = _LazySingleton()