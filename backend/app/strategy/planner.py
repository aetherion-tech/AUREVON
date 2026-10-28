"""One exact-decimal path for candidate discovery, preview and future paper plans."""

import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from functools import reduce
from math import gcd

from app.market.renko_builder import IST
from app.market.warmup import SessionCalendar
from app.strategy.models import (
    CapitalSnapshot,
    Catalog,
    OptionContract,
    OptionQuote,
    PlanAttempt,
    PlanDecision,
    PlanLeg,
    SignalInput,
    StrategySettings,
    TradePlan,
)


class PlanRejected(ValueError):
    pass


def check(condition: bool, reason: str) -> None:
    if not condition:
        raise PlanRejected(reason)


def tick_round(value: Decimal, tick: Decimal, *, buy: bool) -> Decimal:
    return (value / tick).to_integral_value(
        rounding=ROUND_CEILING if buy else ROUND_FLOOR
    ) * tick


def strike_step(contracts: list[OptionContract]) -> Decimal:
    strikes = sorted({c.strike for c in contracts})
    check(len(strikes) >= 2, "strike_grid_unavailable")
    exponent = min(x.as_tuple().exponent for x in strikes)
    scale = Decimal(10) ** (-int(exponent))
    gaps = [int((b - a) * scale) for a, b in zip(strikes, strikes[1:])]
    return Decimal(reduce(gcd, gaps)) / scale


def select_expiry(catalog: Catalog, now: datetime, settings: StrategySettings) -> date:
    dates = sorted({c.expiry for c in catalog.contracts if c.expiry >= now.date()})
    check(bool(dates), "expiry_unavailable")
    if dates[0] == now.date():
        check(settings.expiry_policy != "skip", "expiry_day_skipped")
        if (
            settings.expiry_policy == "trade_next"
            and now.time() >= settings.expiry_switch_at
        ):
            dates = dates[1:]
            check(bool(dates), "next_expiry_unavailable")
    return dates[0]


def candidate_pairs(
    signal: SignalInput, catalog: Catalog, now: datetime, s: StrategySettings
) -> tuple[Decimal, list[tuple[OptionContract | None, list[OptionContract]]]]:
    expiry = select_expiry(catalog, now, s)
    kind = "PE" if signal.direction == 1 else "CE"
    contracts = [
        c for c in catalog.contracts if c.expiry == expiry and c.option_type == kind
    ]
    step = strike_step(contracts)
    atm = (signal.spot / step).to_integral_value(rounding=ROUND_HALF_UP) * step
    lookup = {c.strike: c for c in contracts}
    pairs = []
    for retry in range(s.liquidity_retries + 1):
        short_strike = atm - signal.direction * (s.short_offset_steps + retry) * step
        short = lookup.get(short_strike)
        if s.hedge_mode == "width":
            hedge = lookup.get(
                short_strike - signal.direction * s.hedge_width_steps * step
            )
            hedges = [hedge] if hedge else []
        else:
            hedges = [
                c
                for c in contracts
                if 0
                < signal.direction * (short_strike - c.strike)
                <= step * s.premium_search_steps
            ]
            hedges.sort(key=lambda c: abs(c.strike - short_strike))
        pairs.append((short, hedges))
    return step, pairs


def quote_for(
    contract: OptionContract,
    quotes: dict[int, OptionQuote],
    now: datetime,
    settings: StrategySettings,
) -> OptionQuote:
    quote = quotes.get(contract.token)
    check(quote is not None, "quote_unavailable")
    assert quote is not None
    check(quote.contract == contract, "quote_identity_mismatch")
    for stamp in (quote.exchange_at, quote.received_at):
        check(
            0 <= (now - stamp).total_seconds() <= settings.quote_max_age_seconds,
            "stale_or_future_quote",
        )
    check(
        abs((quote.exchange_at - quote.received_at).total_seconds())
        <= settings.quote_max_age_seconds,
        "delayed_quote",
    )
    check(
        quote.open_interest >= settings.min_open_interest, "insufficient_open_interest"
    )
    bid, ask = quote.bids[0].price, quote.asks[0].price
    allowed = max(
        settings.max_spread_abs, (bid + ask) / 2 * settings.max_spread_pct / 100
    )
    check(ask - bid <= allowed, "wide_bid_ask")
    return quote


