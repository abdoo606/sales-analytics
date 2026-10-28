from __future__ import annotations

from datetime import date, timedelta

import pytest

from sales.rfm import Customer, Order, build_customers, cohort_retention, segment_summary

BASE = date(2024, 1, 1)


def make_orders() -> list[Order]:
    orders = []
    # champion: recent, frequent, high value
    for i in range(6):
        orders.append(Order("c1", BASE + timedelta(days=300 + i * 5), 200.0))
    # lost: old and cheap
    orders.append(Order("c2", BASE + timedelta(days=10), 10.0))
    # loyal: middling
    for i in range(4):
        orders.append(Order("c3", BASE + timedelta(days=200 + i * 20), 80.0))
    # new: one recent order
    orders.append(Order("c4", BASE + timedelta(days=352), 50.0))
    return orders


def test_order_parsing():
    order = Order.from_row({"customer_id": "u1", "date": "2024-05-06", "amount": "19.99"})
    assert order.day == date(2024, 5, 6) and order.amount == pytest.approx(19.99)


def test_bad_row_raises_with_context():
    with pytest.raises(ValueError, match="bad order row"):
        Order.from_row({"customer_id": "u1", "date": "06/05/2024", "amount": "1"})


def test_build_customers_aggregates():
    customers = {c.customer_id: c for c in build_customers(make_orders())}
    assert customers["c1"].frequency == 6
    assert customers["c1"].monetary == pytest.approx(1200.0)
    assert customers["c1"].recency_days == 27  # measured from the newest order in the data


def test_scores_are_in_range_and_ranked():
    customers = {c.customer_id: c for c in build_customers(make_orders())}
    for c in customers.values():
        assert all(1 <= s <= 5 for s in (c.r_score, c.f_score, c.m_score))
    assert customers["c1"].m_score > customers["c2"].m_score
    assert customers["c2"].r_score < customers["c1"].r_score  # reverse scoring


def test_small_input_falls_back_to_neutral_scores():
    customers = build_customers([Order("solo", BASE, 10.0)])
    assert customers[0].rfm == "333"


def test_empty_input():
    assert build_customers([]) == []


def test_segments_are_named():
    segments = {c.segment for c in build_customers(make_orders())}
    assert segments <= {"champion", "loyal", "new", "at risk", "lost", "promising"}


def test_segment_summary_shares_sum_to_one():
    summary = segment_summary(build_customers(make_orders()))
    assert sum(v["revenue_share"] for v in summary.values()) == pytest.approx(1.0, abs=0.01)


def test_cohort_retention_shape():
    orders = [
        Order("a", date(2024, 1, 5), 10),
        Order("b", date(2024, 1, 20), 10),
        Order("a", date(2024, 2, 5), 10),
        Order("b", date(2024, 3, 5), 10),
    ]
    retention = cohort_retention(orders)
    assert retention["2024-01"] == [1.0, 0.5, 0.5]


def test_cohort_single_customer():
    assert cohort_retention([Order("a", date(2024, 1, 1), 5)]) == {"2024-01": [1.0]}
