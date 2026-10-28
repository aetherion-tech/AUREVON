"""Literal Pine raw conditions, direction priorities, grading and risk factors."""

from typing import Any

from app.indicator.features import gt, nz
from app.indicator.math import crossover, crossunder
from app.indicator.settings import IndicatorSettings

PRIORITY = ("DIV", "CORE", "ORB", "BRK", "TRAP", "HDIV", "SRG", "PB")
TYPES = ("CORE", "DIV", "HDIV", "PB", "BRK", "TRAP", "ORB", "SRG")


def raw_signals(
    v: dict[str, Any], previous: dict[str, Any], f: dict[str, Any], s: IndicatorSettings
) -> dict[int, dict[str, bool]]:
    i, c, color, up = (f[k] for k in ("index", "close", "brick_direction", "is_up"))
    if f["flipped"]:
        v["coreDone"] = False
    minute = f["minute"]
    if 555 <= minute < 570:
        v["orH"] = f["high"] if v["orH"] is None else max(v["orH"], f["high"])
        v["orL"] = f["low"] if v["orL"] is None else min(v["orL"], f["low"])
    orb_end = s["orbUntil"] // 100 * 60 + s["orbUntil"] % 100
    orb_valid = (
        v["orH"] is not None
        and v["orL"] is not None
        and v["orH"] - v["orL"] >= s["orbMinBx"] * s["boxSize"]
        and 570 <= minute < orb_end
    )
    orb_l = bool(orb_valid and c > v["orH"] and not v["orbUpSeen"])
    orb_s = bool(orb_valid and c < v["orL"] and not v["orbDnSeen"])
    # Range consumption is independent of orbOn, alignment, cooldown and grade.
    if orb_valid and c > v["orH"]:
        v["orbUpSeen"] = True
    if orb_valid and c < v["orL"]:
        v["orbDnSeen"] = True
    brk_l = crossover(c, v["lastTopP"], previous.get("close"), previous.get("last_top"))
    brk_s = crossunder(
        c, v["lastBotP"], previous.get("close"), previous.get("last_bottom")
    )
    if brk_l:
        v["trapUpLvl"], v["trapUpBar"] = v["lastTopP"], i
    if brk_s:
        v["trapDnLvl"], v["trapDnBar"] = v["lastBotP"], i
    trap = {1: False, -1: False}
    for sd, side in ((-1, "Up"), (1, "Dn")):
        bar = v[f"trap{side}Bar"]
        if bar is not None and i > bar:
            if i - bar > s["trapBars"]:
                v[f"trap{side}Bar"] = None
            elif color == sd and (
                gt(c, v[f"trap{side}Lvl"]) if sd == 1 else gt(v[f"trap{side}Lvl"], c)
            ):
                trap[sd] = s["trapOn"]
                v[f"trap{side}Bar"] = None
    raw: dict[int, dict[str, bool]] = {}
    for sd in (1, -1):
        aligned = color == sd and (up if sd == 1 else not up)
        side = "L" if sd == 1 else "S"
        surge = (
            s["srgOn"]
            and f["flow_ok"]
            and f["flow_score"] * sd >= s["srgMin"]
            and (not s["srgNeedVol"] or f["volume_side"] * sd > 0)
        )
        f["surge_" + side] = surge
        if surge and not previous.get("surge_" + side, False):
            v["srgArm" + side] = i
        arm = v["srgArm" + side]
        pivot = v["lastTopI" if sd == 1 else "lastBotI"]
        raw[sd] = {
            "DIV": f["bull_div" if sd == 1 else "bear_div"],
            "CORE": aligned
            and f["bars_since_flip"] < s["coreWindow"]
            and not v["coreDone"],
            "ORB": s["orbOn"] and (orb_l if sd == 1 else orb_s) and aligned,
            "BRK": s["brkOn"]
            and (brk_l if sd == 1 else brk_s)
            and aligned
            and i - nz(pivot) <= s["brkAge"],
            "TRAP": trap[sd],
            "HDIV": f["hidden_bull" if sd == 1 else "hidden_bear"],
            "SRG": surge and arm is not None and i - arm <= 2 and aligned,
            "PB": s["pbOn"]
            and aligned
            and previous.get("brick_direction") == -sd
            and f["trend_age"] >= s["pbMinAge"],
        }
    return raw


