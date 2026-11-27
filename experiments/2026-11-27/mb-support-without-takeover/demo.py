"""Demo: run both arms on the synthetic fixture and print the report, then show self_reported_ownership as DENY."""

import io
import os
import sys

import ownership

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "fixtures", "main.json")
SELF = os.path.join(HERE, "fixtures", "bad", "self_reported_ownership.json")

if __name__ == "__main__":
    print("Synthetic fixture with planted sessions: shows the mechanism, not evidence of any rate.\n")
    sys.stdout.flush()
    rc_main = ownership.main(["ownership.py", MAIN])
    out, err = io.StringIO(), io.StringIO()
    rc_self = ownership.main(["ownership.py", SELF], out, err)
    print("# self_reported_ownership standalone")
    print("exit: %d" % rc_self)
    print("stdout_empty: %s" % ("yes" if out.getvalue() == "" else "no"))
    print("stderr: %s" % err.getvalue().rstrip("\n"))
    if rc_main == 0 and rc_self == 2 and out.getvalue() == "" and err.getvalue().startswith("DENY self_reported_measure: "):
        sys.exit(0)
    sys.exit(1)
