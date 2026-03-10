"""Tests for Chase-style QIF parsing."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qif_to_qfx import parse_qif, write_qfx

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestChaseBlankLineParsing:
    def test_parses_chase_ccard_fixture(self):
        txns = parse_qif(os.path.join(FIXTURES, "chase_ccard.qif"))
        assert len(txns) == 292

    def test_n_field_not_in_payee(self):
        """Chase's NN/A should not appear as payee data."""
        txns = parse_qif(os.path.join(FIXTURES, "chase_ccard.qif"))
        for t in txns:
            assert "N/A" not in t.get("payee", ""), f"N/A found in payee: {t}"

    def test_n_field_not_in_qfx_name(self):
        """The N field should not appear in QFX <NAME> tags."""
        import re as re_mod
        import tempfile
        txns = parse_qif(os.path.join(FIXTURES, "chase_ccard.qif"))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".qfx", delete=False) as f:
            outpath = f.name
        write_qfx(txns, outpath)
        with open(outpath) as f:
            qfx_content = f.read()
        os.unlink(outpath)
        names = re_mod.findall(r"<NAME>(.+)", qfx_content)
        for name in names:
            assert "N/A" not in name, f"N/A leaked into QFX NAME: {name}"
