"""Persistent menu decoding, fed only by the existing terminal input owner.

No serial handle is accepted or opened here. Active modes keep their own input
handling; this object is used only while the orchestrator owns the main menu.
"""
import math
import time


_DIGITS = {"-----": "0", ".----": "1", "..---": "2", "...--": "3",
           "....-": "4", ".....": "5", "-....": "6", "--...": "7",
           "---..": "8", "----.": "9"}


class InputArbiter:
    def __init__(self, symbol_gap=5.0, *, clock=time.monotonic):
        try:
            gap = float(symbol_gap)
            self.symbol_gap = max(2.0, min(30.0, gap)) if math.isfinite(gap) else 5.0
        except (TypeError, ValueError):
            self.symbol_gap = 5.0
        self._clock = clock
        self._symbols = ""
        self._last_symbol = None
        self._raw_seen = False

    def _expire_partial(self):
        if (self._last_symbol is not None
                and self._clock() - self._last_symbol > self.symbol_gap):
            self._symbols = ""
            self._last_symbol = None

    @property
    def physical_pending(self):
        self._expire_partial()
        return bool(self._symbols)

    def feed(self, message):
        """Consume one already-read event; return a physical digit when complete.

        None/poll boundaries do not reset a partial digit. READY/backspace and
        LETTER-only legacy firmware match MorseSerial.read_menu_digit().
        """
        self._expire_partial()
        if message in ("RAW:1", "RAW:2"):
            self._raw_seen = True
            self._symbols += "." if message == "RAW:1" else "-"
            self._last_symbol = self._clock()
            if len(self._symbols) == 5:
                digit = _DIGITS.get(self._symbols)
                self._symbols = ""
                return digit
        elif message == "BACKSPACE":
            self._symbols = self._symbols[:-1]
        elif message == "READY":
            self._symbols = ""
            self._last_symbol = None
        elif isinstance(message, str) and message.startswith("LETTER:") and not self._raw_seen:
            char = message.split(":", 1)[1]
            if char in tuple("0123456789"):
                return char
        return None
