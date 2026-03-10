# qif-to-qfx

Convert QIF transaction files to QFX (Web Connect) format for import into Quicken and other financial software that supports OFX.

## Claude Code Skill

Install as a [Claude Code](https://claude.ai/download) skill:

```
claude plugin install manishie/qif-to-qfx
```

Then just ask Claude:

> *"Convert my PayPal QIF download to QFX for Quicken."*

Claude will find your QIF files, ask which source they're from, build the right command, and show you how to import the result into Quicken.

## CLI Installation

Also available as a standalone command-line tool:

```bash
pip install qif-to-qfx
```

## Why

Quicken can only import QIF into **new** accounts. To import into an existing account, you need QFX format. This tool converts QIF → QFX in one step, handling common problems along the way:

- **Strips split lines** — PayPal adds $0 "Fee" splits that cause Quicken to show "Split" instead of the category
- **Auto-balances** — generates offsetting entries so the file nets to $0.00 (needed for PayPal-style exports)
- **Adds missing headers** — some QIF exports omit the `!Account` block Quicken requires
- **Deduplicates** — combine multiple overlapping QIF files without duplicate transactions

## Usage

```bash
# PayPal export (auto-balances unmatched subscriptions)
qif-to-qfx ~/Downloads/Download.QIF ~/Downloads/PayPal.qfx --org PayPal

# Bank export that already balances
qif-to-qfx ~/Downloads/Bank.qif --no-balance --org "My Bank"

# Combine multiple files (deduplicates overlapping transactions)
qif-to-qfx jan.QIF feb.QIF mar.QIF -o combined.qfx --org PayPal

# Zip file containing QIF exports
qif-to-qfx ~/Downloads/exports.zip -o combined.qfx --org PayPal
```

## Options

| Flag | Description |
|------|-------------|
| `-o FILE` | Output path (required for multiple inputs) |
| `--no-balance` | Skip auto-balancing |
| `--org NAME` | Institution name in QFX header (default: "Import") |
| `--acctid ID` | Account identifier (defaults to `--org` value) |

If `-o` is omitted with a single input, writes to `<input>-clean.qfx`.

## Import into Quicken

1. **File → Import → Web Connect (.QFX)**
2. Change Action to **"Link to existing account"**
3. Select the target account
4. Accept All

## Tested With

- **PayPal** QIF exports (handles double-entry balancing, subscription mismatches)
- **Chase** QIF exports (blank-line separators, CCard type)
- **Quicken Mac** import (QFX/Web Connect)

Should work with any QIF source. [Open an issue](https://github.com/manishie/qif-to-qfx/issues) if you find one that doesn't.

## Requirements

Python 3.6+. No external dependencies.

## Author

[Manish Mukherjee](https://mukherjee.me)

## License

MIT