def build_plan(
    signal: SignalInput,
    catalog: Catalog,
    quotes: dict[int, OptionQuote],
    capital: CapitalSnapshot | None,
    now: datetime,
    calendar: SessionCalendar,
    settings: StrategySettings | None = None,
    *,
    discover: bool = False,
) -> PlanDecision:
    s = settings or StrategySettings()
    attempts: list[PlanAttempt] = []
    candidates: dict[int, OptionContract] = {}
    try:
        check(now.utcoffset() is not None, "aware_plan_time_required")
        now = now.astimezone(IST)
        check(
            catalog.loaded_at.date() == now.date() and catalog.loaded_at <= now,
            "stale_catalog",
        )
        check(
            signal.at.date() == now.date()
            and 0 <= (now - signal.at).total_seconds() <= s.quote_max_age_seconds,
            "stale_or_future_signal",
        )
        check(
            any(
                session.opening <= now < session.closing
                for session in calendar.sessions
            ),
            "outside_exchange_session",
        )
        check(s.entry_start <= now.time() < s.entry_end, "outside_entry_window")
        check(signal.family in s.allowed_families, "family_filtered")
        check(signal.grade >= s.min_grade, "grade_filtered")
        check(not s.skip_high_risk or signal.risk != "High", "high_risk_filtered")
        check(
            not s.skip_opposite_bias or signal.bias_direction in (0, signal.direction),
            "opposite_bias_filtered",
        )
        check(
            signal.replaced_trade_id is None,
            "indicator_replacement_requires_reconciliation",
        )
        step, pairs = candidate_pairs(signal, catalog, now, s)
        for short, hedges in pairs:
            if short:
                candidates[short.token] = short
            for hedge in hedges:
                candidates[hedge.token] = hedge
        if discover:
            return PlanDecision(
                accepted=False,
                reason="quotes_required",
                candidates=tuple(candidates.values()),
            )
        check(capital is not None, "capital_unavailable")
        assert capital is not None
        check(
            0 <= (now - capital.at).total_seconds() <= s.quote_max_age_seconds,
            "stale_or_future_capital",
        )
        for short, hedges in pairs:
            try:
                check(short is not None, "short_strike_unavailable")
                assert short is not None
                check(bool(hedges), "hedge_strike_unavailable")
                sq = quote_for(short, quotes, now, s)
                eligible = []
                for hedge in hedges:
                    try:
                        hq = quote_for(hedge, quotes, now, s)
                        eligible.append((hedge, hq))
                    except PlanRejected as error:
                        attempts.append(
                            PlanAttempt(
                                short_symbol=short.symbol,
                                hedge_symbol=hedge.symbol,
                                reason=str(error),
                            )
                        )
                check(bool(eligible), "hedge_quote_unavailable")
                if s.hedge_mode == "premium":
                    eligible.sort(
                        key=lambda pair: (
                            abs(pair[1].asks[0].price - s.hedge_target_premium),
                            abs(pair[0].strike - short.strike),
                        )
                    )
                for hedge, hq in eligible:
                    try:
                        check(short.lot_size == hedge.lot_size, "leg_lot_size_mismatch")
                        check(
                            abs((sq.exchange_at - hq.exchange_at).total_seconds())
                            <= s.quote_max_skew_seconds,
                            "quote_pair_skew",
                        )
                        sell = tick_round(sq.bids[0].price, short.tick_size, buy=False)
                        buy = tick_round(hq.asks[0].price, hedge.tick_size, buy=True)
                        credit = sell - buy
                        width = abs(short.strike - hedge.strike)
                        check(credit >= s.minimum_credit, "insufficient_credit")
                        check(credit < width, "credit_exceeds_width")
                        per_lot_loss = (width - credit) * short.lot_size
                        margin_per_lot = (
                            per_lot_loss * (1 + s.margin_buffer_pct / 100)
                        ).quantize(Decimal(".01"), rounding=ROUND_CEILING)
                        cap = min(s.max_lots, s.max_quantity // short.lot_size)
                        lots = (
                            min(s.fixed_lots, cap)
                            if s.sizing == "fixed_lots"
                            else min(
                                int(
                                    capital.free_capital
                                    * s.risk_pct
                                    / 100
                                    // per_lot_loss
                                ),
                                int(capital.free_capital // margin_per_lot),
                                cap,
                            )
                        )
                        check(lots >= 1, "size_below_one_lot")
                        quantity = lots * short.lot_size
                        check(
                            capital.free_capital >= margin_per_lot * lots,
                            "insufficient_free_capital",
                        )
                        check(
                            sq.bids[0].quantity >= quantity
                            and hq.asks[0].quantity >= quantity,
                            "insufficient_entry_depth",
                        )
                        plan = TradePlan(
                            plan_id=hashlib.sha256(
                                json.dumps(
                                    {
                                        "signal": signal.model_dump(mode="json"),
                                        "settings": s.model_dump(mode="json"),
                                        "capital": capital.model_dump(mode="json"),
                                        "short": sq.model_dump(mode="json"),
                                        "hedge": hq.model_dump(mode="json"),
                                        "planned_at": now.isoformat(),
                                        "catalog_loaded_at": (
                                            catalog.loaded_at.isoformat()
                                        ),
                                    },
                                    sort_keys=True,
                                ).encode()
                            ).hexdigest(),
                            signal=signal,
                            planned_at=now,
                            structure="BULL_PUT_SPREAD"
                            if signal.direction == 1
                            else "BEAR_CALL_SPREAD",
                            expiry=short.expiry,
                            strike_step=step,
                            lots=lots,
                            short=PlanLeg(
                                role="SHORT",
                                side="SELL",
                                contract=short,
                                quantity=quantity,
                                limit_price=sell,
                            ),
                            hedge=PlanLeg(
                                role="HEDGE",
                                side="BUY",
                                contract=hedge,
                                quantity=quantity,
                                limit_price=buy,
                            ),
                            credit_per_unit=credit,
                            credit=credit * quantity,
                            maximum_loss=(width - credit) * quantity,
                            stop_debit_per_unit=credit
                            + (width - credit) * s.sl_pct_of_max_loss / 100,
                            profit_capture_debit_per_unit=credit
                            * (1 - s.profit_capture_pct / 100),
                            profit_capture_enabled=s.profit_capture_enabled,
                            required_margin=margin_per_lot * lots,
                            capital=capital,
                            settings=s,
                            catalog_loaded_at=catalog.loaded_at,
                            short_quote_at=sq.exchange_at,
                            hedge_quote_at=hq.exchange_at,
                        )
                        return PlanDecision(
                            accepted=True,
                            reason="planned_nonexecuting",
                            plan=plan,
                            candidates=tuple(candidates.values()),
                            attempts=tuple(attempts),
                        )
                    except PlanRejected as error:
                        attempts.append(
                            PlanAttempt(
                                short_symbol=short.symbol,
                                hedge_symbol=hedge.symbol,
                                reason=str(error),
                            )
                        )
            except PlanRejected as error:
                attempts.append(
                    PlanAttempt(
                        short_symbol=short.symbol if short else None, reason=str(error)
                    )
                )
        return PlanDecision(
            accepted=False,
            reason=attempts[-1].reason if attempts else "no_eligible_pair",
            candidates=tuple(candidates.values()),
            attempts=tuple(attempts),
        )
    except PlanRejected as error:
        return PlanDecision(
            accepted=False,
            reason=str(error),
            candidates=tuple(candidates.values()),
            attempts=tuple(attempts),
        )
