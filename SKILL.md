---
name: qif-to-qfx
description: Convert QIF files to QFX format for Quicken import. Handles PayPal balancing, split stripping, deduplication, and multi-file combine.
---

# QIF → QFX Converter for Quicken

## When to use

- Convert QIF exports (PayPal, banks, any financial service) to QFX for Quicken Mac import
- Clean up splits, balance issues, or missing headers in QIF files

## Entry Point

Guide the user through conversion interactively.

1. **Find files.** Run `bash {skill_dir}/find-qif-files.sh` (scans `~/Downloads` for `*.qif`, `*.QIF`, `*.zip`). Output: `ext|size|date|path` per file, or `NO_FILES`. Also check user-provided paths.

2. **Present files.** AskUserQuestion with multiSelect, one option per file. If `NO_FILES`, ask for a path.

3. **Ask source.** AskUserQuestion: "PayPal" (auto-balance on), "Bank" (no balance, ask bank name for `--org`), or "Other".

4. **Build command.** Show full command. Multi-file: `-o ~/Downloads/{source}-combined.qfx`. Single: auto-names. Confirm before running.

5. **Run.** `python3 {skill_dir}/qif_to_qfx.py {args}`

6. **Show results.** Display output, then: "**To import:** File → Import → Web Connect (.QFX) → Link to existing account → select account → Accept All"

### Rules
- Always show command before running
- Combine multiple files from same source with `-o`
- If user provided a path as argument, skip file discovery

---

## CLI Reference

```bash
python3 qif_to_qfx.py <input.qif> [output.qfx] [--no-balance] [--org NAME] [--acctid ID]
python3 qif_to_qfx.py <a.qif> <b.qif> -o <output.qfx> [--no-balance] [--org NAME]
python3 qif_to_qfx.py <exports.zip> -o <output.qfx> [--no-balance] [--org NAME]
```

- `-o FILE` — Output path. Required for multi-file, optional for single.
- `--no-balance` — Skip auto-balancing.
- `--org NAME` — Institution name in QFX header (default: "Import").
- `--acctid ID` — Account identifier (default: same as `--org`).

Multi-file deduplicates on date+amount+payee. Zip files auto-extracted.

## Source-Specific Notes

**PayPal:** Double-entry structure — auto-balance fixes unmatched subscriptions. Max 12 months per download; use multi-file mode for longer periods.

**Banks:** Single-entry, use `--no-balance`. Chase QIF uses blank-line separators and `!Type:CCard` — handled automatically.

**Investment (`!Type:Invst`):** Not supported — detected and rejected with error.

## Technical Notes

- Python 3.6+, no dependencies
- INTU.BID 10898 (Chase) used as Web Connect partner — cosmetic only
- FITIDs are deterministic (MD5 of date+amount+payee+index) — re-import won't duplicate
- Strips `!Type:Cat`, `!Type:Class`, `!Type:Memorized` metadata sections
- QFX doesn't support categories — Quicken uses its own renaming rules

## Troubleshooting

- **"Unable to verify financial institution"** — Quicken needs internet for INTU.BID validation
- **Balance not zero** — check for overlapping date ranges in multi-file input
- **Wrong account balance** — user must select "Link to existing account", not "Add"
