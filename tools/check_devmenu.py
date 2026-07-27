#!/usr/bin/env python3
"""Cross-check every hardcoded s_DevMenu row index in SMS_GUIMenuSMS.c.

WHY THIS EXISTS
---------------
s_DevMenu is a static array whose row indices are hardcoded in several unrelated places, so
reordering rows means moving ALL of them in lockstep. That has already gone wrong once: a
reorder updated the array and the status paint block but missed the `_switch_flag` indices,
so toggling an autostart flipped the correct flag and painted the indicator on the WRONG
row. It shipped and had to be reverted.

The ad-hoc check written at the time only looked at the paint block, so it printed
"ALL ROWS MATCH" while an entire second consumer was silently wrong. This script exists so
that cannot happen again.

A mismatch is not always cosmetic. m_IconRight is a union in practice: MENU_ITEM_TYPE_TEXT
rows hold a STRING POINTER, plain rows hold a GUICON_* id. Writing an id into a text row --
or a pointer into an icon row -- corrupts the redraw.

The file is compiled twice (BDM=1 and BDM=0) with two DIFFERENT array layouts, so the
indices are only meaningful per build. This script evaluates #ifdef BDM / #else / #endif and
checks each build against its own array.

WHAT IT CHECKS, per build
-------------------------
1. handler->row binding: a handler registered at row N must write row N. This is the check
   that would have caught the shipped bug.
2. type agreement: GUICON_* only into plain rows, string pointers only into TEXT rows.
3. range: every index lies inside that build's array.
4. coverage: every row carrying an indicator is painted by the status block.

Run from anywhere:  python tools/check_devmenu.py
Exit status 0 when consistent, 1 otherwise, so it can gate a build.
"""

import io
import os
import re
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "SMS_GUIMenuSMS.c")


def preprocess(text, bdm):
    """Resolve #ifdef BDM / #ifndef BDM / #else / #endif for one build.

    Blank out excluded lines rather than deleting them so reported line numbers stay true.
    Unrelated #ifdefs are left alone; only the BDM condition is evaluated.
    """
    out, stack = [], []          # stack of (is_bdm_cond, currently_emitting)
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"#\s*if(n?)def\s+BDM\b", s)
        if m:
            stack.append((True, bdm if not m.group(1) else not bdm))
            out.append("")
            continue
        if re.match(r"#\s*if(n?)def\b", s) or re.match(r"#\s*if\b", s):
            stack.append((False, True))
            out.append(line)
            continue
        if re.match(r"#\s*else\b", s) and stack:
            is_bdm, emit = stack[-1]
            stack[-1] = (is_bdm, (not emit) if is_bdm else emit)
            out.append("" if is_bdm else line)
            continue
        if re.match(r"#\s*endif\b", s) and stack:
            is_bdm, _ = stack.pop()
            out.append("" if is_bdm else line)
            continue
        out.append(line if all(e for _, e in stack) else "")
    return "\n".join(out)


def parse_array(text):
    """Return [(index, str_name, is_text_row, handler)] for the one visible s_DevMenu."""
    m = re.search(r"static GUIMenuItem s_DevMenu\[\s*\d+\s*\][^=]*=\s*\{", text)
    if not m:
        return None
    body = text[m.end():]
    body = body[: body.index("\n};")]
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        rm = re.match(
            r"\{\s*([A-Za-z_0-9]*)\s*,\s*&STR_(\w+)\s*,[^,]*,[^,]*,\s*([A-Za-z_0-9]+)", line)
        if rm:
            rows.append((len(rows), rm.group(2), rm.group(1) == "MENU_ITEM_TYPE_TEXT", rm.group(3)))
    return rows


def func_spans(text):
    """Map function name -> (start, end) of its body, for the visible build."""
    spans = {}
    for m in re.finditer(r"static void (_\w+)\s*\(\s*GUIMenu\s*\*[^)]*\)\s*\{", text):
        name, depth, i = m.group(1), 1, m.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        spans[name] = (m.end(), i)
    return spans


def is_pointer_rhs(rhs):
    """True when the value assigned to m_IconRight is a string pointer, not a GUICON id."""
    if "GUICON_" in rhs:
        return False
    return bool(re.search(r"&STR_|s_Speeds|&sl_|\)\s*l[A-Z]\w*", rhs)) or rhs.strip().startswith("lStr")


