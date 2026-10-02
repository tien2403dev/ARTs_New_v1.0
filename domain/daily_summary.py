from dataclasses import dataclass, field


@dataclass(frozen=True)
class DailyYieldRow:
    date: str
    in_qty: int
    fail_qty: int
    scrap_qty: dict = field(default_factory=dict)

    @property
    def out_qty(self):
        return self.in_qty - self.fail_qty

    @property
    def yield_percent(self):
        return self.out_qty * 100 / self.in_qty if self.in_qty else None

    @property
    def fail_ppm(self):
        return self.fail_qty * 1_000_000 / self.in_qty if self.in_qty else None

    @property
    def scrap_ppm_by_code(self):
        return {code: qty * 1_000_000 / self.in_qty for code, qty in self.scrap_qty.items()} if self.in_qty else {}


@dataclass(frozen=True)
class DailyYieldResult:
    eqpid: str | None
    scrap_codes: list
    rows: list
    handler: str | None = None
