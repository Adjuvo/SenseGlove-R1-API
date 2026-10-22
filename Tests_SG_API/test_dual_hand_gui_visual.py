"""
Visual test matching examples/user_GUI_2gloves.py.

Captures the left 3D pane from the desktop compositor (QScreen.grabWindow(0)),
not the Qt widget HWND (that misses Qt3D children) and not QRenderCapture
(replacing the frame graph whites the view). Window stays on top.
"""

import json
import os
import subprocess
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_RUNNER = r'''
import json, sys, os
sys.path.insert(0, os.path.abspath("."))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from SG_API import SG_main, SG_types as SG_T
from SG_API import SG_GUI as GUI

WARMUP_MS = 2500
GAP_MS = 2500
MIN_PERC_BENT_DELTA = 500
MIN_PIXEL_CHANGE = 0.02
MAX_PIXEL_CHANGE = 0.85


def index_flex(perc_gui):
    return perc_gui.finger_bars[0][0].value()


def mean_rgb(img, step=24):
    if img.isNull() or img.width() == 0:
        return (0.0, 0.0, 0.0)
    r = g = b = n = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            r += c.red(); g += c.green(); b += c.blue(); n += 1
    return (r / n, g / n, b / n)


def grey_fraction(img, step=24):
    """Empty QWidget grey, not the dark Qt3D clear color (10,10,30)."""
    if img.isNull():
        return 1.0
    grey = total = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if r > 180 and g > 180 and b > 180 and max(r, g, b) - min(r, g, b) < 12:
                grey += 1
            total += 1
    return grey / max(total, 1)


def bright_fraction(img, threshold=40, step=24):
    """Links are white-ish on a near-black clear color — hand visible if some pixels light up."""
    if img.isNull():
        return 0.0
    bright = total = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            if (c.red() + c.green() + c.blue()) / 3 > threshold:
                bright += 1
            total += 1
    return bright / max(total, 1)


def pixel_change_fraction(a, b, tolerance=8, step=16):
    if a.isNull() or b.isNull() or a.size() != b.size():
        return 1.0
    changed = total = 0
    for y in range(0, a.height(), step):
        for x in range(0, a.width(), step):
            ca, cb = a.pixelColor(x, y), b.pixelColor(x, y)
            if (
                abs(ca.red() - cb.red()) > tolerance
                or abs(ca.green() - cb.green()) > tolerance
                or abs(ca.blue() - cb.blue()) > tolerance
            ):
                changed += 1
            total += 1
    return changed / max(total, 1)


def pixel_variance(img, step=24):
    if img.isNull() or img.width() == 0:
        return 0.0
    vals = []
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            vals.append((c.red() + c.green() + c.blue()) / 3)
    avg = sum(vals) / len(vals)
    return sum((v - avg) ** 2 for v in vals) / len(vals)


def capture_left_3d(app, dual_gui):
    """Desktop compositor grab of the left 3D pane (screen coords, window id 0)."""
    dual_gui.raise_()
    dual_gui.activateWindow()
    c = dual_gui.left_container
    tl = c.mapToGlobal(c.rect().topLeft())
    screen = app.screenAt(tl) or app.primaryScreen()
    geo = screen.geometry()
    pm = screen.grabWindow(0, tl.x() - geo.x(), tl.y() - geo.y(), c.width(), c.height())
    return pm.toImage()


def looks_like_hand(img):
    return (not img.isNull()) and grey_fraction(img) < 0.25 and pixel_variance(img) > 20


app = QApplication(sys.argv)
dual_gui = GUI.DualHandGUI()
dual_gui.setWindowFlag(Qt.WindowStaysOnTopHint, True)
dual_gui.show()
dual_gui.raise_()
dual_gui.activateWindow()

try:
    _init_mode = os.environ.get("SG_VISUAL_INIT", "usb")
    if _init_mode == "two_sim":
        SG_main.init(2, SG_T.Com_type.SIMULATED_GLOVE)
    elif _init_mode == "two_sim_cpp":
        from SG_API import SG_callback_manager as SG_cb
        SG_cb.init()
        SG_main.init(2, SG_T.Com_type.SIMULATED_GLOVE)
    else:
        SG_main.init(1, SG_T.Com_type.REAL_GLOVE_USB)
        SG_main.init_rembrandt_sim(SG_T.Hand.LEFT, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)
    left_id = SG_main.get_left_hand_deviceid()
    right_id = SG_main.get_right_hand_deviceid()
    if left_id is None or right_id is None:
        raise RuntimeError(f"missing hands left={left_id} right={right_id}")
except Exception as exc:
    print(json.dumps({"skipped": True, "reason": str(exc)}), flush=True)
    sys.exit(0)

if SG_main.get_COM_type(left_id) == SG_T.Com_type.SIMULATED_GLOVE:
    SG_main.SG_sim.set_mode(left_id, SG_main.SG_sim.Simulation_Mode.FINGERS_OPEN_CLOSE)

dual_gui.left_gui.create_hand_exo(SG_main.get_exo_joints_poss_rots(left_id)[0])
dual_gui.right_gui.create_hand_exo(SG_main.get_exo_joints_poss_rots(right_id)[0])


def on_new_data(from_device_id):
    if from_device_id == left_id:
        exo_poss, _ = SG_main.get_exo_joints_poss_rots(left_id)
        dual_gui.left_gui.update_hand_exo(exo_poss)
        fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(left_id)
        dual_gui.left_gui.set_fingertip_points(fingertips_poss, fingertips_rots)
        dual_gui.left_gui.set_fingertip_thimbles(SG_main.get_fingertip_thimble_dims(left_id))
        flexion, abduction = SG_main.get_percentage_bents(left_id)
        dual_gui.left_perc_bent.update(flexion, abduction)
    elif from_device_id == right_id:
        exo_poss, _ = SG_main.get_exo_joints_poss_rots(right_id)
        dual_gui.right_gui.update_hand_exo(exo_poss)
        fingertips_poss, fingertips_rots = SG_main.get_fingertips_pos_rot(right_id)
        dual_gui.right_gui.set_fingertip_points(fingertips_poss, fingertips_rots)
        dual_gui.right_gui.set_fingertip_thimbles(SG_main.get_fingertip_thimble_dims(right_id))
        flexion, abduction = SG_main.get_percentage_bents(right_id)
        dual_gui.right_perc_bent.update(flexion, abduction)

SG_main.subscr_r1_data_callback(on_new_data)

state = {}

def after_warmup():
    state["bar0"] = index_flex(dual_gui.left_perc_bent)
    state["link_x0"] = dual_gui.left_gui.linkages[1].linkages[-1].end.x()
    dual_gui.left_gui.requestUpdate()
    state["img0"] = capture_left_3d(app, dual_gui)
    QTimer.singleShot(GAP_MS, after_gap)

def after_gap():
    img0 = state["img0"]
    dual_gui.left_gui.requestUpdate()
    img1 = capture_left_3d(app, dual_gui)
    bar1 = index_flex(dual_gui.left_perc_bent)
    link = dual_gui.left_gui.linkages[1].linkages[-1]
    capture_failed = img0 is None or img1 is None or img0.isNull() or img1.isNull()
    pix = 0.0 if capture_failed else pixel_change_fraction(img0, img1)
    result = {
        "skipped": False,
        "capture": "desktop_grabWindow0",
        "capture_failed": capture_failed,
        "left_com": str(SG_main.get_COM_type(left_id)),
        "right_com": str(SG_main.get_COM_type(right_id)),
        "left_perc_bent_delta": abs(bar1 - state["bar0"]),
        "link_x0": state["link_x0"],
        "link_x1": link.end.x(),
        "pixel_frac": pix,
        "grey0": 1.0 if capture_failed else grey_fraction(img0),
        "grey1": 1.0 if capture_failed else grey_fraction(img1),
        "bright0": 0.0 if capture_failed else bright_fraction(img0),
        "bright1": 0.0 if capture_failed else bright_fraction(img1),
        "mean0": (0, 0, 0) if capture_failed else mean_rgb(img0),
        "mean1": (0, 0, 0) if capture_failed else mean_rgb(img1),
        "var0": 0.0 if capture_failed else pixel_variance(img0),
        "var1": 0.0 if capture_failed else pixel_variance(img1),
        "ok_perc_bent": abs(bar1 - state["bar0"]) >= MIN_PERC_BENT_DELTA,
        "ok_link_moved": abs(link.end.x() - state["link_x0"]) > 2.0,
        "ok_hand_visible": (not capture_failed) and looks_like_hand(img0) and looks_like_hand(img1),
        "ok_pose_changed": (not capture_failed) and MIN_PIXEL_CHANGE <= pix <= MAX_PIXEL_CHANGE,
    }
    print(json.dumps(result), flush=True)
    SG_main.exit()

QTimer.singleShot(WARMUP_MS, after_warmup)
app.exec()
'''


