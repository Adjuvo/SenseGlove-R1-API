"""Regression: live USB close must hard-kill; lib.Terminate / os._exit hang on Windows."""

import os
import sys

import pytest

sys.path.append(os.path.abspath("."))

try:
    from SG_API import SG_CPP_SDK as cpp
except Exception as e:
    pytest.skip(f"SG_CPP_SDK unavailable: {e}", allow_module_level=True)

pytestmark = pytest.mark.skipif(not getattr(cpp, "USE_CPP_SDK", False), reason="CPP SDK disabled")


def test_close_hard_exits_when_lib_present(monkeypatch):
    calls = []

    def fake_hard_exit(code=0):
        calls.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(cpp, "_hard_exit_process", fake_hard_exit)

    class FakeLib:
        def Terminate(self):
            raise AssertionError("lib.Terminate must not be called")

    old = (cpp.lib, cpp._cpp_closing)
    try:
        cpp.lib = FakeLib()
        cpp._cpp_closing = False
        with pytest.raises(SystemExit) as exc:
            cpp.close()
        assert exc.value.code == 0
        assert calls == [0]
    finally:
        cpp.lib, cpp._cpp_closing = old


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only handle typing")
def test_void_p_preserves_pseudo_handle_width():
    """Without c_void_p, ctypes truncates -1 → ERROR_INVALID_HANDLE on TerminateProcess."""
    import ctypes

    truncated = ctypes.c_int(-1).value & 0xFFFFFFFF
    full = ctypes.c_void_p(-1).value
    assert full != truncated or ctypes.sizeof(ctypes.c_void_p) == 4
    assert full in (-1, (1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1)