def audit(text, label):
    rows = parse_array(text)
    if not rows:
        return [f"{label}: could not parse s_DevMenu"], 0, []
    by_index = {i: r for i, r in enumerate(rows)}
    handler_rows = {}
    for i, nm, t, h in rows:
        handler_rows.setdefault(h, []).append(i)

    errs, checked = [], 0
    spans = func_spans(text)

    for hname, (s, e) in spans.items():
        if hname not in handler_rows:
            continue
        owned, body = handler_rows[hname], text[s:e]

        for m in re.finditer(r"_switch_flag\s*\(\s*apMenu\s*,\s*(\d+)\s*,[^;]*?(SMS_\w+)\s*\)", body):
            idx, flag = int(m.group(1)), m.group(2)
            checked += 1
            if idx not in by_index:
                errs.append(f"{label}: {hname} _switch_flag row {idx} out of range")
            elif idx not in owned:
                errs.append(f"{label}: {hname} sits at row(s) {owned} but _switch_flag writes "
                            f"row {idx} ({by_index[idx][1]}) with {flag}")
            elif by_index[idx][2]:
                errs.append(f"{label}: {hname} _switch_flag puts a GUICON into TEXT row "
                            f"{idx} ({by_index[idx][1]}) -- crash risk")

        for m in re.finditer(r"s_DevMenu\[\s*(\d+)\s*\]\.m_IconRight\s*=\s*([^;]+);", body):
            idx, rhs = int(m.group(1)), m.group(2)
            checked += 1
            if idx not in by_index:
                errs.append(f"{label}: {hname} writes row {idx}, out of range")
                continue
            _, nm, is_text, _ = by_index[idx]
            if idx not in owned:
                errs.append(f"{label}: {hname} sits at row(s) {owned} but writes row {idx} ({nm})")
            elif is_pointer_rhs(rhs) != is_text:
                kind = "pointer" if is_pointer_rhs(rhs) else "GUICON"
                errs.append(f"{label}: {hname} writes a {kind} into "
                            f"{'TEXT' if is_text else 'plain'} row {idx} ({nm}) -- crash risk")

    # status paint block
    painted = {}
    if "_device_handler" in spans:
        s, e = spans["_device_handler"]
        for m in re.finditer(r"s_DevMenu\[\s*(\d+)\s*\]\.m_IconRight\s*=\s*([^;]+);", text[s:e]):
            painted[int(m.group(1))] = m.group(2)
            checked += 1
    else:
        errs.append(f"{label}: _device_handler not found")

    for idx, rhs in painted.items():
        if idx not in by_index:
            errs.append(f"{label}: status block writes row {idx}, out of range")
            continue
        _, nm, is_text, _ = by_index[idx]
        if is_pointer_rhs(rhs) != is_text:
            kind = "pointer" if is_pointer_rhs(rhs) else "GUICON"
            errs.append(f"{label}: status block writes a {kind} into "
                        f"{'TEXT' if is_text else 'plain'} row {idx} ({nm}) -- crash risk")

    for i, nm, t, h in rows:
        if i not in painted and h in handler_rows and h != "_network_handler":
            errs.append(f"{label}: row {i} ({nm}) is never painted by the status block")

    return errs, checked, rows


def main():
    raw = io.open(SRC, encoding="latin-1").read()
    all_errs, grand = [], 0

    for label, bdm in (("BDM=1", True), ("BDM=0", False)):
        text = preprocess(raw, bdm)
        errs, checked, rows = audit(text, label)
        print(f"\n=== {label} : {len(rows)} static rows, {checked} indexed writes checked ===")
        for i, nm, t, h in rows:
            mark = "TEXT" if t else "icon"
            print(f"  {i:2d}  {mark}  {nm:<24} {h}")
        all_errs += errs
        grand += checked

    print(f"\ncross-checked {grand} indexed writes across both builds")
    if all_errs:
        print("\nINCONSISTENT:")
        for e in all_errs:
            print("  -", e)
        return 1
    print("CONSISTENT: every handler writes its own row, every type agrees, every row painted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