def grade(typ: str, sd: int, f: dict[str, Any], s: IndicatorSettings) -> int:
    if typ in ("DIV", "TRAP"):
        level = f["support" if sd == 1 else "resistance"]
        evidence = sum(
            (
                f["flow_ok"] and f["flow_score"] * sd >= 1,
                f["flow_ok"] and f["vwap_side"] * sd > 0,
                (not f["is_up"] if sd == 1 else f["is_up"]) and f["stretched"],
                level is not None
                and (f["close"] - level if sd == 1 else level - f["close"])
                <= 2 * s["boxSize"],
                gt(f["rsi"], nz(f["previous_rsi"]))
                if sd == 1
                else gt(nz(f["previous_rsi"]), f["rsi"]),
            )
        )
        return 3 if evidence >= 3 else 2 if evidence == 2 else 1
    aligned = sd * f["bias_score"] - (
        2 if f["late_long" if sd == 1 else "late_short"] else 0
    )
    return 3 if aligned >= 5 else 2 if aligned >= 2 else 1


def risk(typ: str, sd: int, f: dict[str, Any], s: IndicatorSettings) -> dict[str, Any]:
    reversal = typ in ("DIV", "TRAP")
    level = f["resistance" if sd == 1 else "support"]
    checks = [
        (
            not reversal and f["late_long" if sd == 1 else "late_short"],
            "a big run already happened (late); ",
        ),
        (
            not reversal
            and f["stretched"]
            and (f["is_up"] if sd == 1 else not f["is_up"]),
            "price is far from its trend line; ",
        ),
        (f["choppy"], "market is zig-zagging; "),
        (f["flow_ok"] and f["flow_score"] * sd <= -2, "big-player flow disagrees; "),
        (
            reversal or f["bias_direction"] not in (0, sd),
            "goes against the current direction reading; ",
        ),
        (
            level is not None
            and (level - f["close"] if sd == 1 else f["close"] - level)
            <= 2 * s["boxSize"],
            "ceiling is very close; " if sd == 1 else "floor is very close; ",
        ),
    ]
    messages = [text for flag, text in checks if flag]
    count = len(messages)
    return {
        "count": count,
        "label": "Low" if count <= 1 else "Medium" if count == 2 else "High",
        "text": "".join(messages) or "nothing unusual.",
    }


def select_signals(
    raw: dict[int, dict[str, bool]],
    v: dict[str, Any],
    f: dict[str, Any],
    s: IndicatorSettings,
) -> list[dict[str, Any]]:
    candidates = []
    minimum = {"Strong only": 3, "Moderate and above": 2, "Weak and above (all)": 1}[
        s["minGrade"]
    ]
    for sd in (1, -1):
        cooldown = (
            f["index"] - v["lastSigL" if sd == 1 else "lastSigS"] >= s["sigCooldown"]
        )
        selected = next(
            (
                typ
                for typ in PRIORITY
                if raw[sd][typ] and (typ in ("DIV", "CORE") or cooldown)
            ),
            "",
        )
        for typ in PRIORITY:
            if not raw[sd][typ]:
                continue
            g = grade(typ, sd, f, s)
            reason = (
                "cooldown"
                if typ not in ("DIV", "CORE") and not cooldown
                else "lower_priority"
                if typ != selected
                else "below_minimum_grade"
                if g < minimum
                else "accepted"
            )
            candidates.append(
                {
                    "type": typ,
                    "direction": sd,
                    "grade": g,
                    "accepted": reason == "accepted",
                    "reason": reason,
                    "risk": risk(typ, sd, f, s),
                }
            )
    return candidates


def accept_signal(signal: dict[str, Any], v: dict[str, Any], f: dict[str, Any]) -> None:
    sd, typ = signal["direction"], signal["type"]
    v["lastSigL" if sd == 1 else "lastSigS"] = f["index"]
    v.update(
        lastSigRisk=signal["risk"]["label"],
        lastSigDirV=sd,
        lastSigType=typ,
        lastSigGradeV=signal["grade"],
        lastSigBarV=f["index"],
        lastSigPxV=f["close"],
    )
    v["sigToday"] += 1
    if typ == "CORE":
        v["coreDone"] = True
    if typ == "ORB":
        v["orbUpSeen" if sd == 1 else "orbDnSeen"] = True
    if typ == "SRG":
        v["srgArmL" if sd == 1 else "srgArmS"] = None