def _run_code(code: str, timeout: int = 60, env_extra=None) -> dict:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"runner crashed (code {proc.returncode})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"no JSON in stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


_PLACEHOLDER_RUNNER = r'''
import json, sys, os
sys.path.insert(0, os.path.abspath("."))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from SG_API import SG_GUI as GUI

def mean_rgb(img, step=24):
    if img.isNull() or img.width() == 0:
        return (0.0, 0.0, 0.0)
    r = g = b = n = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            r += c.red(); g += c.green(); b += c.blue(); n += 1
    return (r / n, g / n, b / n)

def grey_fraction(img, step=24):
    if img.isNull():
        return 1.0
    grey = total = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if r > 180 and g > 180 and b > 180 and max(r, g, b) - min(r, g, b) < 12:
                grey += 1
            total += 1
    return grey / max(total, 1)

def bright_fraction(img, threshold=40, step=24):
    if img.isNull():
        return 0.0
    bright = total = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            if (c.red() + c.green() + c.blue()) / 3 > threshold:
                bright += 1
            total += 1
    return bright / max(total, 1)

def pixel_variance(img, step=24):
    if img.isNull() or img.width() == 0:
        return 0.0
    vals = []
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            vals.append((c.red() + c.green() + c.blue()) / 3)
    avg = sum(vals) / len(vals)
    return sum((v - avg) ** 2 for v in vals) / len(vals)

def capture_left_3d(app, dual_gui):
    dual_gui.raise_()
    dual_gui.activateWindow()
    c = dual_gui.left_container
    tl = c.mapToGlobal(c.rect().topLeft())
    screen = app.screenAt(tl) or app.primaryScreen()
    geo = screen.geometry()
    pm = screen.grabWindow(0, tl.x() - geo.x(), tl.y() - geo.y(), c.width(), c.height())
    return pm.toImage()

app = QApplication(sys.argv)
dual_gui = GUI.DualHandGUI()
dual_gui.setWindowFlag(Qt.WindowStaysOnTopHint, True)
dual_gui.show()
dual_gui.raise_()
dual_gui.activateWindow()

def capture_and_quit():
    img = capture_left_3d(app, dual_gui)
    mean = mean_rgb(img)
    result = {
        "mean": mean,
        "var": pixel_variance(img),
        "grey": grey_fraction(img),
        "bright": bright_fraction(img),
        "empty_clear": abs(mean[0] - 10) < 8 and abs(mean[1] - 10) < 8 and abs(mean[2] - 30) < 12 and pixel_variance(img) < 20,
        "ok_hand_visible": (not img.isNull()) and grey_fraction(img) < 0.25 and pixel_variance(img) > 20,
    }
    print(json.dumps(result), flush=True)
    app.quit()

QTimer.singleShot(800, capture_and_quit)
app.exec()
'''


