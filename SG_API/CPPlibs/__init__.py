# CPPlibs __init__.py - Import the RembrandtPySDK module
import os
import sys
import ctypes
import platform
import importlib.util
from typing import Optional

# Add this directory to Python path
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

REMBRANDT_SDK_LOADED = False
REMBRANDT_SDK_LOAD_ERROR = None

def _debug_enabled() -> bool:
    return os.environ.get("REMBRANDT_SDK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

def _load_rembrandt_sdk():
    global REMBRANDT_SDK_LOADED
    global REMBRANDT_SDK_LOAD_ERROR
    try:
        if _debug_enabled():
            print(f"Loading RembrandtPySDK from: {current_dir}")
        import RembrandtPySDK
        # Expose the module under the package namespace to avoid double-loading
        globals()["RembrandtPySDK"] = RembrandtPySDK
        sys.modules.setdefault(f"{__name__}.RembrandtPySDK", RembrandtPySDK)
        # Make it available as if imported with from .RembrandtPySDK import *
        globals().update({name: getattr(RembrandtPySDK, name) for name in dir(RembrandtPySDK) if not name.startswith('_')})
        REMBRANDT_SDK_LOADED = True
        REMBRANDT_SDK_LOAD_ERROR = None
    except ImportError as e:
        # If RembrandtPySDK.pyd is not available, import will fail
        spec = importlib.util.find_spec("RembrandtPySDK")
        expected_pyd = os.path.join(current_dir, "RembrandtPySDK.cp38-win_amd64.pyd")
        REMBRANDT_SDK_LOADED = False
        REMBRANDT_SDK_LOAD_ERROR = f"Could not import RembrandtPySDK: {e}"
        print(f"Warning: {REMBRANDT_SDK_LOAD_ERROR}")
        print(f"Expected path: {expected_pyd}")
        if _debug_enabled():
            print(f"RembrandtPySDK spec: {spec}")
            print(f"CPPlibs dir exists: {os.path.isdir(current_dir)}")
            print(f"CPPlibs contents: {os.listdir(current_dir) if os.path.isdir(current_dir) else 'N/A'}")
            print(f"Python: {sys.version}")
            print(f"Platform: {platform.platform()}")
            print(f"sys.path[0:5]: {sys.path[0:5]}")

        # Basic VC++ runtime presence checks (common missing dependencies on Windows)
        if platform.system() == "Windows":
            system32 = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32")
            vcruntime = os.path.join(system32, "vcruntime140.dll")
            msvcp = os.path.join(system32, "msvcp140.dll")
            if _debug_enabled():
                print(f"vcruntime140.dll present: {os.path.exists(vcruntime)}")
                print(f"msvcp140.dll present: {os.path.exists(msvcp)}")

        _print_missing_windows_deps(expected_pyd)

        # Try a direct CDLL load to surface missing dependency errors
        try:
            ctypes.CDLL(expected_pyd)
        except OSError as dll_error:
            print(f"Direct CDLL load of RembrandtPySDK failed: {dll_error}")


def _load_math_dll():
    dll_name = "libSG_math.dll" if platform.system() == "Windows" else "libSG_math.so"
    dll_path = os.path.join(current_dir, dll_name)

    if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
        # Ensure CPPlibs is in the DLL search path for dependent DLLs
        os.add_dll_directory(current_dir)

    try:
        ctypes.CDLL(dll_path)
    except OSError as e:
        # Preload failure typically means missing DLL, dependencies, or arch mismatch
        print(f"Warning: Could not load {dll_name}: {e}")


def _print_missing_windows_deps(binary_path: str):
    if platform.system() != "Windows":
        return

    try:
        import pefile
    except Exception as exc:
        if _debug_enabled():
            print(f"Dependency scan skipped (install 'pefile'): {exc}")
        return

    if not os.path.isfile(binary_path):
        if _debug_enabled():
            print(f"Dependency scan skipped (file not found): {binary_path}")
        return

    try:
        pe = pefile.PE(binary_path)
        imports = []
        if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            for entry in pe.DIRECTORY_ENTRY_IMPORT:
                try:
                    imports.append(entry.dll.decode("utf-8"))
                except Exception:
                    imports.append(str(entry.dll))
        pe.close()
    except Exception as exc:
        print(f"Dependency scan failed: {exc}")
        return

    search_dirs = [current_dir]
    windir = os.environ.get("WINDIR", "C:\\Windows")
    search_dirs.append(os.path.join(windir, "System32"))
    search_dirs.append(os.path.join(windir, "SysWOW64"))
    search_dirs.extend([p for p in os.environ.get("PATH", "").split(os.pathsep) if p])

    missing = []
    for dll in sorted(set(imports), key=str.lower):
        found = False
        for d in search_dirs:
            if os.path.isfile(os.path.join(d, dll)):
                found = True
                break
        if not found:
            missing.append(dll)

    if missing:
        print("Missing DLLs (from import table): " + ", ".join(missing))
    else:
        if _debug_enabled():
            print("Dependency scan: no missing DLLs found in PATH/System32/CPPlibs.")


def is_rembrandt_sdk_loaded() -> bool:
    return REMBRANDT_SDK_LOADED


def get_rembrandt_sdk_load_error() -> Optional[str]:
    return REMBRANDT_SDK_LOAD_ERROR


_load_rembrandt_sdk()
_load_math_dll()

