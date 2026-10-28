"""Pine's indicator position and statistics, separate from paper/broker positions."""

from typing import Any

from app.indicator.features import nz
from app.indicator.settings import IndicatorSettings
from app.indicator.signals import TYPES
from app.indicator.text import render

CHARACTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789#@$%&*+!"


def trade_id(sequence: int, salt: int) -> str:
    value = (sequence * 63283001 + salt) % 102400000
    result = ""
    for _ in range(5):
        result = CHARACTERS[value % 40 : value % 40 + 1] + result
        value //= 40
    return "[" + result + "]"


def family_index(typ: str, sd: int) -> int:
    return (0 if typ == "CORE" else 1 if typ in ("DIV", "HDIV") else 2) * 2 + (
        0 if sd == 1 else 1
    )


def invalidation(typ: str, sd: int, v: dict[str, Any], f: dict[str, Any]) -> Any:
    if typ == "DIV":
        raw = v["lastBotP" if sd == 1 else "lastTopP"]
    elif typ == "BRK":
        raw = v["lastTopP" if sd == 1 else "lastBotP"]
    elif typ == "TRAP":
        raw = v["trapDnLvl" if sd == 1 else "trapUpLvl"]
    elif typ == "ORB":
        raw = v["orH" if sd == 1 else "orL"]
    else:
        raw = (
            f["supertrend"]
            if (f["is_up"] if sd == 1 else not f["is_up"])
            else v["lastBotP" if sd == 1 else "lastTopP"]
        )
    return nz(raw, f["supertrend"])


