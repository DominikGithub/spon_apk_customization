#!/usr/bin/env python3
"""Put a small marker next to the DER SPIEGEL wordmark in the top toolbar,
so the patched build is recognisable at a glance.

The red header is native (the page's own <header> is collapsed to zero height),
so this edits the toolbar layout rather than injecting anything into the page.

Idempotent: re-running on an already patched tree is a no-op.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LAYOUT = ROOT / "apktool_out" / "res" / "layout" / "nav_fragment_top_tool_bar.xml"

MARKER_ID = "spon_noads_marker"
# U+2298 CIRCLED DIVISION SLASH - reads as "no ads" and is in the stock font.
MARKER_TEXT = "&#8856;"

ANCHOR = '<ImageView android:layout_gravity="start" android:id="@id/top_toolbar_logo"'

MARKER = (
    '    <TextView android:layout_gravity="start" '
    'android:layout_width="wrap_content" android:layout_height="wrap_content" '
    f'android:text="{MARKER_TEXT}" '
    'android:textColor="#ffffffff" android:textSize="13.0sp" '
    'android:alpha="0.85" android:layout_marginStart="7.0dp" '
    f'android:contentDescription="{MARKER_ID}" />\n'
)


def main() -> None:
    if not LAYOUT.exists():
        sys.exit(f"missing {LAYOUT} - run apktool d first")

    text = LAYOUT.read_text(encoding="utf-8")
    if MARKER_ID in text:
        print("toolbar marker already present - skipping")
        return

    idx = text.find(ANCHOR)
    if idx == -1:
        sys.exit("top_toolbar_logo ImageView not found - toolbar layout changed, "
                 "inspect res/layout/nav_fragment_top_tool_bar.xml by hand")

    end = text.find("\n", idx)
    if end == -1:
        sys.exit("malformed layout: no newline after the logo ImageView")

    LAYOUT.write_text(text[: end + 1] + MARKER + text[end + 1:], encoding="utf-8")
    print(f"added '{MARKER_TEXT}' marker after the logo in "
          f"{LAYOUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
