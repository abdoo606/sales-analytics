"""RFM: Recency, Frequency, Monetary value - the classic customer segmentation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from statistics import quantiles


@dataclass(slots=True, frozen=True)
class Order:
    customer_id: str
    day: date
    amount: float

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "Order":
        try:
            return cls(
                customer_id=row["customer_id"].strip(),
                day=datetime.strptime(row["date"].strip(), "%Y-%m-%d").date(),
                amount=float(row["amount"]),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"bad order row {row!r}: {exc}") from exc


@dataclass(slots=True)
class Customer:
    customer_id: str
    recency_days: int
    frequency: int
    monetary: float
    r_score: int = 0
    f_score: int = 0
    m_score: int = 0

    @property
    def rfm(self) -> str:
        return f"{self.r_score}{self.f_score}{self.m_score}"

    @property
    def segment(self) -> str:
        r, f, m = self.r_score, self.f_score, self.m_score
        if r >= 4 and f >= 4 and m >= 4:
            return "champion"
        if r >= 3 and f >= 3:
            return "loyal"
        if r >= 4 and f <= 2:
            return "new"
        if r <= 2 and f >= 3:
            return "at risk"
        if r <= 2 and f <= 2:
            return "lost"
        return "promising"


def _score(value: float, thresholds: list[float], *, reverse: bool = False) -> int:
    """Maps a value to 1-5 using empirical quantiles (reverse for recency)."""
    index = sum(value > t for t in thresholds)
    score = index + 1
    return 6 - score if reverse else score


def build_customers(orders: list[Order], *, as_of: date | None = None) -> list[Customer]:
    if not orders:
        return []
    as_of = as_of or max(o.day for o in orders)
    grouped: dict[str, list[Order]] = {}
    for order in orders:
        grouped.setdefault(order.customer_id, []).append(order)

    customers = [
        Customer(
            customer_id=cid,
            recency_days=(as_of - max(o.day for o in items)).days,
            frequency=len(items),
            monetary=round(sum(o.amount for o in items), 2),
        )
        for cid, items in grouped.items()
    ]
    if len(customers) >= 4:
        r_values = [c.recency_days for c in customers]
        f_values = [c.frequency for c in customers]
        m_values = [c.monetary for c in customers]
        r_bands = quantiles(r_values, n=5)[:4]
        f_bands = quantiles(f_values, n=5)[:4]
        m_bands = quantiles(m_values, n=5)[:4]
        for c in customers:
            c.r_score = _score(c.recency_days, r_bands, reverse=True)
            c.f_score = _score(c.frequency, f_bands)
            c.m_score = _score(c.monetary, m_bands)
    else:
        for c in customers:  # too few customers for quantiles: everyone is average
            c.r_score = c.f_score = c.m_score = 3
    return sorted(customers, key=lambda c: (-c.monetary, c.customer_id))


def segment_summary(customers: list[Customer]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for c in customers:
        bucket = summary.setdefault(c.segment, {"customers": 0, "revenue": 0.0, "avg_recency": 0.0})
        bucket["customers"] += 1
        bucket["revenue"] = round(bucket["revenue"] + c.monetary, 2)
        bucket["avg_recency"] += c.recency_days
    for bucket in summary.values():
        bucket["avg_recency"] = round(bucket["avg_recency"] / bucket["customers"], 1)
        bucket["revenue_share"] = round(
            bucket["revenue"] / sum(b["revenue"] for b in summary.values()), 3
        )
    return dict(sorted(summary.items(), key=lambda kv: -kv[1]["revenue"]))


def cohort_retention(orders: list[Order]) -> dict[str, list[float]]:
    """For each signup month, the share of customers who ordered again in later months."""
    first_seen: dict[str, date] = {}
    for order in sorted(orders, key=lambda o: o.day):
        first_seen.setdefault(order.customer_id, order.day)
    cohorts: dict[str, set[str]] = {}
    for cid, day in first_seen.items():
        cohorts.setdefault(day.strftime("%Y-%m"), set()).add(cid)

    activity: dict[str, dict[str, set[str]]] = {}
    for order in orders:
        month = order.day.strftime("%Y-%m")
        activity.setdefault(month, set()).add(order.customer_id)

    retention: dict[str, list[float]] = {}
    for cohort, members in sorted(cohorts.items()):
        months = sorted(activity)
        start = months.index(cohort)
        row = []
        for month in months[start:]:
            active = len(members & activity.get(month, set()))
            row.append(round(active / len(members), 2))
        retention[cohort] = row
    return retention