def text_context(
    v: dict[str, Any],
    f: dict[str, Any],
    s: IndicatorSettings,
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return (
        v
        | s.values
        | {
            "bsf": f["bars_since_flip"],
            "trendAge": f["trend_age"],
            "divTxt": f["divergence_text"],
            "isUp": f["is_up"],
            "lastTopP": v["lastTopP"],
            "lastBotP": v["lastBotP"],
            "biasScore": f["bias_score"],
            "rsi": f["rsi"],
            "flowOk": f["flow_ok"],
            "flowScore": f["flow_score"],
            "risk": signal["risk"]
            if signal
            else {"label": "Low", "text": "nothing unusual."},
        }
    )


def explanation(
    signal: dict[str, Any], v: dict[str, Any], f: dict[str, Any], s: IndicatorSettings
) -> dict[str, Any]:
    typ, sd, g = (signal[k] for k in ("type", "direction", "grade"))
    env = text_context(v, f, s, signal)
    return {
        "family": render("f_family", env, typ),
        "name": render("f_name", env, typ, sd),
        "meaning": render("f_meaning", env, typ, sd),
        "why_now": render("f_reason", env, typ, sd),
        "risk": signal["risk"],
        "tooltip": render("f_sigTip", env, typ, sd, g),
    }


def trade_step(
    v: dict[str, Any],
    f: dict[str, Any],
    s: IndicatorSettings,
    accepted: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    i, c, color = (f[k] for k in ("index", "close", "brick_direction"))
    t1_now = False
    if v["posDir"] != 0 and i > v["posBar"]:
        sd = v["posDir"]
        v["oppRun"] = v["oppRun"] + 1 if color == -sd else 0
        if not v["posT1Hit"] and sd * (c - v["posT1"]) >= 0:
            v["posT1Hit"] = True
            t1_now = True
            if s["exitOnStop"]:
                v["posStop"] = v["posEntry"]
        t2 = s["exitAtT2"] and sd * (c - v["posT2"]) >= 0
        why = ""
        reason = ""
        if t2:
            why = f"Target 2 ({s['tgt2Pct']:g}%) reached - the plan is complete."
            reason = "target_2"
        elif (
            s["exitOnStop"]
            and v["posStop"] is not None
            and sd * (c - v["posStop"]) <= 0
        ):
            why = "A brick closed beyond the safety level."
            reason = "safety"
        elif v["oppRun"] >= s["exitOppN"]:
            lead = (
                "The next brick closed"
                if s["exitOppN"] == 1
                else f"{s['exitOppN']} bricks closed"
            )
            why = (
                lead
                + f" in the opposite colour ({'RED' if sd == 1 else 'GREEN'})"
                + " - momentum has turned."
            )
            reason = "opposite_bricks"
        if why:
            t1_now = False
            points = sd * (c - v["posEntry"])
            pct = points / v["posEntry"] * 100
            held = i - v["posBar"]
            ci = family_index(v["posType"], sd)
            env = text_context(v, f, s)
            tooltip = render(
                "f_exitTip",
                env,
                v["posType"],
                sd,
                why,
                v["posEntry"],
                c,
                pct,
                points,
                held,
                v["posT1Hit"] or t2,
                t2,
                v["posId"],
            )
            events.append(
                {
                    "kind": "EXIT",
                    "trade_id": v["posId"],
                    "type": v["posType"],
                    "direction": sd,
                    "price": c,
                    "points": points,
                    "percent": pct,
                    "held_bricks": held,
                    "target_1_hit": v["posT1Hit"] or t2,
                    "target_2_hit": t2,
                    "reason": reason,
                    "explanation": why,
                    "tooltip": tooltip,
                }
            )
            for key, value in (
                ("cN", 1),
                ("cP", pct),
                ("cB", held),
                ("cW", int(pct > 0)),
                ("cT1", int(v["posT1Hit"] or t2)),
                ("cT2", int(t2)),
            ):
                v[key][ci] += value
            v["trN"] += 1
            v["trP"] += pct
            v["trW"] += int(pct > 0)
            v["posDir"] = v["oppRun"] = 0
    # Pine prefers long if both entry booleans are true. Opposite signals can
    # replace an unexited position with nondefault exit settings; do not fabricate EXIT.
    entries = [sig for sig in accepted if sig["direction"] != v["posDir"]]
    if entries:
        signal = next((sig for sig in entries if sig["direction"] == 1), entries[0])
        sd, typ, g = (signal[k] for k in ("direction", "type", "grade"))
        raw = invalidation(typ, sd, v, f)
        box = s["boxSize"]
        stop = (
            (
                max(min(raw, c - box), c - s["stopCapBx"] * box)
                if sd == 1
                else min(max(raw, c + box), c + s["stopCapBx"] * box)
            )
            if raw is not None
            else None
        )
        replaced = v["posId"] if v["posDir"] else None
        v["tradeSeq"] += 1
        v.update(
            posDir=sd,
            posEntry=c,
            posStop=stop,
            posT1=c * (1 + sd * s["tgt1Pct"] / 100),
            posT2=c * (1 + sd * s["tgt2Pct"] / 100),
            oppRun=0,
            posId=trade_id(v["tradeSeq"], v["idSalt"]),
            posBar=i,
            posT1Hit=False,
            posType=typ,
            posGrade=g,
        )
        env = text_context(v, f, s, signal)
        tip = (
            ("▲ " if sd == 1 else "▼ ")
            + render("f_code", env, typ, sd, "ENTRY")
            + " "
            + v["posId"]
            + "\n\nTRADE ID "
            + v["posId"]
            + " - the matching EXIT will show this same ID.\n\n"
            + render("f_sigTip", env, typ, sd, g)
            + "\n\n"
            + render("f_planTip", env, typ, sd, c, v["posT1"], v["posT2"], stop)
            + "\n\nGuide only - not advice."
        )
        v["posTip"] = tip
        events.append(
            {
                "kind": "ENTRY",
                "trade_id": v["posId"],
                "type": typ,
                "direction": sd,
                "price": c,
                "target_1": v["posT1"],
                "target_2": v["posT2"],
                "stop": stop,
                "grade": g,
                "replaced_trade_id": replaced,
                "tooltip": tip,
            }
        )
    if t1_now:
        events.append(
            {
                "kind": "T1",
                "trade_id": v["posId"],
                "direction": v["posDir"],
                "price": c,
                "tooltip": f"Trade {v['posId']}: Target 1 ({s['tgt1Pct']:g}%) "
                f"reached at {c:g}.\n"
                f"Target 2 ({s['tgt2Pct']:g}%): {v['posT2']:g}\n"
                "The EXIT still comes from the opposite-colour brick (or Target 2).",
            }
        )
    if accepted:
        entry = next((e for e in events if e["kind"] == "ENTRY"), None)
        v["lastSigTip"] = (
            entry["tooltip"]
            if entry
            else accepted[0]["explanation"]["tooltip"]
            + (
                "\n\nA trade in this direction is already active - no new entry."
                "\nGuide only - not advice."
            )
        )
    return events


def signal_statistics(
    v: dict[str, Any],
    f: dict[str, Any],
    s: IndicatorSettings,
    accepted: list[dict[str, Any]],
) -> None:
    for signal in accepted:
        for key, value in (
            ("pBar", f["index"]),
            ("pPx", f["close"]),
            ("pDir", signal["direction"]),
            ("pTyp", TYPES.index(signal["type"])),
            ("pGr", signal["grade"]),
        ):
            v[key].append(value)
    for j in range(len(v["pBar"]) - 1, -1, -1):
        if f["index"] - v["pBar"][j] >= s["evalBricks"]:
            points = v["pDir"][j] * (f["close"] - v["pPx"][j])
            typ, g = v["pTyp"][j], v["pGr"][j] - 1
            for key, idx, value in (
                ("tN", typ, 1),
                ("tW", typ, int(points > 0)),
                ("tP", typ, points),
                ("gN", g, 1),
                ("gW", g, int(points > 0)),
                ("gP", g, points),
            ):
                v[key][idx] += value
            for key in ("pBar", "pPx", "pDir", "pTyp", "pGr"):
                v[key].pop(j)
