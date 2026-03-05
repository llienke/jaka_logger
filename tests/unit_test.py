"""
jaka_logger - Unit Test Suite
==============================
Custom runner: aligned columns, coloured OK / FAIL, grouped sections.
Compatible with Python 3.5+.
"""

import os
import sys
import time
import shutil
import tempfile
import threading
import unittest

# Ensure the package root is on sys.path when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jaka_logger.core import Logger, LEVELS  # noqa: E402

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
C = {
    "GREEN":  "\033[92m",
    "RED":    "\033[91m",
    "CYAN":   "\033[96m",
    "YELLOW": "\033[93m",
    "BOLD":   "\033[1m",
    "DIM":    "\033[2m",
    "ENDC":   "\033[0m",
}


def _c(color, text):
    return C.get(color, "") + text + C["ENDC"]


# ---------------------------------------------------------------------------
# Custom test runner
# ---------------------------------------------------------------------------
COL_WIDTH = 62   # width reserved for the test name column
RESULT_W  = 6    # "  OK  " or " FAIL "


class Result:
    def __init__(self, name, passed, message=""):
        self.name    = name
        self.passed  = passed
        self.message = message  # failure detail


class AlignedRunner:
    """Collect and print results with aligned OK/FAIL badges."""

    def __init__(self):
        self.results = []
        self._section = ""

    def section(self, title):
        self._section = title
        pad = "-" * (COL_WIDTH + RESULT_W + 4)
        print("\n" + _c("BOLD", "  {} {}".format(title, pad[len(title) + 2:])))

    def run(self, test_case):
        """Run a single TestCase method and record the result."""
        name = test_case.shortDescription() or test_case._testMethodName

        suite = unittest.TestLoader().loadTestsFromName(
            test_case._testMethodName, test_case.__class__
        )

        stream = open(os.devnull, "w")
        runner = unittest.TextTestRunner(stream=stream, verbosity=0)
        res = runner.run(suite)
        stream.close()

        passed = res.wasSuccessful()
        detail = ""
        if not passed:
            for _test, err in res.failures + res.errors:
                # Grab last non-empty line of traceback as short summary
                lines = [l.strip() for l in err.strip().splitlines() if l.strip()]
                detail = lines[-1] if lines else "unknown error"
                break

        r = Result(name, passed, detail)
        self.results.append(r)
        self._print_line(r)

    def _print_line(self, r):
        # Truncate or pad name to COL_WIDTH
        name = r.name
        if len(name) > COL_WIDTH:
            name = name[:COL_WIDTH - 1] + "..."

        dots = _c("DIM", "." * (COL_WIDTH - len(name) + 2))

        if r.passed:
            badge = _c("GREEN", " OK ")
        else:
            badge = _c("RED",   "FAIL")

        line = "  {}{}[{}]".format(name, dots, badge)
        print(line)

        if not r.passed and r.message:
            # Indent failure reason under the test name
            print("  " + _c("YELLOW", "    -> {}".format(r.message)))

    def summary(self):
        total  = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        bar = "=" * (COL_WIDTH + RESULT_W + 4)
        print("\n" + _c("BOLD", "  " + bar))

        status = _c("GREEN", "ALL PASSED") if failed == 0 else _c("RED", "{} FAILED".format(failed))
        print("  {} / {} tests passed   {}".format(passed, total, status))
        print(_c("BOLD", "  " + bar) + "\n")

        return failed == 0


# ---------------------------------------------------------------------------
# Helpers shared by tests
# ---------------------------------------------------------------------------

def _make_logger(tmp_dir, **kwargs):
    """Return a Logger writing to a temp directory."""
    return Logger(log_dir=tmp_dir, log_filename="test.log", console=False, **kwargs)


def _read_log(tmp_dir):
    path = os.path.join(tmp_dir, "test.log")
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def test_default_construction(self):
        """Logger() constructs with correct defaults"""
        d = tempfile.mkdtemp()
        try:
            lg = Logger(log_dir=d, console=True, min_level="DEBUG")
            self.assertTrue(lg.console)
            self.assertEqual(lg.min_level, "DEBUG")
        finally:
            shutil.rmtree(d)

    def test_log_path_always_string(self):
        """log_path is a string even before first write"""
        d = tempfile.mkdtemp()
        try:
            lg = Logger(log_dir=d, log_filename="x.log", console=False)
            self.assertIsInstance(lg.log_path, str)
            self.assertTrue(lg.log_path.endswith("x.log"))
        finally:
            shutil.rmtree(d)

    def test_dir_not_created_before_write(self):
        """Log directory is not created until first write"""
        d = tempfile.mkdtemp()
        subdir = os.path.join(d, "never_created")
        lg = Logger(log_dir=subdir, console=False)
        self.assertFalse(os.path.exists(subdir))
        shutil.rmtree(d)

    def test_invalid_min_level_raises(self):
        """ValueError raised for unknown min_level"""
        with self.assertRaises(ValueError):
            Logger(min_level="VERBOSE")

    def test_valid_min_levels_accepted(self):
        """All five standard levels accepted at construction"""
        d = tempfile.mkdtemp()
        try:
            for lvl in LEVELS:
                Logger(log_dir=d, min_level=lvl, console=False)
        finally:
            shutil.rmtree(d)

    def test_custom_filename_used(self):
        """Custom log_filename is reflected in log_path"""
        d = tempfile.mkdtemp()
        try:
            lg = Logger(log_dir=d, log_filename="custom.log", console=False)
            self.assertTrue(lg.log_path.endswith("custom.log"))
        finally:
            shutil.rmtree(d)


