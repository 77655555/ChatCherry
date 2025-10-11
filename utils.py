from __future__ import annotations
import random
from typing import Iterable


def clamp(value: float, min_value: float, max_value: float) -> float:
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def lerp(a: float, b: float, t: float) -> float:
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    return a + (b - a) * t


def chance(probability: float) -> bool:
    return random.random() < max(0.0, min(1.0, probability))


def weighted_choice(choices: dict[str, float]) -> str:
    total = sum(choices.values())
    r = random.random() * total
    upto = 0.0
    for key, weight in choices.items():
        upto += weight
        if upto >= r:
            return key
    # Fallback (shouldn't happen with valid weights)
    return next(iter(choices.keys()))


def choose_one(items: Iterable):
    items = list(items)
    if not items:
        return None
    return random.choice(items)

