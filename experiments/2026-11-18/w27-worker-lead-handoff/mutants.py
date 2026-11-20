"""Mutation self-check for w27-worker-lead-handoff (stdlib only).

Each mutant replaces one exact source fragment (which must occur exactly once) in a copy of this
folder, then runs the unittest suite with the same Python interpreter. A mutant is killed when the
suite fails. Run: python3 -B mutants.py   (exit 0 only when every mutant is killed)
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
COPY = ("handoff.py", "test_handoff.py", "demo.py", "mutants.py", "README.md", "evidence.json", "fixtures")
M = "handoff.py"

MUTANTS = [
    # packet rule
    ("packet", r'    ordered = sorted(context, key=lambda d: d["id"], reverse=packet["rule"] == "id_desc")', r'    ordered = sorted(context, key=lambda d: d["id"])'),
    ("packet", r'    ordered = sorted(context, key=lambda d: d["id"], reverse=packet["rule"] == "id_desc")', r'    ordered = sorted(context, key=lambda d: d["id"], reverse=True)'),
    ("packet", r'    ordered = sorted(context, key=lambda d: d["id"], reverse=packet["rule"] == "id_desc")', r'    ordered = list(context)'),
    ("packet", r'    return [item(d) for d in ordered[:packet["budget"]]]', r'    return [item(d) for d in ordered[:packet["budget"] + 1]]'),
    ("packet", r'    return [item(d) for d in ordered[:packet["budget"]]]', r'    return [item(d) for d in ordered[:max(packet["budget"] - 1, 1)]]'),
    ("packet", r'    return [item(d) for d in ordered[:packet["budget"]]]', r'    return [item(d) for d in ordered]'),
    ("packet", r'    return [item(d) for d in ordered[:packet["budget"]]]', r'    return [item(d) for d in ordered[-packet["budget"]:]]'),
    ("item", r'    return {"doc": doc["id"], "entity": doc["entity"], "attribute": doc["attribute"], "value": doc["value"]}', r'    return dict(doc, doc=doc["id"])'),
    ("item", r'    return {"doc": doc["id"], "entity": doc["entity"], "attribute": doc["attribute"], "value": doc["value"]}', r'    return {"doc": doc["id"], "entity": doc["entity"], "attribute": doc["attribute"], "value": doc["value"], "claims": 2}'),
    # lead detector
    ("lead", r'    return {"detected": len(values) > 1, "values": values}', r'    return {"detected": len(values) > 0, "values": values}'),
    ("lead", r'    return {"detected": len(values) > 1, "values": values}', r'    return {"detected": len(values) > 2, "values": values}'),
    ("lead", r'    return {"detected": len(values) > 1, "values": values}', r'    return {"detected": True, "values": values}'),
    ("lead", r'    return {"detected": len(values) > 1, "values": values}', r'    return {"detected": len(values) > 1, "values": values, "winner": values[0] if values else None}'),
    ("lead", r'    values = sorted({i["value"] for i in evidence if i["entity"] == entity and i["attribute"] == attribute})', r'    values = sorted({i["value"] for i in evidence})'),
    ("lead", r'    values = sorted({i["value"] for i in evidence if i["entity"] == entity and i["attribute"] == attribute})', r'    values = sorted({i["value"] for i in evidence if i["entity"] == entity})'),
    ("lead", r'    values = sorted({i["value"] for i in evidence if i["entity"] == entity and i["attribute"] == attribute})', r'    values = sorted({i["value"] for i in evidence if i["attribute"] == attribute})'),
    ("lead", r'    values = sorted({i["value"] for i in evidence if i["entity"] == entity and i["attribute"] == attribute})', r'    values = sorted([i["value"] for i in evidence if i["entity"] == entity and i["attribute"] == attribute])'),
    # verdict
    ("verdict", r'    if not both_retrieved:', r'    if False:'),
    ("verdict", r'        return "FAIL", "not_retrieved"', r'        return "PASS", "not_retrieved"'),
    ("verdict", r'    if detected:', r'    if True:'),
    ("verdict", r'    if detected:', r'    if not detected:'),
    ("verdict", r'    return "FAIL", "handoff_failure"', r'    return "PASS", "handoff_failure"'),
    ("verdict", r'    return "FAIL", "handoff_failure"', r'    return "FAIL", "detected"'),
    ("verdict", r'    return "PASS", "detected"', r'    return "PASS", "handoff_failure"'),
    # expiry
    ("expiry", r'    if packet is None:@@        return "missing_packet"', r'    if packet is None:@@        return None'),
    ("expiry", r'    if packet["expires_at"] < now:', r'    if packet["expires_at"] <= now:'),
    ("expiry", r'    if packet["expires_at"] < now:', r'    if packet["expires_at"] > now:'),
    ("expiry", r'    if packet["expires_at"] < now:', r'    if False:'),
    ("expiry", r'        return "expired_packet"', r'        return "missing_packet"'),
    ("expiry", r'        row["verdict"], row["reason"], row["denied_workers"] = "DENY", denied[0][1], [w for w, _ in denied]', r'        row["verdict"], row["reason"], row["denied_workers"] = "FAIL", denied[0][1], [w for w, _ in denied]'),
    ("expiry", r'        row["verdict"], row["reason"], row["denied_workers"] = "DENY", denied[0][1], [w for w, _ in denied]', r'        row["verdict"], row["reason"], row["denied_workers"] = "DENY", denied[0][1], [denied[0][0]]'),
    ("expiry", r'    denied = [(w, s) for w, s in states if s is not None]', r'    denied = [(w, s) for w, s in states if s == "missing_packet"]'),
    ("expiry", r'    denied = [(w, s) for w, s in states if s is not None]', r'    denied = [(w, s) for w, s in states if s == "expired_packet"]'),
    ("expiry", r'    states = [(w, packet_state(case["packets"][w], now)) for w in sorted(case["packets"])]', r'    states = [(w, packet_state(case["packets"][w], 0)) for w in sorted(case["packets"])]'),
    ("expiry", r'ON_EXPIRY = "DENY"', r'ON_EXPIRY = "HOLD"'),
    # profiler
    ("profile", r'    both_retrieved = all(c in retrieved for c in case["claims"])', r'    both_retrieved = any(c in retrieved for c in case["claims"])'),
    ("profile", r'    both_retrieved = all(c in retrieved for c in case["claims"])', r'    both_retrieved = True'),
    ("profile", r'    both_retrieved = all(c in retrieved for c in case["claims"])', r'    both_retrieved = False'),
    ("profile", r'    retrieved = {d["id"] for docs_ in context.values() for d in docs_}', r'    retrieved = {d["id"] for d in context.get("w_a", [])}'),
    ("profile", r'    if case["layout"] == "single_agent":@@        evidence', r'    if False:@@        evidence'),
    ("profile", r'        evidence = [i for w in sorted(context) for i in write_packet(context[w], case["packets"][w])]', r'        evidence = [item(d) for w in sorted(context) for d in context[w]]'),
    ("profile", r'        evidence = [i for w in sorted(context) for i in write_packet(context[w], case["packets"][w])]', r'        evidence = [i for w in sorted(context)[:1] for i in write_packet(context[w], case["packets"][w])]'),
    ("profile", r'    row["lead_detected"] = found["detected"]', r'    row["lead_detected"] = both_retrieved'),
    ("profile", r'    row["dropped_claims"] = [c for c in case["claims"] if c in retrieved and c not in reported]', r'    row["dropped_claims"] = []'),
    ("profile", r'    row["reported_claims"] = [c for c in case["claims"] if c in reported]', r'    row["reported_claims"] = list(case["claims"])'),
    ("profile", r'    row["lead_values"] = found["values"]', r'    row["lead_values"] = []'),
    ("profile", r'    context = {w: [docs[i] for i in ids] for w, ids in case["assign"].items()}', r'    context = {w: [docs[i] for i in ids if i in case["claims"]] for w, ids in case["assign"].items()}'),
    # totals
    ("totals", r'            "handoff_failure": sum(1 for r in mine if r["reason"] == "handoff_failure"),', r'            "handoff_failure": sum(1 for r in mine if r["verdict"] == "FAIL"),'),
    ("totals", r'            "lead_detected": sum(1 for r in mine if r["lead_detected"]),', r'            "lead_detected": sum(1 for r in mine if r["both_retrieved"]),'),
    ("totals", r'            "pass": sum(1 for r in mine if r["verdict"] == "PASS"),', r'            "pass": sum(1 for r in mine if r["both_retrieved"]),'),
    # layout shape
    ("layout", r'    ok = {"single_agent": len(holds) == 1 and sizes == [2],', r'    ok = {"single_agent": len(holds) == 1,'),
    ("layout", r'          "delegated_same": len(holds) == 2 and sizes == [0, 2],', r'          "delegated_same": len(holds) == 2,'),
    ("layout", r'          "delegated_split": len(holds) == 2 and sizes == [1, 1]}[layout]', r'          "delegated_split": len(holds) == 2 and sizes != [0, 2]}[layout]'),
    ("layout", r'    if any(c not in used for c in claims):', r'    if False:'),
    ("layout", r'    if case["layout"] == "single_agent":@@        if case["packets"]:', r'    if case["layout"] == "single_agent":@@        if False:'),
    ("layout", r'        missing = [w for w in sorted(assign) if w not in case["packets"]]', r'        missing = []'),
    ("layout", r'            if worker not in assign:', r'            if False:'),
    # validate
    ("validate", r'    if len(claims) != 2:', r'    if len(claims) < 2:'),
    ("validate", r'    if docs[claims[0]]["value"] == docs[claims[1]]["value"]:', r'    if False:'),
    ("validate", r'        if docs[claim]["entity"] != case["entity"] or docs[claim]["attribute"] != case["attribute"]:', r'        if docs[claim]["entity"] != case["entity"]:'),
    ("validate", r'            if doc_id not in claims and doc["entity"] == case["entity"] and doc["attribute"] == case["attribute"]:', r'            if False:'),
    ("validate", r'            if doc_id in used:', r'            if False:'),
    ("validate", r'        if worker not in workers:', r'        if False:'),
    ("validate", r'    if case["id"] in seen:', r'    if False:'),
    ("validate", r'    if type(case["layout"]) is not str or case["layout"] not in LAYOUTS:', r'    if False:'),
    ("validate", r'    if type(packet["rule"]) is not str or packet["rule"] not in RULES:', r'    if False:'),
    ("validate", r'    if type(packet["budget"]) is not int or not 1 <= packet["budget"] <= MAX_BUDGET:', r'    if not 1 <= packet["budget"] <= MAX_BUDGET:'),
    ("validate", r'    if type(packet["budget"]) is not int or not 1 <= packet["budget"] <= MAX_BUDGET:', r'    if type(packet["budget"]) is not int or not 0 <= packet["budget"] <= MAX_BUDGET:'),
    ("validate", r'    if packet["expires_at"] < packet["issued_at"]:', r'    if False:'),
    ("validate", r'    if packet["issued_at"] > now:', r'    if False:'),
    ("validate", r'    if type(value) is not int or not 0 <= value <= MAX_TIME:', r'    if not 0 <= value <= MAX_TIME:'),
    ("validate", r'    if root["on_expiry"] != ON_EXPIRY:', r'    if False:'),
    ("validate", r'    if type(root["fixture_version"]) is not int or root["fixture_version"] != FIXTURE_VERSION:', r'    if root["fixture_version"] != FIXTURE_VERSION:'),
    ("validate", r'    if len(set(workers)) != len(workers):', r'    if False:'),
    ("validate", r'        if doc["id"] in docs:', r'        if False:'),
    ("validate", r'    if unknown:@@        raise Deny("unknown_key"', r'    if False:@@        raise Deny("unknown_key"'),
    ("validate", r'    if missing:@@        raise Deny("missing_key"', r'    if False:@@        raise Deny("missing_key"'),
    ("validate", r'    if len(set(ids)) != len(ids):', r'    if False:'),
    ("validate", r'    if not cases:', r'    if False:'),
    # text rule (shared with the region experiment) and the both_retrieved total
    ("text", r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', r'BAD_CATEGORIES = ("Cf", "Cs", "Co", "Zl", "Zp")'),
    ("text", r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', r'BAD_CATEGORIES = ("Cc", "Cs", "Co", "Zl", "Zp")'),
    ("text", r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', r'BAD_CATEGORIES = ("Cc", "Cf", "Co", "Zl", "Zp")'),
    ("text", r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Zl", "Zp")'),
    ("text", r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zp")'),
    ("text", r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")', r'BAD_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl")'),
    ("text", r'(cat == "Zs" and ch != " ")', r'False'),
    ("text", r'BLANK_LOOKALIKES = ("\u3164", "\u2800")', r'BLANK_LOOKALIKES = ("\u3164",)'),
    ("text", r'BLANK_LOOKALIKES = ("\u3164", "\u2800")', r'BLANK_LOOKALIKES = ("\u2800",)'),
    ("text", r' or ch in BLANK_LOOKALIKES:', r':'),
    ("totals", r'"both_retrieved": sum(1 for r in mine if r["both_retrieved"]),', r'"both_retrieved": sum(1 for r in mine if r["both_retrieved"] and r["verdict"] != "DENY"),'),
    # strict JSON and CLI
    ("json", r'        if key in out:', r'        if False:'),
    ("json", r'                          parse_constant=_reject_constant, parse_float=_parse_float)', r'                          parse_float=_parse_float)'),
    ("json", r'                          parse_constant=_reject_constant, parse_float=_parse_float)', r'                          parse_constant=_reject_constant)'),
    ("json", r'    if not math.isfinite(value):', r'    if False:'),
    ("json", r'    if text.startswith("\ufeff"):', r'    if False:'),
    ("cli", r'        if len(argv) != 1 or argv[0].startswith("-"):', r'        if len(argv) != 1:'),
    ("cli", r'        if len(argv) != 1 or argv[0].startswith("-"):', r'        if len(argv) < 1:'),
    ("cli", r'        return 2', r'        return 1'),
    ("cli", r'    return 2 if any(r["verdict"] == "DENY" for r in report["rows"]) else 0', r'    return 0'),
    ("cli", r'        err.write("DENY %s: %s\n" % (exc.code, exc.detail))', r'        out.write("DENY %s: %s\n" % (exc.code, exc.detail))'),
    ("cli", r'    except (OSError, UnicodeDecodeError) as exc:', r'    except OSError as exc:'),
]


def run_suite(folder):
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "test_handoff"], cwd=folder,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    return res.returncode


def main():
    base = tempfile.mkdtemp(prefix="w27-handoff-mutants-")
    try:
        clean = os.path.join(base, "clean")
        os.mkdir(clean)
        for name in COPY:
            src = os.path.join(HERE, name)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(clean, name))
            else:
                shutil.copy2(src, os.path.join(clean, name))
        if run_suite(clean) != 0:
            print("baseline suite fails; no mutants run")
            return 1
        with open(os.path.join(clean, M), encoding="utf-8") as handle:
            source = handle.read()
        survivors = 0
        for idx, (group, old, new) in enumerate(MUTANTS, 1):
            old = old.replace("@@", "\n")
            if source.count(old) != 1:
                print("mutant %02d %-9s fragment occurs %d times" % (idx, group, source.count(old)))
                return 1
            folder = os.path.join(base, "m%02d" % idx)
            shutil.copytree(clean, folder)
            with open(os.path.join(folder, M), "w", encoding="utf-8") as handle:
                handle.write(source.replace(old, new.replace("@@", "\n")))
            killed = run_suite(folder) != 0
            survivors += 0 if killed else 1
            print("mutant %02d %-9s %s" % (idx, group, "killed" if killed else "SURVIVED"))
            shutil.rmtree(folder)
        total = len(MUTANTS)
        print("%d/%d killed" % (total - survivors, total))
        return 0 if survivors == 0 else 1
    finally:
        shutil.rmtree(base)


if __name__ == "__main__":
    sys.exit(main())
