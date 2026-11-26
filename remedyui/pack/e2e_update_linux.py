"""A real self-update of the Linux program, run inside Linux (WSL) on a virtual display.
Expects the current program and a newer throwaway one, the newer with its .sig beside it
(signed with the update key), and works on copies in a temporary folder with its own HOME.

  python3 pack/e2e_update_linux.py <old program> <newer program>
"""
import base64, functools, hashlib, http.server, json, os, pathlib, shutil, subprocess, sys, tempfile, threading, time

PORT = 18766
old, new = map(pathlib.Path, sys.argv[1:3])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def running(program):
    """Process ids of this program only (matched by its own path)."""
    found = []
    for entry in pathlib.Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                if os.readlink(entry / "exe").removesuffix(" (deleted)") in (str(program), str(program.with_suffix(".old"))):
                    found.append(int(entry.name))
            except OSError:
                pass
    return found


def wait(what, check, seconds):
    end = time.time() + seconds
    while time.time() < end:
        got = check()
        if got:
            return got
        time.sleep(1)
    raise AssertionError(f"never happened: {what}")


with tempfile.TemporaryDirectory() as folder:
    folder = pathlib.Path(folder)
    (folder / "bin").mkdir()
    program = folder / "bin" / "RemedyPDF"
    shutil.copy(old, program)
    program.chmod(0o755)
    serve = folder / "serve"
    serve.mkdir()
    shutil.copy(new, serve / new.name)
    entry = {"url": f"http://127.0.0.1:{PORT}/{new.name}",
             "signature": base64.b64encode(pathlib.Path(str(new) + ".sig").read_bytes()).decode(),
             "sha256": digest(new)}
    (serve / "latest.json").write_text(json.dumps({"version": new.name.split("_")[1],
                                                   "platforms": {"linux-x86_64": entry}}))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(serve))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    home = folder / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), XDG_CACHE_HOME=str(home / ".cache"),
               XDG_DATA_HOME=str(home / ".local/share"), XDG_CONFIG_HOME=str(home / ".config"),
               REMEDYPDF_UPDATE_FEED=f"http://127.0.0.1:{PORT}/latest.json")
    env.pop("WAYLAND_DISPLAY", None)
    display = subprocess.Popen(["Xvfb", ":97", "-screen", "0", "1280x900x24"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        env["DISPLAY"] = ":97"
        first = subprocess.Popen([str(program), "--install-update"], env=env)
        wait("the program is replaced", lambda: digest(program) == digest(new), 120)
        wait("the old copy exits", lambda: first.poll() is not None, 30)
        assert first.returncode == 0, f"the old copy exited {first.returncode}"
        again = wait("the new version starts", lambda: [p for p in running(program) if p != first.pid], 30)
        time.sleep(8)
        assert running(program) == again, f"expected one running copy that stays up: {running(program)}"
        assert os.access(program, os.X_OK)
        print("ok   the Linux program updated itself with no clicks and restarted")
    finally:
        for pid in running(program):
            os.kill(pid, 9)
        display.kill()
        server.shutdown()