def _run(init_mode: str = "usb") -> dict:
    return _run_code(_RUNNER, timeout=180, env_extra={"SG_VISUAL_INIT": init_mode})


def _assert_visual_motion(test, result):
    test.assertFalse(
        result.get("capture_failed"),
        f"desktop capture did not return frames: {result}",
    )
    test.assertTrue(
        result["ok_hand_visible"],
        f"3D pane is not a rendered hand: {result}",
    )
    test.assertTrue(
        result["ok_perc_bent"] or result.get("ok_link_moved"),
        f"left sim pose did not move (bars and CPU links): {result}",
    )
    test.assertTrue(
        result["ok_pose_changed"],
        f"3D hands did not move between frames: {result}",
    )


@unittest.skipUnless(sys.platform == "win32", "winmm vs thread timer is Windows-only")
class TestHighFreqTimerWithGui(unittest.TestCase):
    """timeSetEvent→Python freezes DualHandGUI Qt3D; GUI path must use a Python thread."""

    def test_gui_import_uses_python_thread_not_winmm_callback(self):
        import SG_API.SG_GUI  # noqa: F401
        from SG_API import SG_timer

        timer_id = SG_timer.create_timer(frequency_hz=100)
        SG_timer.start_timer(timer_id)
        timer = SG_timer._timers[timer_id]
        try:
            self.assertTrue(timer._windows_mm_uses_thread)
            self.assertIsNotNone(timer.timer_thread)
            self.assertTrue(timer.timer_thread.is_alive())
        finally:
            SG_timer.stop_timer(timer_id)


