from agent_types import UsageStats, UsageTotals


def test_usage_totals_adds_available_counts():
    totals = UsageTotals()

    totals.add(UsageStats(prompt_tokens=10, response_tokens=5))
    totals.add(UsageStats(prompt_tokens=3, response_tokens=2))

    assert totals.prompt_tokens == 13
    assert totals.response_tokens == 7
    assert totals.total_tokens == 20
    assert totals.has_usage is True


def test_usage_totals_ignores_missing_usage():
    totals = UsageTotals()

    totals.add(None)
    totals.add(UsageStats(prompt_tokens=None, response_tokens=None))

    assert totals.prompt_tokens == 0
    assert totals.response_tokens == 0
    assert totals.total_tokens == 0
    assert totals.has_usage is False
