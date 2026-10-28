"""Pine divergence, outlook and ten-factor bias, in source execution order."""

from typing import Any

from app.indicator.settings import IndicatorSettings
from app.indicator.text import number_text


def nz(value: Any, replacement: Any = 0) -> Any:
    return replacement if value is None else value


def ge(a: Any, b: Any) -> bool:
    return a is not None and b is not None and a >= b


def gt(a: Any, b: Any) -> bool:
    return a is not None and b is not None and a > b


def nearest(above: bool, close: float, values: list[Any]) -> float | None:
    valid = [
        x for x in values if x is not None and (x >= close if above else x <= close)
    ]
    return (min(valid) if above else max(valid)) if valid else None


def divergence(
    v: dict[str, Any],
    old: dict[str, Any],
    previous: dict[str, Any],
    f: dict[str, Any],
    s: IndicatorSettings,
) -> None:
    """Compare old pivots before the base engine's updated swings are consumed."""
    i, close, rsi, color = f["index"], f["close"], f["rsi"], f["brick_direction"]
    half = s["boxSize"] / 2
    f.update(
        bull_div=False,
        bear_div=False,
        hidden_bull=False,
        hidden_bear=False,
        divergence_text="",
    )
    for side, prior_color, new_color in [("Top", 1, -1), ("Bot", -1, 1)]:
        if previous.get("brick_direction") != prior_color or color != new_color:
            continue
        price, momentum = previous["close"], previous["rsi"]
        last, last_r, last_i = (old[f"last{side}{k}"] for k in ("P", "R", "I"))
        if (
            last is None
            or last_i is None
            or i - 1 - last_i > s["maxGap"]
            or momentum is None
            or last_r is None
        ):
            continue
        same = abs(price - last) < half
        extreme = price >= last + half if side == "Top" else price <= last - half
        other = price <= last - half if side == "Top" else price >= last + half
        price_ok = same if s["topType"] == "Equal only" else same or extreme
        regular = price_ok and (
            momentum <= last_r - s["minRsiGap"] and last_r >= s["rsiHi"]
            if side == "Top"
            else momentum >= last_r + s["minRsiGap"] and last_r <= s["rsiLo"]
        )
        hidden = (
            not regular
            and s["hdivOn"]
            and other
            and (
                momentum >= last_r + s["minRsiGap"] and not f["is_up"]
                if side == "Top"
                else momentum <= last_r - s["minRsiGap"] and f["is_up"]
            )
        )
        sd = -1 if side == "Top" else 1
        if regular:
            f["bear_div" if sd == -1 else "bull_div"] = True
            v["lastDivDir"], v["lastDivBar"] = sd, i
            level = (
                ("an equal high" if same else "a higher high")
                if sd == -1
                else ("an equal low" if same else "a lower low")
            )
            f["divergence_text"] = (
                f"price made {level} but RSI {'fell' if sd == -1 else 'rose'} "
                f"from {number_text(last_r, '#.#')} "
                f"to {number_text(momentum, '#.#')} - "
                f"{'buyers' if sd == -1 else 'sellers'} are weakening."
            )
        elif hidden:
            f["hidden_bear" if sd == -1 else "hidden_bull"] = True
            v["lastHidDir"], v["lastHidBar"] = sd, i
            trend_text = (
                "a downtrend - the fall" if sd == -1 else "an uptrend - the rise"
            )
            f["divergence_text"] = (
                f"price made a {'LOWER high' if sd == -1 else 'HIGHER low'} but RSI "
                f"{'rose' if sd == -1 else 'fell'} from {number_text(last_r, '#.#')} "
                f"to {number_text(momentum, '#.#')} "
                f"in {trend_text} "
                "is likely to continue."
            )
    top, bot, tr, br = (v[k] for k in ("lastTopP", "lastBotP", "lastTopR", "lastBotR"))
    top_armed = (
        top is not None and ge(tr, s["rsiHi"]) and i - nz(v["lastTopI"]) <= s["maxGap"]
    )
    bot_armed = (
        bot is not None and ge(s["rsiLo"], br) and i - nz(v["lastBotI"]) <= s["maxGap"]
    )
    f["bear_forming"] = bool(
        top_armed
        and color == 1
        and ge(nz(tr) - s["minRsiGap"], rsi)
        and (
            abs(close - top) < half
            or (s["topType"] == "Equal or higher" and close >= top + half)
        )
    )
    f["bull_forming"] = bool(
        bot_armed
        and color == -1
        and ge(rsi, nz(br) + s["minRsiGap"])
        and (
            abs(close - bot) < half
            or (s["topType"] == "Equal or higher" and close <= bot - half)
        )
    )


