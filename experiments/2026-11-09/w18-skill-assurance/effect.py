"""Deterministic effect for the toy ``pack_cart`` skill (see manifest.json).

One crate per sack, plus two spare crates when ``spare`` is true. The cart
goes to the bin named in the input. No I/O, no clock, no randomness, no
state between calls. The input contract caps ``sacks`` at 8, so the output
stays within the declared cart cap of 10 crates.
"""


def pack_cart(payload):
    crates = payload["sacks"] + (2 if payload["spare"] else 0)
    return {"crates": crates, "bin": payload["bin"]}