class TestLevelFiltering(unittest.TestCase):

    def _count_calls(self, min_level, methods):
        """Register callback, fire given methods, return call count."""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d, min_level=min_level)
            calls = []
            lg.register_callback(lambda lvl, msg, exc, ctx: calls.append(lvl))
            for m in methods:
                getattr(lg, m)("x")
            return calls
        finally:
            shutil.rmtree(d)

    def test_debug_suppressed_at_info(self):
        """DEBUG message suppressed when min_level=INFO"""
        calls = self._count_calls("INFO", ["debug"])
        self.assertEqual(calls, [])

    def test_warning_passes_at_info(self):
        """WARNING passes when min_level=INFO"""
        calls = self._count_calls("INFO", ["warning"])
        self.assertEqual(len(calls), 1)

    def test_all_levels_pass_at_debug(self):
        """All five levels fire when min_level=DEBUG"""
        calls = self._count_calls("DEBUG", ["debug", "info", "warning", "error", "critical"])
        self.assertEqual(len(calls), 5)

    def test_only_critical_passes_at_critical(self):
        """Only CRITICAL passes when min_level=CRITICAL"""
        calls = self._count_calls("CRITICAL", ["debug", "info", "warning", "error", "critical"])
        self.assertEqual(calls, ["CRITICAL"])

    def test_set_level_changes_behaviour(self):
        """set_level() immediately affects subsequent log calls"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            calls = []
            lg.register_callback(lambda lvl, msg, exc, ctx: calls.append(lvl))
            lg.info("before")
            lg.set_level("ERROR")
            lg.warning("after raise")
            self.assertEqual(calls, ["INFO"])
        finally:
            shutil.rmtree(d)

    def test_set_level_invalid_raises(self):
        """ValueError raised for unknown level string"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            with self.assertRaises(ValueError):
                lg.set_level("TRACE")
        finally:
            shutil.rmtree(d)


class TestFileOutput(unittest.TestCase):

    def test_file_created_on_first_write(self):
        """Log file is created after the first log call"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.info("hello")
            self.assertTrue(os.path.exists(lg.log_path))
        finally:
            shutil.rmtree(d)

    def test_file_not_created_before_write(self):
        """Log file does not exist before any log call"""
        d = tempfile.mkdtemp()
        subdir = os.path.join(d, "subdir")
        lg = Logger(log_dir=subdir, log_filename="test.log", console=False)
        self.assertFalse(os.path.exists(subdir))
        shutil.rmtree(d)

    def test_log_line_format(self):
        """Log line matches expected [timestamp][LEVEL][source] message format"""
        import re
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.info("format check")
            content = _read_log(d)
            pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[INFO\]\[.+\] format check"
            self.assertRegex(content, pattern)
        finally:
            shutil.rmtree(d)

    def test_exception_traceback_appended(self):
        """Exception traceback is written into the log file"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            try:
                raise ValueError("boom")
            except ValueError as e:
                lg.error("caught", exc=e)
            content = _read_log(d)
            self.assertIn("ValueError", content)
            self.assertIn("boom", content)
        finally:
            shutil.rmtree(d)

    def test_context_appears_in_log(self):
        """context kwarg is included in the formatted log line"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.info("msg", context={"key": "val"})
            content = _read_log(d)
            self.assertIn("context=", content)
            self.assertIn("val", content)
        finally:
            shutil.rmtree(d)

    def test_multiple_entries_appended(self):
        """Multiple log calls all appear in the file"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            for i in range(5):
                lg.info("line {}".format(i))
            lines = [l for l in _read_log(d).splitlines() if l.strip()]
            self.assertEqual(len(lines), 5)
        finally:
            shutil.rmtree(d)

    def test_nested_log_dir_created(self):
        """Nested log directory is created automatically on first write"""
        d = tempfile.mkdtemp()
        nested = os.path.join(d, "a", "b", "c")
        try:
            lg = Logger(log_dir=nested, log_filename="test.log", console=False)
            lg.info("nested")
            self.assertTrue(os.path.isdir(nested))
        finally:
            shutil.rmtree(d)


