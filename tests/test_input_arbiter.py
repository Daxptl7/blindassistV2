from pathlib import Path
import ast
import unittest

from gateway.input_arbiter import InputArbiter


class InputArbiterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.arbiter = InputArbiter(clock=lambda: self.now)

    def digit(self, symbols):
        result = None
        for symbol in symbols:
            result = self.arbiter.feed("RAW:1" if symbol == "." else "RAW:2")
            self.now += .1
        return result

    def test_all_physical_digits_including_shutdown(self):
        for symbols, digit in [("-----", "0"), (".----", "1"), ("..---", "2"),
                                ("...--", "3"), ("....-", "4"), (".....", "5"),
                                ("-....", "6"), ("--...", "7"), ("---..", "8"), ("----.", "9")]:
            self.assertEqual(self.digit(symbols), digit)

    def test_partial_digit_survives_many_poll_intervals_and_firmware_letters(self):
        self.arbiter.feed("RAW:1")
        for _ in range(40):
            self.now += .1
            self.assertIsNone(self.arbiter.feed(None))
            self.assertTrue(self.arbiter.physical_pending)
        self.assertIsNone(self.arbiter.feed("LETTER:E"))
        self.assertEqual(self.digit("----"), "1")

    def test_each_new_symbol_extends_gap_and_preserves_exact_boundary(self):
        result = None
        for message in ["RAW:1", "RAW:2", "RAW:2", "RAW:2", "RAW:2"]:
            result = self.arbiter.feed(message)
            self.now += 5.0
        self.assertEqual(result, "1")

    def test_expired_partial_yields_to_mobile_and_new_digit_starts_cleanly(self):
        self.arbiter.feed("RAW:1")
        self.now = 5.001
        self.assertFalse(self.arbiter.physical_pending)
        self.assertEqual(self.digit("--..."), "7")

    def test_long_press_backspace_and_ready_reset_partial(self):
        self.arbiter.feed("RAW:2")
        self.arbiter.feed("RAW:3")
        self.arbiter.feed("BACKSPACE")
        self.assertFalse(self.arbiter.physical_pending)
        self.assertEqual(self.digit(".----"), "1")
        self.arbiter.feed("RAW:1")
        self.arbiter.feed("READY")
        self.assertFalse(self.arbiter.physical_pending)
        self.assertEqual(self.digit("-----"), "0")

    def test_button3_followups_do_not_select_a_mode(self):
        for message in ["READY", "RAW:3", "WORD_SPACE", "CONFIRM", "BACKSPACE", "LETTER:?", "unknown"]:
            self.assertIsNone(self.arbiter.feed(message))
        self.assertFalse(self.arbiter.physical_pending)

    def test_legacy_letter_only_firmware_and_raw_precedence(self):
        self.assertEqual(self.arbiter.feed("LETTER:6"), "6")
        self.arbiter.feed("RAW:1")
        self.assertIsNone(self.arbiter.feed("LETTER:1"))
        self.arbiter.feed("READY")
        self.assertIsNone(self.arbiter.feed("LETTER:9"))
        self.assertEqual(self.digit("....-"), "4")

    def test_invalid_five_presses_reset_without_selecting(self):
        self.assertIsNone(self.digit(".-.-."))
        self.assertFalse(self.arbiter.physical_pending)
        self.assertEqual(self.digit("-...."), "6")

    def test_gap_configuration_has_existing_limits(self):
        for value, expected in [(0, 2), (100, 30), ("bad", 5), (None, 5), (float("nan"), 5)]:
            self.assertEqual(InputArbiter(value).symbol_gap, expected)

    def test_pure_arbiter_never_imports_a_serial_reader_or_terminal(self):
        tree = ast.parse((Path(__file__).parents[1] / "gateway/input_arbiter.py").read_text())
        imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        self.assertEqual(set(imports), {"math", "time"})
