#!/usr/bin/env python3
"""
QIF → Clean QFX Converter for Quicken Mac Import

Solves common problems with QIF exports from financial services (PayPal,
banks, etc.) that make them unusable for direct Quicken Mac import:

1. SPLITS: Strips $0 "Fee" split lines that cause Quicken to show "Split"
2. BALANCE: Optionally generates offsetting entries so the file nets to zero
3. HEADER: Adds missing !Account header block if absent
4. FORMAT: Outputs QFX (Web Connect) so Quicken can import into existing accounts

Usage:
    python3 qif_to_qfx.py input.qif [output.qfx] [--no-balance] [--org NAME]

Options:
    --no-balance    Skip auto-balancing (use if source already balances to zero)
    --org NAME      Set the institution name in the QFX header (default: Import)
    --acctid ID     Set the account identifier. Defaults to "{org} - Import"
                    when --org is set, otherwise "Import".

If output is omitted, writes to input-clean.qfx in the same directory.
"""

import sys
import os
import hashlib
import re
import tempfile
import zipfile
from datetime import datetime


# ── QIF Parsing ──────────────────────────────────────────────────────────────

def ensure_account_header(content):
    """Ensure QIF file has an account header block.
    Some QIF exports omit this, but Quicken needs it for import."""
    if content.lstrip().startswith("!Account"):
        return content
    header = "!Account\nNImport\nTCash\n^\n"
    print("  Added missing !Account header")
    return header + content


def parse_qif(filepath):
    """Parse a QIF file into a list of transaction dicts.
    Automatically strips split lines (S/$ prefixed)."""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    if "!Type:Invst" in content:
        print("Error: Investment QIF files (!Type:Invst) are not yet supported. "
              "This tool handles banking and credit card transactions only.",
              file=sys.stderr)
        sys.exit(1)

    # Strip non-transaction sections before parsing
    content = re.sub(
        r"(?m)^(!Type:(?:Cat|Class|Memorized)\b.*?)(?=^!Type:|^!Account|\Z)",
        "", content, flags=re.DOTALL
    )

    content = ensure_account_header(content)

    # Split on ^ (standard) or blank lines (Chase-style)
    after_header = content.split("!Type:", 1)[-1] if "!Type:" in content else content
    if "^\n" in after_header or after_header.rstrip().endswith("^"):
        blocks = content.split("^\n")
    else:
        blocks = re.split(r"\n\n+", content)
    txns = []

    for block in blocks:
        lines = block.strip().split("\n")
        t = {}
        for line in lines:
            if not line:
                continue
            code, val = line[0], line[1:]
            if code == "D":
                t["date"] = val
            elif code == "T":
                try:
                    t["amount"] = float(val.replace(",", ""))
                except ValueError:
                    pass
            elif code == "L":
                t["category"] = val
            elif code == "P":
                t["payee"] = val
            elif code == "M":
                t["memo"] = val
            # S and $ lines (splits) are silently skipped
        if "amount" in t and "date" in t:
            txns.append(t)

    return txns


def parse_qif_files(filepaths):
    """Parse multiple QIF/ZIP files and return deduplicated transactions."""
    all_txns = []
    for path in filepaths:
        if path.lower().endswith(".zip"):
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(path) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".qif"):
                            zf.extract(name, tmpdir)
                            all_txns.extend(parse_qif(os.path.join(tmpdir, name)))
        else:
            all_txns.extend(parse_qif(path))
    return deduplicate_transactions(all_txns)


# ── Deduplication ────────────────────────────────────────────────────────────

def deduplicate_transactions(txns):
    """Remove duplicate transactions based on date + amount + payee."""
    seen = set()
    result = []
    for t in txns:
        key = (t["date"], t["amount"], t.get("payee", ""))
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result


# ── Balancing ────────────────────────────────────────────────────────────────

def balance_transactions(txns):
    """Add offsetting entries so the file nets to zero.

    Some QIF exports (especially PayPal) are inconsistent about including
    both sides of each transaction. This matches debits to credits by
    date+amount, then generates balancing entries for anything unmatched."""
    debits = [(i, t) for i, t in enumerate(txns) if t["amount"] < 0]
    credits = [(i, t) for i, t in enumerate(txns) if t["amount"] > 0]

    used_credits = set()
    unmatched_debits = []

    for _, d in debits:
        matched = False
        for j, (ci, c) in enumerate(credits):
            if ci in used_credits:
                continue
            if d.get("date") == c.get("date") and abs(d["amount"] + c["amount"]) < 0.01:
                used_credits.add(ci)
                matched = True
                break
        if not matched:
            unmatched_debits.append(d)

    unmatched_credits = [c for ci, c in credits if ci not in used_credits]

    generated = []
    for d in unmatched_debits:
        generated.append({
            "date": d["date"],
            "amount": abs(d["amount"]),
            "category": "General Card Deposit",
            "payee": "",
            "memo": d.get("memo", ""),
        })
    for c in unmatched_credits:
        generated.append({
            "date": c["date"],
            "amount": -c["amount"],
            "category": "General Card Withdrawal",
            "payee": "",
            "memo": c.get("memo", ""),
        })

    return txns + generated


