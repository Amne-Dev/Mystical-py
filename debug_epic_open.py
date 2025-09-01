# debug_epic_open.py
import platform
import ctypes
from pathlib import Path
import subprocess
import sys

# read registry value for the protocol (Windows-only)
def read_protocol_command(protocol: str):
    try:
        import winreg
    except Exception:
        print("[diag] winreg not available on this platform")
        return None
    key_path = protocol + r"\shell\open\command"
    try:
        k = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path)
        val, _ = winreg.QueryValueEx(k, None)  # (default) value
        winreg.CloseKey(k)
        return val
    except FileNotFoundError:
        return None
    except Exception as e:
        return f"<error reading key: {e}>"

def shellexecute_open(uri: str):
    # Use ShellExecuteW via ctypes (no os.startfile, no fallback)
    ShellExecuteW = ctypes.windll.shell32.ShellExecuteW
    # hwnd=0, operation="open", file=uri, params=None, dir=None, show=1
    res = ShellExecuteW(None, "open", uri, None, None, 1)
    try:
        ival = int(res)
    except Exception:
        ival = -1
    return ival

if __name__ == "__main__":
    if platform.system().lower() != "windows":
        print("[diag] This diagnostic is for Windows only.")
        sys.exit(0)

    proto = "com.epicgames.launcher"
    print("[diag] Reading registry for protocol:", proto)
    cmd = read_protocol_command(proto)
    print("[diag] HKCR\\%s\\shell\\open\\command -> %r" % (proto, cmd))

    # Build the exact URI (your requested format)
    example_id = "530145df28a24424923f5828cc9031a1"   # replace with real AppID
    uri = f"com.epicgames.launcher://apps/{example_id}?action=launch&silent=true"
    print("[diag] Attempting ShellExecuteW open of URI:", uri)

    result = shellexecute_open(uri)
    print("[diag] ShellExecuteW returned:", result)
    if result > 32:
        print("[diag] ShellExecuteW indicates success (>32).")
    else:
        print("[diag] ShellExecuteW indicates failure (<=32).")
