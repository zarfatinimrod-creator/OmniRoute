"""Mutation harness (gate B, test-pinning lens). One textual mutant at a time is applied to a worker copy of DEV,
the four relevant test files are run with `python3 -m unittest discover -s tests -p <file>`, and the copy is restored.
Never touches BASE, DEV or the live checkout: it only writes under mutlens2/."""
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # .../scratchpad/mutlens2
PRISTINE = ROOT / "work5"               # my copy of DEV (snapshot 5), never mutated
WORKERS = ROOT / "workers"
SHIM = ROOT / "shim"
TESTS = ["test_news_guards.py", "test_postmortem.py", "test_news_rules.py", "test_news_inputs.py"]


def apply(text: str, edits) -> str:
    lines = text.split("\n")
    # edits are applied bottom-up so line numbers stay those of the pristine file
    for e in sorted(edits, key=lambda e: -e[1]):
        kind = e[0]
        if kind == "sub":
            _, ln, old, new = e
            line = lines[ln - 1]
            if old not in line:
                raise ValueError(f"line {ln}: {old!r} not in {line!r}")
            lines[ln - 1] = line.replace(old, new, 1)
        elif kind == "rep":
            _, a, b, new = e
            lines[a - 1:b] = new.split("\n") if new != "" else []
        elif kind == "move":   # move lines a..b so that they come before line dest (dest < a)
            _, a, b, dest = e
            block = lines[a - 1:b]
            del lines[a - 1:b]
            lines[dest - 1:dest - 1] = block
        elif kind == "txt":    # whole-file unique text replacement (config.json)
            _, _ln, old, new = e
            body = "\n".join(lines)
            if body.count(old) != 1:
                raise ValueError(f"{old!r} occurs {body.count(old)} times")
            lines = body.replace(old, new, 1).split("\n")
        else:
            raise ValueError(kind)
    return "\n".join(lines)


def run_tests(wdir: Path, tests=TESTS, timeout=600):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PATH=f"{SHIM}:{os.environ['PATH']}")
    failed = {}
    for t in tests:
        try:
            cp = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", t], cwd=wdir, env=env,
                                capture_output=True, text=True, timeout=timeout)
            if cp.returncode != 0:
                names = [l.split(" ", 1)[1].strip() for l in cp.stderr.splitlines() if l.startswith(("FAIL: ", "ERROR: "))]
                failed[t] = names or [cp.stderr.strip().splitlines()[-1][:200] if cp.stderr.strip() else "nonzero"]
        except subprocess.TimeoutExpired:
            failed[t] = ["TIMEOUT"]
    return failed


def one(m, wq: Queue, tests=TESTS):
    wdir = wq.get()
    try:
        target = wdir / m["file"]
        src = (PRISTINE / m["file"]).read_text(encoding="utf-8")
        try:
            mutated = apply(src, m["edits"])
        except ValueError as e:
            return {**m, "status": "BADSPEC", "detail": str(e)}
        if mutated == src:
            return {**m, "status": "BADSPEC", "detail": "no change"}
        target.write_text(mutated, encoding="utf-8")
        try:
            if m["file"].endswith(".py"):
                try:
                    compile(mutated, str(target), "exec")
                except SyntaxError as e:
                    return {**m, "status": "INVALID", "detail": str(e)[:300]}
            elif m["file"].endswith(".json"):
                json.loads(mutated)
            failed = run_tests(wdir, tests)
        finally:
            target.write_text(src, encoding="utf-8")
        return {**m, "status": "KILLED" if failed else "SURVIVED", "failed": failed}
    finally:
        wq.put(wdir)


def main():
    sys.path.insert(0, str(HERE))
    import mutants
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    tests = TESTS if len(sys.argv) <= 3 else sys.argv[3].split(",")
    out_path = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "results.json")
    n = 6
    WORKERS.mkdir(exist_ok=True)
    wq = Queue()
    for i in range(n):
        w = WORKERS / f"w{i}"
        if w.exists():
            shutil.rmtree(w)
        shutil.copytree(PRISTINE, w, ignore=shutil.ignore_patterns("__pycache__", ".cache"))
        for extra in filter(None, os.environ.get("EXTRA_TESTS", "").split(",")):   # proposed tests, into the worker only
            shutil.copy(extra, w / "tests" / Path(extra).name)
        wq.put(w)
    base = run_tests(WORKERS / "w0", tests)
    if base:
        print("BASELINE NOT GREEN:", base)
        sys.exit(2)
    ms = [m for m in mutants.MUTANTS if only is None or m["id"] in only]
    ids = [m["id"] for m in ms]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    with ThreadPoolExecutor(n) as ex:
        res = list(ex.map(lambda m: one(m, wq, tests), ms))
    for r in res:
        r["edits"] = [list(e) for e in r["edits"]]
    out_path.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    by = {}
    for r in res:
        by.setdefault(r["status"], []).append(r["id"])
    for k, v in by.items():
        print(k, len(v), " ".join(v) if k != "KILLED" else "")
    for r in res:
        if r["status"] in ("BADSPEC", "INVALID"):
            print(r["id"], r["status"], r.get("detail"))


if __name__ == "__main__":
    main()