# ── QFX Output ───────────────────────────────────────────────────────────────

def date_to_ofx(date_str):
    """Convert MM/DD/YYYY to YYYYMMDD."""
    parts = date_str.split("/")
    if len(parts) == 3:
        mm, dd, yy = parts
        if len(yy) == 2:
            yy = "20" + yy if int(yy) < 50 else "19" + yy
        return f"{yy}{mm.zfill(2)}{dd.zfill(2)}"
    return date_str


def make_fitid(txn, index):
    """Generate a unique, deterministic FITID for dedup across imports."""
    raw = f"{txn['date']}|{txn['amount']:.2f}|{txn.get('payee', '')}|{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:24]


def escape_ofx(s):
    """Escape special characters for OFX/SGML."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_qfx(txns, filepath, account_id="Import", org="Import"):
    """Write transactions as a Quicken-compatible QFX file.

    Uses INTU.BID 10898 (Chase) which is a known-working Web Connect
    partner. On import, Quicken will ask which account to link to."""
    ofx_dates = [date_to_ofx(t["date"]) for t in txns]
    dt_start = min(ofx_dates)
    dt_end = max(ofx_dates)
    dt_server = datetime.now().strftime("%Y%m%d%H%M%S")
    balance = sum(t["amount"] for t in txns)

    trn_lines = []
    for i, t in enumerate(txns):
        payee = escape_ofx(t.get("payee", "").strip() or t.get("category", "Unknown"))
        memo = escape_ofx(t.get("memo", "").strip())
        fitid = make_fitid(t, i)
        ofx_date = date_to_ofx(t["date"])
        ttype = "CREDIT" if t["amount"] > 0 else "DEBIT"

        trn = f"""<STMTTRN>
