#!/usr/bin/env python3
"""Rename the decoded app so it can be installed alongside the original.

Changes only what Android requires to be unique across installed apps:
  * the manifest `package` attribute        -> de.spiegel.android.app.spon.noads
  * every ContentProvider authority          -> .noads. variant
  * the custom signature permission          -> .noads. variant
  * the launcher label                       -> "SPON no Ads"

Component class names (android:name="de.spiegel.android.app.spon.activities....")
are deliberately left alone: they are Java class names, not the package id, and
the manifest uses no relative ".Name" forms.

Idempotent: re-running on an already renamed tree is a no-op.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "apktool_out" / "AndroidManifest.xml"
STRINGS = ROOT / "apktool_out" / "res" / "values" / "strings.xml"

OLD_PKG = "de.spiegel.android.app.spon"
NEW_PKG = "de.spiegel.android.app.spon.noads"
NEW_LABEL = "SPON no Ads"
PERM = "DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"


def patch_manifest() -> None:
    text = MANIFEST.read_text()
    if f'package="{NEW_PKG}"' in text:
        print("AndroidManifest.xml already renamed - skipping")
        return

    before = text

    # 1. the application id itself
    text = text.replace(f'package="{OLD_PKG}"', f'package="{NEW_PKG}"')

    # 2. provider authorities must be globally unique on the device
    text = re.sub(
        r'android:authorities="' + re.escape(OLD_PKG) + r'\.',
        f'android:authorities="{NEW_PKG}.',
        text,
    )

    # 3. a signature permission declared by both apps would clash
    text = text.replace(f"{OLD_PKG}.{PERM}", f"{NEW_PKG}.{PERM}")

    if text == before:
        sys.exit("manifest unchanged - expected patterns not found")
    MANIFEST.write_text(text)
    print(f"AndroidManifest.xml: package -> {NEW_PKG}, authorities + permission renamed")


def patch_strings() -> None:
    text = STRINGS.read_text()
    changed = False

    if f"<string name=\"app_name\">{NEW_LABEL}</string>" not in text:
        text, n = re.subn(
            r'<string name="app_name">[^<]*</string>',
            f'<string name="app_name">{NEW_LABEL}</string>',
            text,
        )
        if n != 1:
            sys.exit(f"expected exactly one app_name string, found {n}")
        changed = True

    # AutoImageContentProvider reads its authority from this string
    old_auth = f"{OLD_PKG}.auto_images"
    new_auth = f"{NEW_PKG}.auto_images"
    if old_auth in text:
        text = text.replace(old_auth, new_auth)
        changed = True

    if changed:
        STRINGS.write_text(text)
        print(f'strings.xml: app_name -> "{NEW_LABEL}", auto_images authority renamed')
    else:
        print("strings.xml already renamed - skipping")


def main() -> None:
    if not MANIFEST.exists():
        sys.exit(f"missing {MANIFEST} - run apktool d first")
    patch_manifest()
    patch_strings()


if __name__ == "__main__":
    main()
