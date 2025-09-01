# launcher_debug_direct.py
import ctypes, os, subprocess, re
from pathlib import Path

def debug(msg): print("[diag]", msg)

def read_handler(protocol="com.epicgames.launcher"):
    try:
        import winreg
        key = fr"{protocol}\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key) as k:
            val, _ = winreg.QueryValueEx(k, None)
            return val
    except Exception as e:
        return f"<err read reg: {e}>"

def shellexec_exe_with_uri(exe, uri):
    try:
        res = ctypes.windll.shell32.ShellExecuteW(None, "open", str(exe), str(uri), None, 1)
        debug(f"ShellExecuteW(exe={exe!r}, uri={uri!r}) returned: {res}")
        return int(res) > 32
    except Exception as e:
        debug(f"ShellExecuteW(exe,uri) error: {e}")
        return False

def spawn_exe_with_uri(exe, uri):
    try:
        debug(f"spawn: {[str(exe), uri]}")
        subprocess.Popen([str(exe), uri])
        return True
    except Exception as e:
        debug(f"spawn error: {e}")
        return False

if __name__ == "__main__":
    app_id = "530145df28a24424923f5828cc9031a1"   # change if needed
    uri = f"com.epicgames.launcher://apps/{app_id}?action=launch&silent=true"
    debug("Reading registry handler...")
    handler = read_handler()
    debug(f"Handler -> {handler}")
    # extract exe path
    m = re.search(r'"([^"]+\.exe)"', str(handler))
    exe_path = None
    if m:
        exe_path = Path(m.group(1))
        debug(f"Parsed exe: {exe_path} (exists={exe_path.exists()})")
    else:
        debug("Couldn't parse exe path from registry handler.")

    if exe_path and exe_path.exists():
        debug("Try ShellExecuteW with EXE + URI")
        ok = shellexec_exe_with_uri(exe_path, uri)
        debug(f"result: {ok}")
        if not ok:
            debug("Try subprocess spawn with EXE + URI")
            ok2 = spawn_exe_with_uri(exe_path, uri)
            debug(f"spawn result: {ok2}")
    else:
        debug("No local EXE path found. You can try specifying EXE manually.")