<TRNTYPE>{ttype}
<DTPOSTED>{ofx_date}
<TRNAMT>{t['amount']:.2f}
<FITID>{fitid}
<NAME>{payee[:32]}"""
        if memo:
            trn += f"\n<MEMO>{memo[:255]}"
        trn += "\n</STMTTRN>"
        trn_lines.append(trn)

    qfx = f"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>{dt_server}
<LANGUAGE>ENG
<FI>
<ORG>{org}
<FID>10898
</FI>
<INTU.BID>10898
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>0
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<BANKID>10898
<ACCTID>{account_id}
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>{dt_start}000000
<DTEND>{dt_end}235959
{chr(10).join(trn_lines)}
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>{balance:.2f}
<DTASOF>{dt_end}235959
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(qfx)


# ── Interactive Mode ─────────────────────────────────────────────────────────

def scan_downloads(directory=None):
    """Scan a directory for .qif and .zip files, return sorted list of paths."""
    if directory is None:
        directory = os.path.expanduser("~/Downloads")
    if not os.path.isdir(directory):
        return []
    results = []
    for name in os.listdir(directory):
        if name.lower().endswith((".qif", ".zip")):
            results.append(os.path.join(directory, name))
    return sorted(results, key=lambda p: os.path.getmtime(p), reverse=True)


def interactive_mode(scan_dir=None, input_fn=None):
    """Interactive file selection and conversion. Returns config dict or None."""
    if input_fn is None:
        input_fn = input

    files = scan_downloads(scan_dir)
    if not files:
        print("No .qif or .zip files found in ~/Downloads.")
        return None

    print("\nFound files:")
    for i, f in enumerate(files, 1):
        size = os.path.getsize(f)
        name = os.path.basename(f)
        print(f"  {i}. {name} ({size:,} bytes)")

    selection = input_fn("\nSelect files (comma-separated numbers, or 'all'): ").strip()
    if selection.lower() == "all":
        chosen = files
    else:
        indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip().isdigit()]
        chosen = [files[i] for i in indices if 0 <= i < len(files)]

    if not chosen:
        print("No files selected.")
        return None

    print("\nSource type:")
    print("  1. PayPal (auto-balance enabled)")
    print("  2. Bank (no balancing)")
    print("  3. Other (no balancing)")
    source = input_fn("\nSelect source [1/2/3]: ").strip()

    source_map = {"1": ("PayPal", False), "2": ("Bank", True), "3": ("Import", True)}
    org, no_balance = source_map.get(source, ("Import", True))

    if len(chosen) == 1:
        base = os.path.splitext(chosen[0])[0]
        output_path = base + "-clean.qfx"
    else:
        directory = os.path.dirname(chosen[0])
        output_path = os.path.join(directory, f"{org}-combined.qfx")

    parts = ["qif-to-qfx"]
    for f in chosen:
        parts.append(f'"{f}"' if " " in f else f)
    if len(chosen) > 1:
        parts.extend(["-o", f'"{output_path}"' if " " in output_path else output_path])
    parts.extend(["--org", org])
    if no_balance:
        parts.append("--no-balance")

    print(f"\nCommand:\n  {' '.join(parts)}")
    print(f"Output:  {output_path}")

    confirm = input_fn("\nProceed? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        print("Cancelled.")
        return None

    return {
        "input_paths": chosen,
        "output_path": output_path,
        "org": org,
        "no_balance": no_balance,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

USAGE = "Usage: qif-to-qfx input1.qif [input2.qif ...] [-o output.qfx] [--no-balance] [--org NAME] [--acctid ID]"


def print_usage():
    print(USAGE)
    print("\nRun with no arguments for interactive mode.")


def main():
    # Parse args (simple, no argparse dependency)
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_usage()
        sys.exit(0)

    # Hidden test flag for interactive scan directory
    scan_dir = None
    if "--interactive-scan-dir" in args:
        idx = args.index("--interactive-scan-dir")
        scan_dir = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    # No args (or only --interactive-scan-dir): interactive mode
    if len(args) < 1:
        config = interactive_mode(scan_dir=scan_dir)
        if config is None:
            sys.exit(0)
        args = config["input_paths"][:]
        if config["no_balance"]:
            args.append("--no-balance")
        args.extend(["--org", config["org"]])
        if len(config["input_paths"]) > 1:
            args.extend(["-o", config["output_path"]])

    no_balance = "--no-balance" in args
    if no_balance:
        args.remove("--no-balance")

    org = "Import"
    if "--org" in args:
        idx = args.index("--org")
        org = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    acctid = None
    if "--acctid" in args:
        idx = args.index("--acctid")
        acctid = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    if acctid is None:
        acctid = org

    output_path = None
    if "-o" in args:
        idx = args.index("-o")
        output_path = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if len(args) < 1:
        print_usage()
        sys.exit(1)

    input_paths = args

    if len(input_paths) == 1 and output_path is None:
        # Single file: legacy behavior
        base = os.path.splitext(input_paths[0])[0]
        output_path = base + "-clean.qfx"
    elif len(input_paths) == 2 and output_path is None:
        # Two positional args: legacy behavior (input output)
        output_path = input_paths.pop()

    if output_path is None:
        print("Error: -o output.qfx is required when using multiple input files")
        sys.exit(1)

    for p in input_paths:
        print(f"Reading: {p}")
    txns = parse_qif_files(input_paths)
    print(f"  Parsed: {len(txns)} transactions (deduplicated)")

    dates = sorted((t["date"] for t in txns), key=date_to_ofx)
    print(f"  Date range: {dates[0]} – {dates[-1]}")

    debits = sum(t["amount"] for t in txns if t["amount"] < 0)
    credits = sum(t["amount"] for t in txns if t["amount"] > 0)
    net = debits + credits
    print(f"  Debits: ${debits:,.2f}  Credits: ${credits:,.2f}  Net: ${net:,.2f}")

    if no_balance:
        balanced = txns
        print(f"  Balancing: skipped (--no-balance)")
    elif abs(net) < 0.01:
        balanced = txns
        print(f"  Balancing: not needed (already $0.00)")
    else:
        balanced = balance_transactions(txns)
        generated = len(balanced) - len(txns)
        final_net = sum(t["amount"] for t in balanced)
        print(f"  Balancing entries added: {generated}")
        print(f"  Final net: ${final_net:,.2f}")

    write_qfx(balanced, output_path, account_id=acctid, org=org)
    print(f"\nWritten: {output_path}")
    print(f"  Total transactions: {len(balanced)}")
    print(f"\nImport: File → Import → Web Connect (.QFX) → Link to existing account")


if __name__ == "__main__":
    main()
