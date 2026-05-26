from __future__ import annotations

from collections.abc import Iterable


def normalize_hkl(values: Iterable[object]) -> tuple[int, ...]:
    hkl = tuple(int(value) for value in values)
    if len(hkl) not in {3, 4}:
        raise ValueError(f"hkl must contain 3 or 4 indices, got {len(hkl)}: {hkl}")
    return hkl


def format_hkl(values: Iterable[object]) -> str:
    return f"({' '.join(str(value) for value in normalize_hkl(values))})"


def split_hkl_components(values: Iterable[object]) -> tuple[int, int, int | None, int]:
    hkl = normalize_hkl(values)
    if len(hkl) == 3:
        h, k, l = hkl
        return h, k, None, l
    h, k, i, l = hkl
    return h, k, i, l
