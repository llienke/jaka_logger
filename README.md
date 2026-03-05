# jaka_logger

A lightweight, thread-safe Python logger with file output, coloured console printing, level filtering, and a callback system for feeding log events into SSE streams, GUIs, or metrics pipelines.

Built for the JAKA cobot automation project. Compatible with **Python 3.5+**, no external dependencies.

---

## Installation

### From GitHub (recommended)

```bash
pip install git+https://github.com/YOUR_USERNAME/jaka_logger.git
```

To pin to a specific version tag:

```bash
pip install git+https://github.com/YOUR_USERNAME/jaka_logger.git@v1.1.0
```

### From a local clone

```bash
git clone https://github.com/YOUR_USERNAME/jaka_logger.git
cd jaka_logger
pip install .
```

### For development (editable install)

```bash
pip install -e .
```

Changes to the source are reflected immediately without reinstalling.

---

## Quick start

```python
from jaka_logger import logger

logger.info("System ready")
logger.warning("Cobot not enabled yet")
logger.error("Connection lost", exc=e)
```

Or create a named instance with custom settings:

```python
from jaka_logger import Logger

log = Logger(
    log_dir="logs",
    log_filename="robot.log",
    console=True,
    min_level="INFO",
)

log.info("Brew sequence started")
log.debug("Step 1 — this is suppressed at INFO level")
```

---

## Log output format

```
[2025-01-15 14:32:01][INFO][BrewController] Brew sequence started
[2025-01-15 14:32:01][WARNING][BrewController] Pressure low | context={'bar': 8.1}
[2025-01-15 14:32:02][ERROR][BrewController] Timeout waiting for EQ900
Traceback (most recent call last):
  ...
TimeoutError: no response after 5s
```

---

## API reference

### `Logger(log_dir, log_filename, console, min_level)`

| Parameter | Default | Description |
|---|---|---|
| `log_dir` | `"logs"` | Directory for the log file. Created on first write. |
| `log_filename` | `jaka_<timestamp>.log` | Log file name. |
| `console` | `True` | Print coloured output to stdout. |
| `min_level` | `"DEBUG"` | Minimum level to emit. One of `DEBUG INFO WARNING ERROR CRITICAL`. |

### Log methods

```python
log.debug("message", exc=None, context=None)
log.info("message", exc=None, context=None)
log.warning("message", exc=None, context=None)
log.error("message", exc=None, context=None)
log.critical("message", exc=None, context=None)
```

- `exc` — an exception instance; its traceback is appended to the log line.
- `context` — any value; serialised as `| context=<value>` in the log line and passed to callbacks.

### Other methods

```python
log.set_level("WARNING")       # Change minimum level at runtime
log.register_callback(fn)      # fn(level, message, exc, context)
log.unregister_callback(fn)
log.close()                    # Stop logging, clear callbacks
log.flush()                    # No-op, provided for API symmetry
log.log_path                   # Full path to the log file (always a string)
```

### Module-level singleton

```python
from jaka_logger import logger  # lazy, thread-safe singleton Logger()

logger.info("ready")
```

---

## Callbacks

Register a function to receive every log event — useful for forwarding to an SSE stream or a GUI message window:

```python
def sse_forwarder(level, message, exc, context):
    event_queue.put({"level": level, "msg": message})

logger.register_callback(sse_forwarder)
```

Callbacks that raise are silently swallowed so a broken callback can never crash the logger. Callbacks are invoked after the file write and console print.

---

## Running the tests

```bash
python tests/unit_test.py
```

42 tests, coloured aligned output, no external test framework needed.

---

## Project structure

```
jaka_logger/
├── jaka_logger/
│   ├── __init__.py
│   └── core.py
├── tests/
│   └── unit_test.py
├── CHANGELOG.md
├── LICENSE
├── MANIFEST.in
├── README.md
├── pyproject.toml
└── setup.py
```

---

## License

MIT