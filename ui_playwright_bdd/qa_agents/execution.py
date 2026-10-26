"""Python execution boundary around the existing deterministic Cucumber runner."""
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from .bridge import ROOT, environment


def terminate_tree(child):
    if os.name == "nt":
        result = subprocess.run(["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
                                capture_output=True, timeout=15, check=False,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode and child.poll() is None:
            child.kill()
            raise RuntimeError("Could not confirm termination of runner process tree")
    else:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    child.wait(timeout=15)


def run_tests(run_id, directory, mode, timeout=1800):
    if mode not in {"quick", "full"} or timeout <= 0:
        raise ValueError("Invalid runner mode or timeout")
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Refusing to reuse a populated results directory")
    directory.mkdir(parents=True, exist_ok=True)
    env = environment()
    env.update(QA_RUN_ID=run_id, ALLURE_RESULTS_DIR=str(directory), QA_EXECUTION_MANAGED="true",
               PLANE_SYNC_RESULTS="false", TEST_HEADLESS="true",
               RUNNER_TIMEOUT_MS=str(int(timeout * 1000)))
    # The runner has its own tree deadline. The outer timeout covers startup failures too.
    command = ["node", str(ROOT / "scripts/agents/runner-agent.js"), "smoke" if mode == "quick" else "run"]
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    with (directory.parent / "runner.log").open("w", encoding="utf-8") as log:
        print(f"[Runner] Journal detaille: {directory.parent / 'runner.log'}", flush=True)
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, **options)
        stopped = threading.Event()
        started = time.monotonic()

        def heartbeat():
            while not stopped.wait(15):
                print(f"[Runner] En cours depuis {int(time.monotonic() - started)} s ; "
                      "details dans runner.log (aucun verdict avant la fin).", flush=True)

        monitor = threading.Thread(target=heartbeat, daemon=True)
        monitor.start()
        try:
            code = child.wait(timeout=timeout + 30)
        except subprocess.TimeoutExpired:
            terminate_tree(child)
            return "Runner deadline exceeded"
        except BaseException:
            terminate_tree(child)
            raise
        finally:
            stopped.set()
            monitor.join(timeout=1)
        print(f"[Runner] Termine apres {int(time.monotonic() - started)} s ; code de sortie: {code}", flush=True)
    return None if code == 0 else "Runner exited unsuccessfully"
