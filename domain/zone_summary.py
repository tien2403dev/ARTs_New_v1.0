from dataclasses import dataclass

ZONES = ('A', 'B', 'C', 'D', 'E', 'F')

@dataclass(frozen=True)
class ZoneYieldRow:
    zone: str
    in_qty: int
    fail_qty: int

    @property
    def pass_qty(self):
        return self.in_qty - self.fail_qty

    @property
    def yield_percent(self):
        return self.pass_qty * 100 / self.in_qty if self.in_qty else None

@dataclass(frozen=True)
class ZoneYieldResult:
    eqpid: str | None
    handler: str | None
    rows: list
