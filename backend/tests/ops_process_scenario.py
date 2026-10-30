"""Child process for deliberate crash/restart drills. Synthetic providers only."""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_option_planner import NOW, calendar
from test_paper_execution import drive, opened, prices, ready

from app.db.models import Base
from app.db.session import database_engine
from app.execution.models import FillSettings, PositionStatus, RiskSettings
from app.wallet.contracts import WalletSettings
from app.wallet.service import WalletService


def main() -> None:
    action, path = sys.argv[1:]
    engine = database_engine(f"sqlite:///{Path(path).resolve().as_posix()}")
    Base.metadata.create_all(engine)
    wallet = WalletService(
        engine,
        calendar(),
        FillSettings(latency_ms=0, fee_per_order=Decimal("1.25")),
        RiskSettings(max_trade_loss_pct=Decimal(20)),
        settings=WalletSettings(initial_capital=Decimal(100000)),
    )
    if action == "crash":
        wallet.initialize(NOW)
        identity, _ = opened(wallet)
        assert wallet.snapshot().positions[identity].status == PositionStatus.OPEN
        # Deliberate ungraceful termination: no Python finally/engine disposal.
        os._exit(71)
    book = wallet.snapshot()
    assert len(book.positions) == 1
    position = next(iter(book.positions.values()))
    assert position.status == PositionStatus.OPEN
    identity, plan = position.id, position.plan
    before_fills = sum(order.fill is not None for order in position.orders.values())
    assert before_fills == 2
    duplicate = wallet.enter(position.decision_id, plan, NOW, ready(), prices(plan))
    assert duplicate == identity
    wallet.close(identity, NOW)
    final = drive(wallet, plan, count=10)
    assert final.status == PositionStatus.CLOSED
    after = wallet.snapshot()
    assert len(after.positions) == 1 and after.reserved == 0
    assert len(after.ledger) == len({entry.key for entry in after.ledger})
    net = final.gross - final.costs
    assert after.balance == Decimal(100000) + net
    print(
        json.dumps(
            {
                "evidence": "SYNTHETIC_PROCESS_CRASH",
                "positions": 1,
                "entry_fills": before_fills,
                "final_fills": sum(
                    order.fill is not None for order in final.orders.values()
                ),
                "balance": str(after.balance),
                "net": str(net),
                "reserved": str(after.reserved),
                "ledger_entries": len(after.ledger),
            }
        )
    )
    engine.dispose()


if __name__ == "__main__":
    main()
