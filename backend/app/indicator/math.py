"""Streaming Pine maths. None represents na; no external numerical dependency."""

from dataclasses import dataclass, field


@dataclass
class RMA:
    length: int
    seed: list[float] = field(default_factory=list)
    value: float | None = None

    def __post_init__(self) -> None:
        if type(self.length) is not int or self.length < 1:
            raise ValueError("length must be positive")

    def update(self, value: float | None) -> float | None:
        if value is None:
            return self.value
        if self.value is None:
            self.seed.append(value)
            if len(self.seed) == self.length:
                self.value = sum(self.seed) / self.length
                self.seed.clear()
        else:
            self.value = value / self.length + (1 - 1 / self.length) * self.value
        return self.value


class RSI:
    def __init__(self, length: int) -> None:
        self.gain = RMA(length)
        self.loss = RMA(length)
        self.previous: float | None = None

    def update(self, close: float | None) -> float | None:
        if close is not None:
            if self.previous is not None:
                delta = close - self.previous
                self.gain.update(max(delta, 0))
                self.loss.update(max(-delta, 0))
            self.previous = close
        gain, loss = self.gain.value, self.loss.value
        if gain is None or loss is None:
            return None
        # Pine's explicit zero-loss branch takes priority, including flat series.
        return (
            100.0 if loss == 0 else 0.0 if gain == 0 else 100 - 100 / (1 + gain / loss)
        )


def true_range(high: float, low: float, previous: float | None) -> float:
    return (
        high - low
        if previous is None
        else max(high - low, abs(high - previous), abs(low - previous))
    )


class Supertrend:
    def __init__(self, length: int, factor: float) -> None:
        if factor <= 0:
            raise ValueError("factor must be positive")
        self.atr = RMA(length)
        self.factor = factor
        self.previous: float | None = None
        self.upper: float | None = None
        self.lower: float | None = None
        self.line: float | None = None
        self.direction = 1

    def update(self, high: float, low: float, close: float) -> tuple[float | None, int]:
        previous_atr = self.atr.value
        atr = self.atr.update(true_range(high, low, self.previous))
        if atr is not None:
            upper = (high + low) / 2 + self.factor * atr
            lower = (high + low) / 2 - self.factor * atr
            pu, pl = self.upper or 0.0, self.lower or 0.0
            pc = self.previous
            lower = lower if lower > pl or (pc is not None and pc < pl) else pl
            upper = upper if upper < pu or (pc is not None and pc > pu) else pu
            if previous_atr is None:
                self.direction = 1
            elif self.line == self.upper:
                self.direction = -1 if close > upper else 1
            else:
                self.direction = 1 if close < lower else -1
            self.upper, self.lower = upper, lower
            self.line = lower if self.direction == -1 else upper
        self.previous = close
        return self.line, self.direction


def crossover(
    a: float | None, b: float | None, pa: float | None, pb: float | None
) -> bool:
    return (
        a is not None
        and b is not None
        and pa is not None
        and pb is not None
        and a > b
        and pa <= pb
    )


def crossunder(
    a: float | None, b: float | None, pa: float | None, pb: float | None
) -> bool:
    return crossover(b, a, pb, pa)


@dataclass
class BarsSince:
    value: int | None = None

    def update(self, condition: bool) -> int | None:
        self.value = 0 if condition else None if self.value is None else self.value + 1
        return self.value


@dataclass
class Series:
    capacity: int
    values: list[float | None] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError("capacity must be positive")

    def update(self, value: float | None) -> None:
        self.values.append(value)
        self.values = self.values[-self.capacity :]

    def ago(self, offset: int) -> float | None:
        if offset < 0:
            raise ValueError("negative history offset")
        return self.values[-1 - offset] if offset < len(self.values) else None

    def sma(self, length: int) -> float | None:
        if not 1 <= length <= self.capacity:
            raise ValueError("length outside retained history")
        valid = [v for v in self.values if v is not None]
        return sum(valid[-length:]) / length if len(valid) >= length else None

    def total(self, length: int) -> float | None:
        if not 1 <= length <= self.capacity:
            raise ValueError("length outside retained history")
        valid = [v for v in self.values if v is not None]
        return sum(valid[-length:]) if len(valid) >= length else None