def outlook_bias(
    v: dict[str, Any],
    previous: dict[str, Any],
    f: dict[str, Any],
    s: IndicatorSettings,
    history: list[dict[str, Any]],
) -> None:
    i, c, color, run, up = (
        f[k] for k in ("index", "close", "brick_direction", "run_length", "is_up")
    )
    aligned = (color == 1 and up) or (color == -1 and not up)
    bucket = min(run, 6) - 1 + (0 if aligned else 6)
    if i > 1 and previous.get("brick_direction", 0) != 0:
        pb = previous["bucket"]
        v["nTot"][pb] += 1
        if color == previous["brick_direction"]:
            v["nCont"][pb] += 1
        else:
            suffix = "Up" if previous["brick_direction"] == 1 else "Dn"
            v["sumRun" + suffix] += previous["run_length"]
            v["cntRun" + suffix] += 1
    total = v["nTot"][bucket]
    prob = v["nCont"][bucket] * 100 / total if total >= s["outSamples"] else None
    suffix = "Up" if color == 1 else "Dn"
    avg = v["sumRun" + suffix] / v["cntRun" + suffix] if v["cntRun" + suffix] else None
    st = f["supertrend"]
    distance = abs(c - st) / s["boxSize"] if st is not None else None
    res = nearest(
        True,
        c,
        [
            v["lastTopP"],
            f["previous_high"],
            f["day_high"],
            s["manRes"] if s["manRes"] > 0 else None,
            None if up else st,
        ],
    )
    sup = nearest(
        False,
        c,
        [
            v["lastBotP"],
            f["previous_low"],
            f["day_low"],
            s["manSup"] if s["manSup"] > 0 else None,
            st if up else None,
        ],
    )
    f.update(
        bucket=bucket,
        continuation_probability=prob,
        up_probability=prob if color == 1 or prob is None else 100 - prob,
        average_run=avg,
        remaining_bricks=max(avg - run, 0) if avg is not None else None,
        up_trigger=(c if color == 1 else f["open"]) + s["boxSize"],
        down_trigger=(c if color == -1 else f["open"]) - s["boxSize"],
        st_distance=distance,
        stretched=ge(distance, s["stretchBx"]),
        resistance=res,
        support=sup,
    )
    half = s["boxSize"] / 2

    def structure(now: Any, before: Any) -> int:
        return (
            1
            if ge(now, before + half if before is not None else None)
            else -1
            if ge(before - half if before is not None else None, now)
            else 0
        )

    score = f["flow_score"]
    factors = {
        "supertrend": 2 if up else -2,
        "run": color if run >= 2 else 0,
        "rsi": 1 if ge(f["rsi"], 55) else -1 if ge(45, f["rsi"]) else 0,
        "flow": (
            2
            if score >= 3
            else 1
            if score >= 1
            else -2
            if score <= -3
            else -1
            if score <= -1
            else 0
        )
        if f["flow_ok"]
        else 0,
        "structure": structure(v["lastTopP"], v["prevTopP"])
        + structure(v["lastBotP"], v["prevBotP"]),
        "divergence": v["lastDivDir"] * 2
        if v["lastDivBar"] is not None and i - v["lastDivBar"] <= s["divFresh"]
        else 1
        if f["bull_forming"]
        else -1
        if f["bear_forming"]
        else 0,
        "hidden": v["lastHidDir"]
        if v["lastHidBar"] is not None and i - v["lastHidBar"] <= s["divFresh"]
        else 0,
        "swing": 1 if gt(c, v["lastTopP"]) else -1 if gt(v["lastBotP"], c) else 0,
        "probability": 0
        if prob is None
        else (
            (1 if color == 1 else -1)
            if prob >= 58
            else (-1 if color == 1 else 1)
            if prob <= 42
            else 0
        ),
        "day": 1
        if gt(c, f["day_open"]) and gt(c, f["previous_close"])
        else -1
        if gt(f["day_open"], c) and gt(f["previous_close"], c)
        else 0,
    }
    bias = sum(factors.values())
    previous_bias = v["biasDir"]
    if bias >= 4:
        v["biasDir"] = 1
    elif bias <= -4:
        v["biasDir"] = -1
    elif (v["biasDir"] == 1 and bias <= 1) or (v["biasDir"] == -1 and bias >= -1):
        v["biasDir"] = 0
    if previous_bias != v["biasDir"]:
        v["biasSince"] = i
    # Pine's lookback includes the current brick, only after bar_index > 12.
    recent = (history + [f])[-12:] if i > 12 else []
    cutoff = f["time_ms"] - s["extMins"] * 60000
    late_l = (
        sum(x["brick_direction"] == 1 for x in recent if x["time_ms"] >= cutoff)
        > s["extBricks"]
    )
    late_s = (
        sum(x["brick_direction"] == -1 for x in recent if x["time_ms"] >= cutoff)
        > s["extBricks"]
    )
    flip_count = (
        sum(bool(x["flipped"]) for x in (history + [f])[-30:]) if i >= 29 else None
    )
    f.update(
        factors=factors,
        bias_score=bias,
        bias_direction=v["biasDir"],
        bias_strong=abs(bias) >= 8,
        late_long=late_l,
        late_short=late_s,
        choppy=flip_count is not None and flip_count >= 4,
        reversal_watch=(
            v["biasDir"] == 1 and (f["bear_forming"] or factors["divergence"] < 0)
        )
        or (v["biasDir"] == -1 and (f["bull_forming"] or factors["divergence"] > 0)),
    )
