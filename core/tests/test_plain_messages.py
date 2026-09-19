from netra_core.rules.plain_messages import plain_for, _PLAIN


def test_no_unformatted_brackets_in_plain_messages():
    """Ensure no check returns unpopulated template brackets like '{missing}'."""
    test_cases = [
        ("6(1)(e)", "FAIL", "MRP declaration not detected."),
        ("6(1)(e)", "FAIL", "MRP non-compliant — missing statutory phrase 'inclusive of all taxes'."),
        ("6(1)(e)", "FAIL", "MRP non-compliant — missing rupee amount."),
        ("6(1)(e)", "FAIL", "MRP non-compliant — missing 'MRP' / 'Maximum Retail Price' wording."),
        ("6(1)(e)", "FAIL", "MRP declaration not found."),
        ("6(1)(e)", "PASS", "MRP Rs 50.00 inclusive of all taxes."),
        ("13", "FAIL", "Non-standard unit 'gms' used."),
        ("13", "PASS", "Unit spellings are correct."),
        ("6(1)(c)", "FAIL", "Net quantity unit invalid."),
        ("6(1)(d)", "FAIL", "Mfg date missing."),
        ("6(1)(a)", "FAIL", "Address incomplete."),
        ("26", "NA", "Exempt under Rule 26. Package net weight <= 10g."),
    ]
    for rule, status, msg in test_cases:
        res = plain_for(rule, status, msg)
        assert "{" not in res, f"Found unformatted bracket in: {res} for {rule}, {status}, {msg}"
        assert "}" not in res, f"Found unformatted bracket in: {res} for {rule}, {status}, {msg}"
        assert "{missing}" not in res


def test_plain_all_registered_templates_with_empty_message():
    """None of the registered templates should leak raw placeholders with empty msg."""
    for (rule, status) in _PLAIN.keys():
        res = plain_for(rule, status, "")
        assert "{" not in res, f"Raw template placeholder leaked for ({rule}, {status}): {res}"
