"""Tests for skipping non-transaction QIF sections."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qif_to_qfx import parse_qif


class TestNonTransactionSections:
    def test_skips_memorized_section(self):
        """Memorized transactions have D and T fields but should be skipped."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write("!Type:Memorized\nD01/01/2025\nT-100.00\nPOld Rent\n^\n"
                    "!Account\nNChecking\nTBank\n^\n!Type:Bank\nD02/01/2025\nT-100.00\nPRENT\n^\n")
            f.flush()
            txns = parse_qif(f.name)
        os.unlink(f.name)
        assert len(txns) == 1
        assert txns[0]["payee"] == "RENT"

    def test_mixed_metadata_and_transactions(self):
        """File with Cat + Class + Memorized before real transactions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write("!Type:Cat\nNFood\n^\n"
                    "!Type:Class\nNPersonal\n^\n"
                    "!Type:Memorized\nD01/01/2025\nT-50.00\nPOld\n^\n"
                    "!Account\nNChecking\nTBank\n^\n"
                    "!Type:Bank\nD03/01/2025\nT-25.00\nPACTUAL TXN\n^\n")
            f.flush()
            txns = parse_qif(f.name)
        os.unlink(f.name)
        assert len(txns) == 1
        assert txns[0]["payee"] == "ACTUAL TXN"
