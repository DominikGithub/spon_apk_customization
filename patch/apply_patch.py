#!/usr/bin/env python3
"""Inject a WebView ad-blocker and section-hider into the decoded SPIEGEL APK.

Adds Lde/spiegel/adblock/Blocker; and, in the targeted WebViewClient:
  * shouldInterceptRequest(...)  -> empty response for hosts in hosts.txt
  * onPageFinished(...)          -> injects JS that hides teasers whose link
                                    matches a pattern in hide.txt

The target classes are DISCOVERED, not hardcoded: R8 renames them on every
SPIEGEL release (they were Lld/n; and Lld/d; in 5.3.8), so this walks the
decoded smali and finds whatever now extends android.webkit.WebViewClient.

Usage:
    python3 patch/apply_patch.py                 # detect and patch
    python3 patch/apply_patch.py --dry-run       # just list what it would patch
    python3 patch/apply_patch.py --client ld/n   # force a specific class

Idempotent: re-running on an already patched tree is a no-op.
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
APKTOOL_OUT = ROOT / "apktool_out"

WEBVIEWCLIENT = "Landroid/webkit/WebViewClient;"

# Third-party code we must not touch: their own WebViewClients belong to the
# ads/analytics SDKs and to AndroidX, and patching them buys nothing.
SKIP_PREFIXES = ("com/google/", "org/chromium/", "androidx/", "kotlin/", "kotlinx/")

BLOCKER_TMPL = """.class public final Lde/spiegel/adblock/Blocker;
.super Ljava/lang/Object;


