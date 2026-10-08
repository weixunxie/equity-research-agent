from backend.graph.formatting import fmt_money, fmt_mult, fmt_pct, format_financials, format_peers


def test_scalar_formatters():
    assert fmt_money(5.56e12, "USD") == "USD 5.56T"
    assert fmt_money(-1.2e9) == "-1.20B"
    assert fmt_money(None) == "n/a"
    assert fmt_pct(0.2534) == "25.3%"
    assert fmt_mult(1.954) == "1.95x"
    assert fmt_pct(None) == fmt_mult(None) == "n/a"


def test_format_financials_tolerates_an_empty_payload():
    text = format_financials({})
    assert "n/a" in text and "Quarterly income statement" not in text


def test_format_financials_includes_statement_rows_and_margin():
    fin = {
        "currency": "USD",
        "quarterly": [{"period": "2026-06-30", "revenue": 200e9, "net_income": 50e9}],
    }
    assert "2026-06-30 | USD 200.00B | n/a | n/a | USD 50.00B | 25.0%" in format_financials(fin)


def test_format_peers_adds_subject_and_median_rows():
    fin = {"ticker": "AAA", "valuation": {"trailing_pe": 30.0}}
    peers = {
        "basis": "test",
        "peers": [
            {"ticker": "BBB", "trailing_pe": 10.0},
            {"ticker": "CCC", "trailing_pe": 20.0},
            {"ticker": "DDD", "trailing_pe": None},
        ],
    }
    lines = format_peers(peers, fin).splitlines()
    assert lines[2].startswith("AAA (subject) | n/a | 30.00x")
    assert lines[-1].startswith("Peer median (excl. subject) | n/a | 15.00x")
    assert format_peers({}, fin) == "No peer set available."
