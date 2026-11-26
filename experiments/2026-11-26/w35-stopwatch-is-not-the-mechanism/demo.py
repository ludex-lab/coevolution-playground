"""Demo: run both arms on the synthetic fixture and print the report, then show fabricated_counter as DENY."""

import io
import os
import sys

import stopwatch

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
FAB = os.path.join(HERE, "fixtures", "bad", "fabricated_counter.json")

if __name__ == "__main__":
    print("Synthetic fixture with planted versions: shows the mechanism, not evidence of any rate.\n")
    sys.stdout.flush()
    rc_main = stopwatch.main(["stopwatch.py", MAIN])
    out, err = io.StringIO(), io.StringIO()
    rc_fab = stopwatch.main(["stopwatch.py", FAB], out, err)
    print("# fabricated_counter standalone")
    print("exit: %d" % rc_fab)
    print("stdout_empty: %s" % ("yes" if out.getvalue() == "" else "no"))
    print("stderr: %s" % err.getvalue().rstrip("\n"))
    if rc_main == 0 and rc_fab == 2 and out.getvalue() == "" and err.getvalue().startswith("DENY self_reported_measure: "):
        sys.exit(0)
    sys.exit(1)
