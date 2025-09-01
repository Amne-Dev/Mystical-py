# launcher_debug.py
import ctypes, os, subprocess, platform, shutil, json
from pathlib import Path

def debug_print(msg):
    print("[diag]", msg)

def read_protocol_handler(protocol: str):
    try:
        import winreg
        key_path = fr"{protocol}\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as k:
            val, _ = winreg.QueryValueEx(k, None)
            return val
    except Exception as e:
        return f"<error reading registry: {e}>"

def shellexecutew_open(target: str, parameters: str = None):
    """
    If parameters is None, ShellExecuteW will be called with lpFile=target.
    If parameters provided, call ShellExecuteW with lpFile=target and lpParameters=parameters.
    """
    try:
        if parameters is None:
            res = ctypes.windll.shell32.ShellExecuteW(None, "open", target, None, None, 1)
            debug_print(f"ShellExecuteW(target={target!r}) returned: {res}")
            return int(res) > 32
        else:
            res = ctypes.windll.shell32.ShellExecuteW(None, "open", str(target), str(parameters), None, 1)
            debug_print(f"ShellExecuteW(exe={target!r}, params={parameters!r}) returned: {res}")
            return int(res) > 32
    except Exception as e:
        debug_print(f"ShellExecuteW exception: {e}")
        return False

def try_direct_spawn(exe_path: Path, uri: str):
    try:
        debug_print(f"subprocess.Popen: [{exe_path}, {uri}]")
        p = subprocess.Popen([str(exe_path), uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        debug_print(f"subprocess.Popen error: {e}")
        return False

def find_epic_exe_candidates():
    env = os.environ
    possible = [
        Path(env.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
        Path(env.get("PROGRAMFILES", "C:\\Program Files")) / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
    ]
    found = [p for p in possible if p.exists()]
    debug_print(f"Epic exe candidates: {found}")
    return found

def main_test(app_id):
    protocol = "com.epicgames.launcher"
    debug_print(f"Reading registry handler for {protocol}")
    handler = read_protocol_handler(protocol)
    debug_print(f"HKEY_CLASSES_ROOT\\{protocol}\\shell\\open\\command -> {handler}")

    # Build strict URI:
    uri = f"com.epicgames.launcher://apps/{app_id}?action=launch&silent=true"
    debug_print(f"Using URI: {uri}")

    # 1) Try ShellExecuteW with the URI (the "normal" approach)
    debug_print("Attempt 1: ShellExecuteW(target=URI)")
    ok = shellexecutew_open(uri)
    debug_print(f"Attempt 1 result: {ok}")
    if ok:
        debug_print("Attempt 1 succeeded. If game didn't start, inspect the registry handler printed above.")
        return

    # 2) If ShellExecuteW on the uri didn't work, try extracting exe from registry string if possible
    debug_print("Attempt 2: Try to parse EXE path from registry handler and call ShellExecuteW(EXE, URI)")
    # Try to extract an exe path from the registry handler string (looking for first quoted path)
    import re
    m = re.search(r'"([^"]+\.exe)"', str(handler))
    if m:
        exe_path = Path(m.group(1))
        debug_print(f"Parsed exe path from registry: {exe_path}")
        if exe_path.exists():
            ok2 = shellexecutew_open(exe_path, uri)
            debug_print(f"Attempt 2 result: {ok2}")
            if ok2:
                debug_print("Attempt 2 succeeded (ShellExecuteW called with EXE and URI).")
                return
            debug_print("Attempt 2 failed; will try direct subprocess spawn.")
        else:
            debug_print("Parsed exe path does not exist on disk.")
    else:
        debug_print("Could not parse exe path from registry handler string.")

    # 3) If we have candidate EXE paths, try launching the exe directly with the URI as argument
    debug_print("Attempt 3: Direct spawn EXE with uri argument")
    candidates = find_epic_exe_candidates()
    for exe in candidates:
        if try_direct_spawn(exe, uri):
            debug_print(f"Attempt 3 succeeded launching {exe} with URI argument.")
            return

    # 4) Last resort use generic opener (but you said avoid os.startfile because it causes the browser fallback)
    debug_print("Attempt 4: generic opener (ShellExecuteW fallback + os.startfile + webbrowser)")
    try:
        # use ShellExecuteW on the URI again but explicitly step through; fallback to os.startfile only after shell failed
        res = ctypes.windll.shell32.ShellExecuteW(None, "open", uri, None, None, 1)
        debug_print(f"Second ShellExecuteW returned {res}")
    except Exception as e:
        debug_print(f"Second ShellExecuteW exception: {e}")
    try:
        os.startfile(uri)
        debug_print("os.startfile(uri) called (may cause wrong browser fallback).")
    except Exception as e:
        debug_print(f"os.startfile failed: {e}")

if __name__ == "__main__":
    # change the ID below to the Epic AppID you want to test
    test_app_id = "530145df28a24424923f5828cc9031a1"
    main_test(test_app_id)