class TestCallbacks(unittest.TestCase):

    def test_callback_called_on_log(self):
        """Registered callback is invoked when a message is logged"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            calls = []
            lg.register_callback(lambda lvl, msg, exc, ctx: calls.append((lvl, msg)))
            lg.info("hello")
            self.assertEqual(calls, [("INFO", "hello")])
        finally:
            shutil.rmtree(d)

    def test_callback_receives_exception(self):
        """Callback receives the actual exception object"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            received = []
            lg.register_callback(lambda lvl, msg, exc, ctx: received.append(exc))
            e = RuntimeError("bad")
            lg.error("oops", exc=e)
            self.assertIs(received[0], e)
        finally:
            shutil.rmtree(d)

    def test_callback_receives_context(self):
        """Callback receives the context dict"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            received = []
            lg.register_callback(lambda lvl, msg, exc, ctx: received.append(ctx))
            lg.info("x", context={"k": "v"})
            self.assertEqual(received[0], {"k": "v"})
        finally:
            shutil.rmtree(d)

    def test_duplicate_callback_not_added(self):
        """Registering the same callback twice results in only one entry"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            cb = lambda lvl, msg, exc, ctx: None
            lg.register_callback(cb)
            lg.register_callback(cb)
            with lg._lock:
                self.assertEqual(len(lg._callbacks), 1)
        finally:
            shutil.rmtree(d)

    def test_unregister_callback(self):
        """Unregistered callback is not called on subsequent logs"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            calls = []
            cb = lambda lvl, msg, exc, ctx: calls.append(1)
            lg.register_callback(cb)
            lg.unregister_callback(cb)
            lg.info("after")
            self.assertEqual(calls, [])
        finally:
            shutil.rmtree(d)

    def test_unregister_nonexistent_is_safe(self):
        """Unregistering an unknown callback does not raise"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.unregister_callback(lambda: None)  # no-op
        finally:
            shutil.rmtree(d)

    def test_faulty_callback_doesnt_crash_logger(self):
        """A callback that raises must not prevent other callbacks from running"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            second_calls = []

            def bad_cb(lvl, msg, exc, ctx):
                raise RuntimeError("boom")

            lg.register_callback(bad_cb)
            lg.register_callback(lambda lvl, msg, exc, ctx: second_calls.append(1))
            lg.info("test")
            self.assertEqual(second_calls, [1])
        finally:
            shutil.rmtree(d)

    def test_multiple_callbacks_all_called(self):
        """All registered callbacks are invoked for each log call"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            counts = [0, 0, 0]
            for i in range(3):
                def make_cb(idx):
                    return lambda lvl, msg, exc, ctx: counts.__setitem__(idx, counts[idx] + 1)
                lg.register_callback(make_cb(i))
            lg.info("x")
            self.assertEqual(counts, [1, 1, 1])
        finally:
            shutil.rmtree(d)

    def test_reentrant_callback_no_deadlock(self):
        """Callback that logs back into the same logger completes without deadlock"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            done = threading.Event()

            def reentrant(lvl, msg, exc, ctx):
                if msg != "inner":
                    lg.debug("inner")
                    done.set()

            lg.register_callback(reentrant)
            lg.info("outer")
            self.assertTrue(done.wait(timeout=2), "deadlock detected")
        finally:
            shutil.rmtree(d)


class TestConsoleOutput(unittest.TestCase):

    def test_console_true_prints(self):
        """console=True causes print() to be called"""
        from unittest.mock import patch
        d = tempfile.mkdtemp()
        try:
            lg = Logger(log_dir=d, log_filename="test.log", console=True)
            with patch("builtins.print") as mock_print:
                lg.info("visible")
                self.assertEqual(mock_print.call_count, 1)
        finally:
            shutil.rmtree(d)

    def test_console_false_no_print(self):
        """console=False suppresses print() entirely"""
        from unittest.mock import patch
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            with patch("builtins.print") as mock_print:
                lg.info("silent")
                mock_print.assert_not_called()
        finally:
            shutil.rmtree(d)

    def test_ansi_codes_in_console_output(self):
        """ANSI escape sequences are present in coloured console output"""
        import io
        d = tempfile.mkdtemp()
        try:
            lg = Logger(log_dir=d, log_filename="test.log", console=True)
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                lg.warning("colour test")
            finally:
                sys.stdout = old_stdout
            self.assertIn("\033[", buf.getvalue())
        finally:
            shutil.rmtree(d)


class TestSourceDetection(unittest.TestCase):

    def test_source_from_class_method(self):
        """Source reflects the calling class name"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            calls = []
            lg.register_callback(lambda lvl, msg, exc, ctx: calls.append(lvl))

            class MyService:
                def do_thing(self):
                    lg.info("from class")

            MyService().do_thing()
            content = _read_log(d)
            self.assertIn("MyService", content)
        finally:
            shutil.rmtree(d)

    def test_source_fallback_is_string(self):
        """_get_source() always returns a non-empty string"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            source = lg._get_source()
            self.assertIsInstance(source, str)
            self.assertTrue(len(source) > 0)
        finally:
            shutil.rmtree(d)


class TestLifecycle(unittest.TestCase):

    def test_close_stops_logging(self):
        """Messages after close() are silently ignored"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.info("before close")
            lg.close()
            lg.info("after close")
            content = _read_log(d)
            self.assertIn("before close", content)
            self.assertNotIn("after close", content)
        finally:
            shutil.rmtree(d)

    def test_close_clears_callbacks(self):
        """close() removes all registered callbacks"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.register_callback(lambda lvl, msg, exc, ctx: None)
            lg.close()
            with lg._lock:
                self.assertEqual(len(lg._callbacks), 0)
        finally:
            shutil.rmtree(d)

    def test_repr_is_informative(self):
        """repr() returns a non-empty descriptive string"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            r = repr(lg)
            self.assertIn("Logger", r)
            self.assertIn("test.log", r)
        finally:
            shutil.rmtree(d)

    def test_flush_does_not_raise(self):
        """flush() is a safe no-op"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            lg.flush()  # must not raise
        finally:
            shutil.rmtree(d)


class TestThreadSafety(unittest.TestCase):

    def test_concurrent_writes_no_corruption(self):
        """Concurrent writes from multiple threads produce correct line count"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            threads = []
            n_threads, n_per = 10, 50

            def write_many():
                for i in range(n_per):
                    lg.info("msg")

            for _ in range(n_threads):
                t = threading.Thread(target=write_many)
                threads.append(t)
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            lines = [l for l in _read_log(d).splitlines() if l.strip()]
            self.assertEqual(len(lines), n_threads * n_per)
        finally:
            shutil.rmtree(d)

    def test_concurrent_callback_registration(self):
        """Concurrent register/unregister does not raise or corrupt state"""
        d = tempfile.mkdtemp()
        try:
            lg = _make_logger(d)
            errors = []

            def toggle():
                cb = lambda lvl, msg, exc, ctx: None
                try:
                    for _ in range(50):
                        lg.register_callback(cb)
                        lg.unregister_callback(cb)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=toggle) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
        finally:
            shutil.rmtree(d)


