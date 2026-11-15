"""ODD+LLM-style documentation hygiene checklist (method sketch, stdlib only).

Reads checklist.json (five blocks A-E) and checks synthetic model
descriptions against it. Public verbs: hold, detect, report, compare, flag.
Nothing here grades quality; it only says which items are written down.

Description shape:
    {"id": "<name>", "blocks": {"A": {"carried_state": "...", ...}, ...}}

Placeholder rule (also in checklist.json): a field is documented only if
its value is a number, a boolean, a non-empty list/object, or a string that
is non-empty after trimming and is not a placeholder word ("TBD",
"default", "n/a", ...; case-insensitive, trailing dots/spaces ignored).
A missing key or null is "missing"; anything else that fails is
"placeholder". Both count as not documented.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK_IDS = ("A", "B", "C", "D", "E")


def _load():
    with open(os.path.join(_HERE, "checklist.json"), encoding="utf-8") as fh:
        return json.load(fh)


CHECKLIST = _load()
PLACEHOLDERS = frozenset(CHECKLIST["placeholders"])


def _is_placeholder(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    if isinstance(value, str):
        word = value.strip().rstrip(". ").casefold()
        return word == "" or word in PLACEHOLDERS
    return True


def hold(description):
    """Structural problems that stop a description from being checked.

    Returns a list of strings; an empty list means it can be checked.
    """
    if not isinstance(description, dict):
        return ["description is not an object"]
    problems = []
    if not isinstance(description.get("id"), str) or not description["id"].strip():
        problems.append("no id")
    if not isinstance(description.get("blocks"), dict):
        problems.append("no blocks object")
    else:
        for key, body in sorted(description["blocks"].items()):
            if not isinstance(body, dict):
                problems.append("block %s is not an object" % key)
    return problems


def detect(description):
    """Per-block documented / missing / placeholder item ids.

    Returns None when hold() reports a problem. Blocks or fields the
    checklist does not declare are listed, never dropped silently.
    """
    if hold(description):
        return None
    given = description["blocks"]
    out = {"id": description["id"], "blocks": {},
           "undeclared_blocks": sorted(k for k in given if k not in BLOCK_IDS),
           "undeclared_fields": {}}
    for block in CHECKLIST["blocks"]:
        body = given.get(block["id"], {})
        row = {"name": block["name"], "documented": [], "missing": [],
               "placeholder": [], "required_gaps": []}
        for item in block["items"]:
            if item["field"] not in body or body[item["field"]] is None:
                state = "missing"
            elif _is_placeholder(body[item["field"]]):
                state = "placeholder"
            else:
                state = "documented"
            row[state].append(item["id"])
            if state != "documented" and item["required"]:
                row["required_gaps"].append(item["id"])
        known = {item["field"] for item in block["items"]}
        extra = sorted(k for k in body if k not in known)
        if extra:
            out["undeclared_fields"][block["id"]] = extra
        out["blocks"][block["id"]] = row
    return out


def report(descriptions):
    """Per-description, per-block coverage counts as "n/m" strings.

    There is deliberately no overall number: five block counts side by
    side, plus the undeclared blocks, plus held descriptions.
    """
    rows = []
    for d in descriptions:
        problems = hold(d)
        if problems:
            rows.append({"id": d.get("id") if isinstance(d, dict) else None,
                         "held": problems})
            continue
        found = detect(d)
        blocks = {}
        for block in CHECKLIST["blocks"]:
            r = found["blocks"][block["id"]]
            n_items = len(block["items"])
            n_req = sum(1 for i in block["items"] if i["required"])
            blocks[block["id"]] = {
                "name": block["name"],
                "documented": "%d/%d" % (len(r["documented"]), n_items),
                "required_documented": "%d/%d" % (n_req - len(r["required_gaps"]), n_req),
            }
        rows.append({"id": found["id"], "blocks": blocks,
                     "undeclared_blocks": found["undeclared_blocks"]})
    return rows


def compare(a, b):
    """Item ids one description documents and the other does not, per block."""
    da, db = detect(a), detect(b)
    if da is None or db is None:
        return None
    only_a, only_b = {}, {}
    for key in BLOCK_IDS:
        sa = set(da["blocks"][key]["documented"])
        sb = set(db["blocks"][key]["documented"])
        if sa - sb:
            only_a[key] = sorted(sa - sb)
        if sb - sa:
            only_b[key] = sorted(sb - sa)
    return {"a": da["id"], "b": db["id"], "only_in_a": only_a, "only_in_b": only_b}


def flag(descriptions):
    """Descriptions with a required gap, an undeclared block, or a hold.

    Each entry names the blocks involved so a gap in one block is not
    smeared over the whole description.
    """
    out = []
    for d in descriptions:
        problems = hold(d)
        if problems:
            out.append({"id": d.get("id") if isinstance(d, dict) else None,
                        "held": problems})
            continue
        found = detect(d)
        gaps = {k: r["required_gaps"] for k, r in found["blocks"].items() if r["required_gaps"]}
        if gaps or found["undeclared_blocks"]:
            out.append({"id": found["id"], "required_gaps": gaps,
                        "undeclared_blocks": found["undeclared_blocks"]})
    return out
