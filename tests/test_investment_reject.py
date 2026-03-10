"""Tests for investment QIF rejection."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qif_to_qfx import parse_qif

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestInvestmentRejection:
    def test_rejects_investment_qif(self):
        with pytest.raises(SystemExit) as exc_info:
            parse_qif(os.path.join(FIXTURES, "fidelity_investment.qif"))
        assert exc_info.value.code != 0

    def test_investment_error_message(self, capsys):
        with pytest.raises(SystemExit):
            parse_qif(os.path.join(FIXTURES, "fidelity_investment.qif"))
        captured = capsys.readouterr()
        assert "!Type:Invst" in captured.err
