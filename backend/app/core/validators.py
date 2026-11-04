"""Validators for Australian business identifiers, shared by sign-up, settings and the record engine."""

from __future__ import annotations

import re

_ABN_WEIGHTS = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
_ACN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 1)


def digits(value: str) -> str:
    return re.sub(r"[\s-]", "", value or "")


def is_valid_abn(value: str) -> bool:
    """ABN checksum (ATO): subtract 1 from the first digit, weight, sum; valid when divisible by 89."""
    abn = digits(value)
    if not re.fullmatch(r"\d{11}", abn) or abn[0] == "0":
        return False
    nums = [int(c) for c in abn]
    nums[0] -= 1
    return sum(n * w for n, w in zip(nums, _ABN_WEIGHTS, strict=True)) % 89 == 0


def is_valid_acn(value: str) -> bool:
    """ACN check digit (ASIC)."""
    acn = digits(value)
    if not re.fullmatch(r"\d{9}", acn):
        return False
    total = sum(int(c) * w for c, w in zip(acn[:8], _ACN_WEIGHTS, strict=True))
    return (10 - total % 10) % 10 == int(acn[8])


_TFN_WEIGHTS_9 = (1, 4, 3, 7, 5, 8, 6, 9, 10)
_TFN_WEIGHTS_8 = (10, 7, 8, 4, 6, 3, 5, 1)


def is_valid_tfn(value: str) -> bool:
    """Tax File Number check digit (ATO): 9 digits (or an older 8), weighted sum divisible by 11."""
    tfn = digits(value)
    weights = {9: _TFN_WEIGHTS_9, 8: _TFN_WEIGHTS_8}.get(len(tfn))
    if weights is None or not tfn.isdigit():
        return False
    return sum(int(c) * w for c, w in zip(tfn, weights, strict=True)) % 11 == 0


def format_abn(value: str) -> str:
    abn = digits(value)
    return f"{abn[:2]} {abn[2:5]} {abn[5:8]} {abn[8:]}" if len(abn) == 11 else value