@unittest.skipUnless(sys.platform == "win32", "Qt3D exo display is Windows-only here")
class TestExoDisplayPlaceholderPaint(unittest.TestCase):
    """Regression: skipping _update_display when no pending API data left 3D empty."""

    def test_update_display_applies_placeholder_without_pending(self):
        from PySide6.QtWidgets import QApplication
        from SG_API.SG_GUI import UI_Exo_Display

        app = QApplication.instance() or QApplication([])
        display = UI_Exo_Display()
        display._gui_update_timer.stop()
        self.assertIsNotNone(display.exo_poss)
        self.assertIsNone(display._pending_exo_poss)
        calls = []
        real = display._update_exo_display

        def spy(poss):
            calls.append(True)
            real(poss)

        display._update_exo_display = spy
        display._update_display()
        self.assertTrue(
            calls,
            "placeholder pose must be applied every tick even with no pending API data",
        )
        display.close()
        app.processEvents()


@unittest.skipUnless(sys.platform == "win32", "embedded Qt3D capture needs Windows desktop")
class TestDualHandGUIPlaceholderVisible(unittest.TestCase):
    """No USB. DualHandGUI.show() must paint the 3D exo, not Qt3D clear color (10,10,30)."""

    def test_placeholder_hand_is_visible(self):
        result = _run_code(_PLACEHOLDER_RUNNER, timeout=60)
        self.assertFalse(
            result["empty_clear"],
            f"3D pane is empty Qt3D clear color (mean={result['mean']}, var={result['var']:.1f})",
        )
        self.assertTrue(
            result["ok_hand_visible"],
            f"3D pane is not a rendered hand "
            f"(grey={result['grey']:.2f}, var={result['var']:.1f}, "
            f"mean={result['mean']}, bright={result['bright']:.2f})",
        )


@unittest.skipUnless(sys.platform == "win32", "embedded Qt3D capture needs Windows desktop")
class TestDualHandGUIVisualRefresh(unittest.TestCase):

    def test_two_sim_gloves_3d_moves(self):
        result = _run("two_sim")
        if result.get("skipped"):
            self.skipTest(f"sim init failed: {result.get('reason')}")
        _assert_visual_motion(self, result)

    def test_two_sim_plus_cpp_init_3d_moves(self):
        """C++ USB SDK starts even though both rendered hands are simulated."""
        result = _run("two_sim_cpp")
        if result.get("skipped"):
            self.skipTest(f"cpp+sim init failed: {result.get('reason')}")
        _assert_visual_motion(self, result)

    def test_user_gui_2gloves_sees_hand_in_two_poses(self):
        result = _run("usb")
        if result.get("skipped"):
            self.skipTest(f"no real glove: {result.get('reason')}")
        _assert_visual_motion(self, result)


if __name__ == "__main__":
    unittest.main()
