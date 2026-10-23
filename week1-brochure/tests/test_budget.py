import random

import pytest

from week1_brochure.budget import Source, allocate, build_context


@pytest.mark.parametrize(
    ("sizes", "budget", "expected"),
    [
        ([10, 20], 100, [10, 20]),  # everything fits
        ([100, 100, 100], 150, [50, 50, 50]),  # equal split
        ([10, 1000, 1000], 300, [10, 145, 145]),  # short source keeps all; rest shared
        ([5, 5], 0, [0, 0]),
        ([], 100, []),
    ],
)
def test_allocate(sizes, budget, expected):
    assert allocate(sizes, budget) == expected


def test_allocate_never_exceeds_budget_or_source_size():
    rng = random.Random(7)
    for _ in range(500):
        sizes = [rng.randint(0, 5_000) for _ in range(rng.randint(1, 8))]
        budget = rng.randint(0, 20_000)
        allocation = allocate(sizes, budget)
        assert sum(allocation) <= budget
        assert all(0 <= a <= s for a, s in zip(allocation, sizes, strict=True))


def test_every_page_survives_when_the_landing_page_is_huge(tokenizer, page):
    """Regression test for the course's `prompt[:5_000]`, which drops later pages."""
    sources = [
        Source("Landing page", page("https://acme.test/", "landing " * 10_000)),
        Source("About page", page("https://acme.test/about", "Founded in 2019 in Riyadh.")),
        Source("Careers page", page("https://acme.test/careers", "We are hiring iOS engineers.")),
    ]

    context, reports = build_context(sources, tokenizer, budget=1_000)

    assert "Founded in 2019 in Riyadh." in context
    assert "We are hiring iOS engineers." in context
    assert "## Landing page: https://acme.test/ [truncated]" in context
    assert [r.truncated for r in reports] == [True, False, False]
    assert sum(r.tokens_kept for r in reports) <= 1_000