# static fields
.field private static final HOSTS:[Ljava/lang/String;


# direct methods
.method static constructor <clinit>()V
    .locals 2

    const-string v0, "%(hosts)s"

    const-string v1, ","

    invoke-virtual {v0, v1}, Ljava/lang/String;->split(Ljava/lang/String;)[Ljava/lang/String;

    move-result-object v0

    sput-object v0, Lde/spiegel/adblock/Blocker;->HOSTS:[Ljava/lang/String;

    return-void
.end method

.method public static blank()Landroid/webkit/WebResourceResponse;
    .locals 4

    new-instance v0, Ljava/io/ByteArrayInputStream;

    const/4 v1, 0x0

    new-array v1, v1, [B

    invoke-direct {v0, v1}, Ljava/io/ByteArrayInputStream;-><init>([B)V

    new-instance v2, Landroid/webkit/WebResourceResponse;

    const-string v3, "text/plain"

    const-string v1, "utf-8"

    invoke-direct {v2, v3, v1, v0}, Landroid/webkit/WebResourceResponse;-><init>(Ljava/lang/String;Ljava/lang/String;Ljava/io/InputStream;)V

    return-object v2
.end method

.method public static isAd(Ljava/lang/String;)Z
    .locals 6

    const/4 v0, 0x0

    if-nez p0, :cond_start

    return v0

    :cond_start
    sget-object v1, Lde/spiegel/adblock/Blocker;->HOSTS:[Ljava/lang/String;

    array-length v2, v1

    const/4 v3, 0x0

    :goto_loop
    if-ge v3, v2, :cond_miss

    aget-object v4, v1, v3

    invoke-virtual {p0, v4}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v5

    if-nez v5, :cond_hit

    new-instance v5, Ljava/lang/StringBuilder;

    invoke-direct {v5}, Ljava/lang/StringBuilder;-><init>()V

    const-string v0, "."

    invoke-virtual {v5, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v5, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v5}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    invoke-virtual {p0, v0}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v0

    if-nez v0, :cond_hit

    add-int/lit8 v3, v3, 0x1

    const/4 v0, 0x0

    goto :goto_loop

    :cond_hit
    const/4 v0, 0x1

    return v0

    :cond_miss
    const/4 v0, 0x0

    return v0
.end method

.method public static hide(Landroid/webkit/WebView;)V
    .locals 2

    if-nez p0, :cond_go

    return-void

    :cond_go
    const/4 v1, 0x1

    :try_start_1
    invoke-static {v1}, Landroid/webkit/WebView;->setWebContentsDebuggingEnabled(Z)V
    :try_end_1
    .catch Ljava/lang/Throwable; {:try_start_1 .. :try_end_1} :catch_1

    goto :goto_js

    :catch_1
    move-exception v1

    :goto_js
    const-string v0, "%(js)s"

    const/4 v1, 0x0

    :try_start_0
    invoke-virtual {p0, v0, v1}, Landroid/webkit/WebView;->evaluateJavascript(Ljava/lang/String;Landroid/webkit/ValueCallback;)V
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    return-void

    :catch_0
    move-exception v0

    return-void
.end method
"""

# One line, single quotes only, so it survives as a smali const-string.
HIDE_JS = (
    "(function(){"
    "var P=[%(patterns)s];"
    "var T=[%(titles)s];"
    "function up(n,stop){var e=n,k=0;while(e&&k<10){"
    "if(stop.indexOf(e.tagName)>=0)return e;e=e.parentElement;k++;}return null;}"
    "function h(){var seen=0,hid=0,samp=[];try{"
    # a[i].href resolves relative hrefs to absolute; getAttribute does not.
    "var a=document.querySelectorAll('a[href]');seen=a.length;"
    "for(var i=0;i<a.length;i++){"
    "var u='';try{u=a[i].href||'';}catch(e2){}"
    "if(!u)u=a[i].getAttribute('href')||'';"
    "if(samp.length<12&&i%%25===0)samp.push(u.slice(0,70));"
    "var m=false;"
    "for(var j=0;j<P.length;j++){if(u.indexOf(P[j])>=0){m=true;break;}}"
    "if(!m)continue;"
    "var t=up(a[i],['ARTICLE','SECTION','LI'])||a[i];"
    "if(t&&t!==document.body&&t!==document.documentElement&&t.style.display!=='none'){"
    "t.style.display='none';hid++;}"
    "}"
    # Section headings: hide the whole block a matching heading belongs to.
    "if(T.length){var hs=document.querySelectorAll('h1,h2,h3,h4');"
    "for(var q=0;q<hs.length;q++){"
    "var txt=(hs[q].textContent||'').trim().toLowerCase();"
    "var mt=false;for(var r=0;r<T.length;r++){if(txt.indexOf(T[r])>=0){mt=true;break;}}"
    "if(!mt)continue;"
    "var s=up(hs[q],['SECTION'])||hs[q].parentElement||hs[q];"
    "if(s&&s!==document.body&&s!==document.documentElement&&s.style.display!=='none'){"
    "s.style.display='none';hid++;}"
    "}}"
    "}catch(err){}"
    "try{console.log('SPONHIDE anchors='+seen+' hidden='+hid+' sample='+JSON.stringify(samp));}catch(e3){}}"
    "h();"
    "try{var d;var o=new MutationObserver(function(){clearTimeout(d);d=setTimeout(h,400);});"
    "o.observe(document.documentElement,{childList:true,subtree:true});}catch(err){}"
    "})();"
)

HIDE_CALL = "    invoke-static {p1}, Lde/spiegel/adblock/Blocker;->hide(Landroid/webkit/WebView;)V\n\n"

# Used only if the target class does not already override onPageFinished.
ONPAGEFINISHED_TMPL = """.method public onPageFinished(Landroid/webkit/WebView;Ljava/lang/String;)V
    .locals 0

    invoke-super {p0, p1, p2}, %(super)s->onPageFinished(Landroid/webkit/WebView;Ljava/lang/String;)V

    invoke-static {p1}, Lde/spiegel/adblock/Blocker;->hide(Landroid/webkit/WebView;)V

    return-void
.end method
"""

# %(super)s is the class's own .super, so invoke-super always resolves.
OVERRIDE_TMPL = """.method public shouldInterceptRequest(Landroid/webkit/WebView;Landroid/webkit/WebResourceRequest;)Landroid/webkit/WebResourceResponse;
    .locals 2

    if-eqz p2, :cond_pass

    invoke-interface {p2}, Landroid/webkit/WebResourceRequest;->isForMainFrame()Z

    move-result v1

    if-nez v1, :cond_pass

    invoke-interface {p2}, Landroid/webkit/WebResourceRequest;->getUrl()Landroid/net/Uri;

    move-result-object v0

    if-eqz v0, :cond_pass

    invoke-virtual {v0}, Landroid/net/Uri;->getHost()Ljava/lang/String;

    move-result-object v0

    invoke-static {v0}, Lde/spiegel/adblock/Blocker;->isAd(Ljava/lang/String;)Z

    move-result v1

    if-eqz v1, :cond_pass

    invoke-static {}, Lde/spiegel/adblock/Blocker;->blank()Landroid/webkit/WebResourceResponse;

    move-result-object v0

    return-object v0

    :cond_pass
    invoke-super {p0, p1, p2}, %(super)s->shouldInterceptRequest(Landroid/webkit/WebView;Landroid/webkit/WebResourceRequest;)Landroid/webkit/WebResourceResponse;

    move-result-object v0

    return-object v0
.end method
"""


def smali_roots() -> list[pathlib.Path]:
    """smali/, smali_classes2/, ... - apktool splits multidex across dirs."""
    roots = sorted(p for p in APKTOOL_OUT.glob("smali*") if p.is_dir())
    if not roots:
        sys.exit(f"no smali* dirs under {APKTOOL_OUT} - run apktool d first")
    return roots


def class_index() -> dict[str, tuple[pathlib.Path, str]]:
    """Map every class descriptor -> (file, its .super descriptor)."""
    index: dict[str, tuple[pathlib.Path, str]] = {}
    for root in smali_roots():
        for path in root.rglob("*.smali"):
            head = path.read_text(errors="replace")[:4096]
            m_cls = re.search(r"^\.class[^\n]*?(L[^\s;]+;)", head, re.M)
            m_sup = re.search(r"^\.super\s+(L[^\s;]+;)", head, re.M)
            if m_cls and m_sup:
                index[m_cls.group(1)] = (path, m_sup.group(1))
    return index


def extends_webviewclient(desc: str, index: dict) -> bool:
    """Walk the .super chain up to WebViewClient (guard against cycles)."""
    seen = set()
    while desc in index and desc not in seen:
        seen.add(desc)
        parent = index[desc][1]
        if parent == WEBVIEWCLIENT:
            return True
        desc = parent
    return False


def find_targets(index: dict) -> list[tuple[str, pathlib.Path, str]]:
    targets = []
    for desc, (path, sup) in sorted(index.items()):
        name = desc[1:-1]  # strip L and ;
        if name.startswith(SKIP_PREFIXES):
            continue
        if extends_webviewclient(desc, index):
            targets.append((desc, path, sup))
    return targets


def load_list(filename: str) -> list[str]:
    """Read a config file: one entry per line, '#' comments and blanks dropped."""
    entries = []
    for line in (HERE / filename).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            entries.append(line.lower())
    return entries


def smali_string(value: str) -> str:
    """Escape a Python string for use inside a smali const-string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def js_array(values: list[str]) -> str:
    return ",".join("'" + v.replace("'", "") + "'" for v in values)


def build_hide_js(patterns: list[str], titles: list[str]) -> str:
    return HIDE_JS % {"patterns": js_array(patterns), "titles": js_array(titles)}


def add_hide_call(text: str, desc: str, sup: str) -> tuple[str, str]:
    """Call Blocker.hide(webView) from onPageFinished. Returns (text, what-happened)."""
    if "Lde/spiegel/adblock/Blocker;->hide(" in text:
        return text, "hide() already wired"

    sig = "onPageFinished(Landroid/webkit/WebView;Ljava/lang/String;)V"
    start = text.find(f".method public {sig}")
    if start == -1:
        start = text.find(f".method public final {sig}")
    if start == -1:
        # class inherits onPageFinished - add our own override that calls super
        body = ONPAGEFINISHED_TMPL % {"super": sup}
        if not text.endswith("\n"):
            text += "\n"
        return text + "\n" + body, "added onPageFinished override"

    end = text.find(".end method", start)
    locals_line = re.search(r"^\s*\.locals\s+\d+\s*$", text[start:end], re.M)
    if not locals_line:
        sys.exit(f"{desc}: onPageFinished has no .locals directive - inspect manually")
    insert_at = start + locals_line.end() + 1
    return text[:insert_at] + "\n" + HIDE_CALL + text[insert_at:], "hooked onPageFinished"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="only report targets")
    ap.add_argument("--client", action="append", default=[],
                    help="force a class, e.g. ld/n (repeatable)")
    args = ap.parse_args()

    index = class_index()

    if args.client:
        targets = []
        for c in args.client:
            desc = f"L{c.strip('/')};"
            if desc not in index:
                sys.exit(f"class {desc} not found in decoded smali")
            path, sup = index[desc]
            targets.append((desc, path, sup))
    else:
        targets = find_targets(index)

    if not targets:
        sys.exit("no WebViewClient subclass found - inspect jadx output and use --client")

    print(f"{len(index)} classes scanned, {len(targets)} WebViewClient subclass(es):")
    for desc, path, sup in targets:
        print(f"  {desc:<28} super={sup:<28} {path.relative_to(APKTOOL_OUT)}")

    if args.dry_run:
        return

    hosts = load_list("hosts.txt")
    if not hosts:
        sys.exit("hosts.txt is empty")
    patterns = load_list("hide.txt")
    titles = load_list("hide_titles.txt")

    blocker_dir = smali_roots()[0] / "de" / "spiegel" / "adblock"
    blocker_dir.mkdir(parents=True, exist_ok=True)
    blocker = blocker_dir / "Blocker.smali"
    blocker.write_text(BLOCKER_TMPL % {
        "hosts": smali_string(",".join(hosts)),
        "js": smali_string(build_hide_js(patterns, titles)),
    })
    print(f"\nwrote {blocker.relative_to(ROOT)} "
          f"({len(hosts)} hosts blocked, {len(patterns)} link patterns, "
          f"{len(titles)} section titles)")
    for p in patterns:
        print(f"    hide link: {p}")
    for t in titles:
        print(f"    hide title: {t}")

    for desc, path, sup in targets:
        text = path.read_text()

        if "shouldInterceptRequest" in text:
            print(f"  {desc}: shouldInterceptRequest already present - skipping blocker")
        else:
            if not text.endswith("\n"):
                text += "\n"
            text += "\n" + OVERRIDE_TMPL % {"super": sup}
            print(f"  patched {desc} (super {sup})")

        if patterns:
            text, what = add_hide_call(text, desc, sup)
            print(f"  {desc}: {what}")

        path.write_text(text)


if __name__ == "__main__":
    main()
