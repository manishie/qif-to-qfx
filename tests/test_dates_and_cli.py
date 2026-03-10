"""Tests for date conversion and single-file CLI mode."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qif_to_qfx import date_to_ofx, main

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


class TestDateConversion:
    def test_four_digit_year(self):
        assert date_to_ofx("01/05/2025") == "20250105"

    def test_two_digit_year_modern(self):
        assert date_to_ofx("02/15/25") == "20250215"

    def test_two_digit_year_1900s(self):
        assert date_to_ofx("06/30/99") == "19990630"


class TestSingleFileMode:
    def test_auto_names_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = fixture("single_txn.qif")
            dst = os.path.join(tmpdir, "test.qif")
            with open(src) as f:
                content = f.read()
            with open(dst, "w") as f:
                f.write(content)
            sys.argv = ["qif_to_qfx.py", dst, "--no-balance"]
            main()
            expected_output = os.path.join(tmpdir, "test-clean.qfx")
            assert os.path.exists(expected_output)


class TestHelpFlag:
    def test_help_flag_shows_usage(self, capsys):
        sys.argv = ["qif-to-qfx", "--help"]
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_h_flag_shows_usage(self, capsys):
        sys.argv = ["qif-to-qfx", "-h"]
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out