class TestSingleton(unittest.TestCase):

    def test_singleton_is_logger_instance(self):
        """Module-level logger proxy resolves to a Logger instance"""
        from jaka_logger.core import logger
        self.assertIsInstance(logger._get(), Logger)

    def test_singleton_repr_is_string(self):
        """repr(logger) returns a non-empty string"""
        from jaka_logger.core import logger
        self.assertIsInstance(repr(logger), str)

    def test_singleton_thread_safe(self):
        """Concurrent accesses to logger all return the same instance"""
        from jaka_logger import core as _core
        # Reset singleton for this test
        original = _core._LazySingleton._instance
        _core._LazySingleton._instance = None
        instances = []

        def grab():
            from jaka_logger.core import logger
            instances.append(logger._get())

        threads = [threading.Thread(target=grab) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Restore
        _core._LazySingleton._instance = original

        ids = {id(i) for i in instances}
        self.assertEqual(len(ids), 1, "Multiple singleton instances created")


# ---------------------------------------------------------------------------
# Entry point - custom runner
# ---------------------------------------------------------------------------

SECTIONS = [
    ("Initialisation",    TestInit),
    ("Level Filtering",   TestLevelFiltering),
    ("File Output",       TestFileOutput),
    ("Callbacks",         TestCallbacks),
    ("Console Output",    TestConsoleOutput),
    ("Source Detection",  TestSourceDetection),
    ("Lifecycle",         TestLifecycle),
    ("Thread Safety",     TestThreadSafety),
    ("Singleton",         TestSingleton),
]


def main():
    runner = AlignedRunner()
    t0 = time.time()

    print("\n" + _c("BOLD", "  jaka_logger - Unit Test Suite"))
    print(_c("DIM", "  Python {}".format(sys.version.split()[0])))

    for section_name, cls in SECTIONS:
        runner.section(section_name)
        loader = unittest.TestLoader()
        for name in loader.getTestCaseNames(cls):
            tc = cls(name)
            runner.run(tc)

    elapsed = time.time() - t0
    print(_c("DIM", "  Completed in {:.2f}s".format(elapsed)))
    runner.summary()

    sys.exit(0 if all(r.passed for r in runner.results) else 1)


if __name__ == "__main__":
    main()