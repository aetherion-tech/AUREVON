"""Independent spread arithmetic and catalog/quote rejection fixtures; no network."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.market.renko_builder import IST
from app.market.warmup import Session, SessionCalendar
from app.strategy.models import (
    CapitalSnapshot,
    Catalog,
    DepthLevel,
    OptionContract,
    OptionQuote,
    SignalInput,
    StrategySettings,
    TradePlan,
)
from app.strategy.planner import build_plan, candidate_pairs, tick_round

NOW = datetime(2026, 10, 28, 10, tzinfo=IST)
EXPIRY = date(2026, 10, 29)


def signal(sd=1, **kw):
    return SignalInput(
        **(
            dict(
                signal_id="replay:1:0",
                trade_id="[AAAAA]",
                direction=sd,
                family="CO",
                grade=3,
                risk="Low",
                bias_direction=sd,
                at=NOW,
                spot=Decimal(24000),
                index_target_1=Decimal(24000) * (1 + Decimal(sd) * Decimal(".025")),
                index_target_2=Decimal(24000) * (1 + Decimal(sd) * Decimal(".04")),
            )
            | kw
        )
    )


def catalog(lot=75, step=50, expiry=EXPIRY, extra=False):
    contracts = []
    for day in [expiry, expiry + timedelta(days=7)] if extra else [expiry]:
        for kind in ("CE", "PE"):
            for strike in range(23000, 25001, step):
                contracts.append(
                    OptionContract(
                        token=1000 + len(contracts),
                        symbol=f"NIFTY{day}{strike}{kind}",
                        expiry=day,
                        strike=Decimal(strike),
                        option_type=kind,
                        lot_size=lot,
                        tick_size=Decimal(".05"),
                    )
                )
    return Catalog(loaded_at=NOW - timedelta(hours=1), contracts=tuple(contracts))


def calendar():
    return SessionCalendar(
        NOW.date(),
        NOW.date(),
        (Session(NOW.replace(hour=9, minute=15), NOW.replace(hour=15, minute=30)),),
    )


def capital(amount="100000", **kw):
    return CapitalSnapshot(
        **(
            dict(
                at=NOW,
                free_capital=Decimal(amount),
                source="USER_PREVIEW",
                revision="test",
            )
            | kw
        )
    )


def quote(contract, bid="10", ask="10.50", qty=10000, oi=1000, **kw):
    return OptionQuote(
        **(
            dict(
                contract=contract,
                exchange_at=NOW,
                received_at=NOW,
                bids=(DepthLevel(price=Decimal(bid), quantity=qty),),
                asks=(DepthLevel(price=Decimal(ask), quantity=qty),),
                open_interest=oi,
            )
            | kw
        )
    )


def fixture(sd=1, lot=75, step=50, settings=None):
    s = settings or StrategySettings()
    sig = signal(sd)
    cat = catalog(lot, step)
    _, pairs = candidate_pairs(sig, cat, NOW, s)
    quotes = {}
    for short, hedges in pairs:
        if short:
            quotes[short.token] = quote(short, "100", "100.50")
        for hedge in hedges:
            quotes[hedge.token] = quote(hedge)
    return sig, cat, quotes, s


@pytest.mark.parametrize("sd", [1, -1])
@pytest.mark.parametrize("lot,step", [(75, 50), (50, 100), (25, 25)])
def test_both_spreads_catalog_lot_step_and_exact_payoffs(sd, lot, step):
    sig, cat, quotes, s = fixture(sd, lot, step)
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert result.accepted, result
    plan = result.plan
    assert plan.short.contract.strike == 24000 - sd * step
    assert plan.hedge.contract.strike == 24000 - sd * step * 5
    assert plan.short.contract.option_type == ("PE" if sd == 1 else "CE")
    assert plan.credit_per_unit == Decimal("89.50")
    assert plan.credit == Decimal("89.50") * lot
    assert plan.maximum_loss == (step * 4 - Decimal("89.50")) * lot
    assert plan.required_margin == (plan.maximum_loss * Decimal("1.1")).quantize(
        Decimal(".01")
    )
    assert (
        plan.stop_debit_per_unit == Decimal("89.50") + (step * 4 - Decimal("89.50")) / 2
    )
    assert plan.profit_capture_debit_per_unit == Decimal("26.850")
    assert not plan.executable and plan.broker_reported_margin is None
    assert plan.capital.source == "USER_PREVIEW"
    assert TradePlan.model_validate_json(plan.model_dump_json()) == plan
    assert isinstance(plan.model_dump(mode="json")["maximum_loss"], str)


@pytest.mark.parametrize(
    "policy,hour,minute,want",
    [
        ("skip", 10, 0, None),
        ("trade_current", 13, 0, 0),
        ("trade_next", 11, 59, 0),
        ("trade_next", 12, 0, 7),
        ("trade_next", 13, 0, 7),
    ],
)
def test_expiry_day_policies_and_no_hardcoded_weekday(policy, hour, minute, want):
    now = NOW.replace(hour=hour, minute=minute)
    cat = catalog(expiry=NOW.date(), extra=True)
    s = StrategySettings(expiry_policy=policy)
    result = build_plan(
        signal(at=now), cat, {}, capital(at=now), now, calendar(), s, discover=True
    )
    if want is None:
        assert result.reason == "expiry_day_skipped"
    else:
        assert result.candidates
        assert all(
            c.expiry == NOW.date() + timedelta(days=want) for c in result.candidates
        )


def test_no_next_expiry_and_expired_catalog():
    now = NOW.replace(hour=12)
    result = build_plan(
        signal(at=now),
        catalog(expiry=NOW.date()),
        {},
        None,
        now,
        calendar(),
        discover=True,
    )
    assert result.reason == "next_expiry_unavailable"
    result = build_plan(
        signal(),
        catalog(expiry=NOW.date() - timedelta(days=1)),
        {},
        None,
        NOW,
        calendar(),
        discover=True,
    )
    assert result.reason == "expiry_unavailable"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"family": "OT"}, "family_filtered"),
        ({"grade": 1}, "grade_filtered"),
        ({"risk": "High"}, "high_risk_filtered"),
        ({"bias_direction": -1}, "opposite_bias_filtered"),
        (
            {"replaced_trade_id": "[BBBBB]"},
            "indicator_replacement_requires_reconciliation",
        ),
        ({"at": NOW - timedelta(seconds=6)}, "stale_or_future_signal"),
    ],
)
def test_entry_filters(change, reason):
    sig, cat, quotes, s = fixture()
    s = StrategySettings(allowed_families=("CO", "DIV"))
    result = build_plan(signal(**change), cat, quotes, capital(), NOW, calendar(), s)
    assert result.reason == reason


@pytest.mark.parametrize("which", ["short", "hedge"])
def test_missing_strikes_fail_without_inventing_contract(which):
    s = StrategySettings(liquidity_retries=0)
    sig, cat, quotes, _ = fixture(settings=s)
    _, pairs = candidate_pairs(sig, cat, NOW, s)
    missing = pairs[0][0] if which == "short" else pairs[0][1][0]
    cat = cat.model_copy(
        update={
            "contracts": tuple(c for c in cat.contracts if c.token != missing.token)
        }
    )
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert not result.accepted
    assert result.reason == (
        "short_strike_unavailable" if which == "short" else "hedge_strike_unavailable"
    )


@pytest.mark.parametrize(
    "problem", ["missing", "stale", "future", "wide", "oi", "identity", "depth", "skew"]
)
def test_quote_liquidity_freshness_and_identity(problem):
    s = StrategySettings(liquidity_retries=0)
    sig, cat, quotes, _ = fixture(settings=s)
    short, hedges = candidate_pairs(sig, cat, NOW, s)[1][0]
    token = short.token
    q = quotes[token]
    if problem == "missing":
        quotes.pop(token)
    elif problem == "stale":
        quotes[token] = q.model_copy(update={"exchange_at": NOW - timedelta(seconds=6)})
    elif problem == "future":
        quotes[token] = q.model_copy(update={"received_at": NOW + timedelta(seconds=1)})
    elif problem == "wide":
        quotes[token] = quote(short, "100", "110")
    elif problem == "oi":
        quotes[token] = quote(short, "100", "100.5", oi=0)
    elif problem == "identity":
        quotes[token] = q.model_copy(update={"contract": hedges[0]})
    elif problem == "depth":
        quotes[token] = quote(short, "100", "100.5", qty=1)
    else:
        quotes[token] = q.model_copy(update={"exchange_at": NOW - timedelta(seconds=3)})
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert not result.accepted
    assert result.attempts


def test_liquidity_retries_at_most_two_and_keep_rejection_reasons():
    sig, cat, quotes, s = fixture()
    _, pairs = candidate_pairs(sig, cat, NOW, s)
    quotes.pop(pairs[0][0].token)
    quotes.pop(pairs[1][0].token)
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert result.accepted and result.plan.short.contract == pairs[2][0]
    assert len(result.attempts) == 2
    quotes.pop(pairs[2][0].token)
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert not result.accepted and len(result.attempts) == 3


@pytest.mark.parametrize("credit", ["0", "-1", "0.01", "200", "201"])
def test_nonpositive_too_small_or_impossible_credit(credit):
    s = StrategySettings(liquidity_retries=0)
    sig, cat, quotes, _ = fixture(settings=s)
    short, hedges = candidate_pairs(sig, cat, NOW, s)[1][0]
    quotes[short.token] = quote(
        short,
        str(Decimal("10.50") + Decimal(credit)),
        str(Decimal("11") + Decimal(credit)),
    )
    # Negative/zero credits still have valid individual bid/ask prices.
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert not result.accepted


def test_risk_pct_sizing_uses_max_loss_free_capital_and_buffered_margin():
    s = StrategySettings(sizing="risk_pct", risk_pct=Decimal("10"), max_lots=99)
    sig, cat, quotes, _ = fixture(settings=s)
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert result.accepted
    assert result.plan.lots == 1  # floor(10,000 / 8,287.50)
    result = build_plan(sig, cat, quotes, capital("8000"), NOW, calendar(), s)
    assert not result.accepted and result.reason == "size_below_one_lot"


@pytest.mark.parametrize(
    "amount,reason",
    [("0", "insufficient_free_capital"), ("9000", "insufficient_free_capital")],
)
def test_fixed_size_insufficient_capital(amount, reason):
    sig, cat, quotes, s = fixture()
    result = build_plan(sig, cat, quotes, capital(amount), NOW, calendar(), s)
    assert not result.accepted and result.reason == reason


def test_lot_quantity_caps_and_capital_missing_stale():
    s = StrategySettings(fixed_lots=5, max_lots=3, max_quantity=150)
    sig, cat, quotes, _ = fixture(settings=s)
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert result.plan.lots == 2 and result.plan.short.quantity == 150
    assert (
        build_plan(sig, cat, quotes, None, NOW, calendar(), s).reason
        == "capital_unavailable"
    )
    assert (
        build_plan(
            sig, cat, quotes, capital(at=NOW - timedelta(seconds=6)), NOW, calendar(), s
        ).reason
        == "stale_or_future_capital"
    )


def test_tick_rounding_is_conservative_and_grid_is_catalog_derived():
    assert tick_round(Decimal("10.031"), Decimal(".05"), buy=False) == Decimal("10")
    assert tick_round(Decimal("10.031"), Decimal(".05"), buy=True) == Decimal("10.05")
    sig, cat, quotes, s = fixture()
    first = candidate_pairs(sig, cat, NOW, s)[1][0][0]
    quotes[first.token] = quote(first, "100.039", "100.50")
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert result.plan.short.limit_price == 100


def test_premium_hedge_mode_picks_closest_valid_further_otm_quote():
    s = StrategySettings(hedge_mode="premium", liquidity_retries=0)
    sig, cat, _, _ = fixture(settings=s)
    short, hedges = candidate_pairs(sig, cat, NOW, s)[1][0]
    quotes = {short.token: quote(short, "100", "100.5")}
    quotes[hedges[0].token] = quote(hedges[0], "1", "1.5")
    quotes[hedges[4].token] = quote(hedges[4], "7", "7.5")
    result = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s)
    assert result.accepted and result.plan.hedge.contract == hedges[4]


def test_plan_schema_rejects_tampered_quantity_credit_or_margin():
    sig, cat, quotes, s = fixture()
    plan = build_plan(sig, cat, quotes, capital(), NOW, calendar(), s).plan
    for key, value in [
        ("credit", "1"),
        ("maximum_loss", "1"),
        ("required_margin", "1"),
    ]:
        payload = plan.model_dump(mode="json")
        payload[key] = value
        with pytest.raises(ValidationError):
            TradePlan.model_validate(payload)


def test_catalog_date_and_session_windows():
    sig, cat, quotes, s = fixture()
    stale = cat.model_copy(update={"loaded_at": NOW - timedelta(days=1)})
    assert (
        build_plan(sig, stale, quotes, capital(), NOW, calendar(), s).reason
        == "stale_catalog"
    )


def test_session_and_entry_cutoffs_are_exclusive():
    sig, cat, quotes, s = fixture()
    closed = SessionCalendar(NOW.date(), NOW.date(), ())
    assert (
        build_plan(sig, cat, quotes, capital(), NOW, closed, s).reason
        == "outside_exchange_session"
    )
    now = NOW.replace(hour=14, minute=45)
    assert (
        build_plan(
            signal(at=now), cat, quotes, capital(at=now), now, calendar(), s
        ).reason
        == "outside_entry_window"
    )


def test_atm_half_step_uses_half_up_and_keeps_otm_offsets():
    sig = signal(spot=Decimal("24025"))
    short = candidate_pairs(sig, catalog(), NOW, StrategySettings())[1][0][0]
    assert short.strike == 24000  # ATM 24050, one step below.


@pytest.mark.parametrize(
    "values",
    [
        {"fixed_lots": True},
        {"risk_pct": Decimal("NaN")},
        {"expiry_policy": "weekday_guess"},
        {"skip_high_risk": "false"},
        {"version": True},
        {"liquidity_retries": 3},
        {"hedge_width_steps": 0},
    ],
)
def test_invalid_or_ambiguous_settings_rejected(values):
    with pytest.raises(ValidationError):
        StrategySettings(**values)


def test_duplicate_catalog_identity_and_unsafe_signal_direction_rejected():
    cat = catalog()
    with pytest.raises(ValidationError):
        Catalog(loaded_at=NOW, contracts=(cat.contracts[0], cat.contracts[0]))
    with pytest.raises(ValidationError):
        signal(direction=True)
    with pytest.raises(ValidationError):
        signal(index_target_1=Decimal("23000"))
