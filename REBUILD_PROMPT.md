# Rebuild prompt: ad-free SPIEGEL app

Paste everything below the line into Claude Code, started in the root of this
repo (the directory holding `patch/`), whenever a new SPIEGEL version is out and
you want a fresh ad-free build on the phone.

It is written as instructions to the agent. It assumes nothing is installed
except `adb`, `curl`, `unzip` and `python3`, and it needs no `sudo`.

---

## Task

Build an ad-free copy of the DER SPIEGEL Android app from the version currently
installed on my phone, name it **SPON no Ads**, and install it **alongside** the
original so both apps coexist. Work through the steps below in order. Verify at
each gate and stop and tell me if a gate fails — do not carry on and hope.

Login, subscription, Play Billing and push are expected to stop working in the
renamed build — that is accepted, so do not try to preserve them and do not stop
to ask about it. The package rename in step 5 is required; never skip it to keep
billing alive.

### Environment facts

- Project dir: the root of this repo (the directory holding `patch/`)
- Phone is connected over network adb; `adb devices` must show one device.
- `sudo` requires a password you do not have → install every tool user-local
  under `~/.local/opt/apktools`. Never use `apt`.
- Original package: `de.spiegel.android.app.spon`
- Patched package: `de.spiegel.android.app.spon.noads`
- Java is NOT on `PATH` by default. Every command that runs a `.jar` must first:
  ```bash
  export JAVA_HOME=$HOME/.local/opt/apktools/jdk
  export PATH=$JAVA_HOME/bin:$PATH
  ```

---

### Step 0 — Tools (skip anything already present)

```bash
mkdir -p ~/.local/opt/apktools && cd ~/.local/opt/apktools

# JDK (Temurin 21) - needed by apktool, jadx and the signer
curl -sL -o jdk.tar.gz "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse"
tar xzf jdk.tar.gz && mv jdk-21* jdk && rm jdk.tar.gz

# apktool, jadx, uber-apk-signer - resolve the latest release URLs first:
#   curl -s https://api.github.com/repos/<repo>/releases/latest
# repos: iBotPeaches/Apktool, skylot/jadx, patrickfav/uber-apk-signer
curl -sL -O  https://github.com/iBotPeaches/Apktool/releases/download/<TAG>/apktool_<VER>.jar
curl -sL -O  https://github.com/patrickfav/uber-apk-signer/releases/download/<TAG>/uber-apk-signer-<VER>.jar
curl -sL -o jadx.zip https://github.com/skylot/jadx/releases/download/<TAG>/jadx-<VER>.zip
mkdir -p jadx && cd jadx && unzip -oq ../jadx.zip && cd .. && rm jadx.zip
```

**Gate:** `java -version`, `java -jar apktool_*.jar --version`, `./jadx/bin/jadx --version`
all print a version. `uber-apk-signer` bundles zipalign, so no Android SDK is needed.

### Step 1 — Pull the current APK off the phone

```bash
adb devices
adb shell pm path --user 0 de.spiegel.android.app.spon
adb pull <the path, minus the "package:" prefix> spon.apk
```

- `--user 0` is required; without it `pm` aborts with
  `SecurityException: Shell does not have permission to access user 11`.
- If `pm path` prints more than one line the app has become a split APK. Pull all
  of them, and say so — the single-APK flow below would then need
  `adb install-multiple` and merged resources.

**Gate:** `unzip -l spon.apk | head` lists `AndroidManifest.xml` and `classes.dex`.

### Step 2 — Decode

```bash
java -jar ~/.local/opt/apktools/apktool_*.jar d spon.apk -o apktool_out -f
grep versionName apktool_out/apktool.yml
```

**Gate:** exit 0, `apktool_out/smali/` exists. Note the version — it goes in the
final report.

### Step 3 — Find the WebViewClient of the main content WebView

The app is a WebView wrapper around spiegel.de. All article ads are ordinary web
requests, so one `shouldInterceptRequest` override kills them. R8 renames that
class on **every** release (it was `ld.n` in 5.3.8), so locate it, never assume it:

```bash
./jadx/bin/jadx -d jadx_out --no-res -j 4 spon.apk      # ~2 min, some errors are normal
grep -n -B4 -A2 'setWebViewClient' \
  jadx_out/sources/de/spiegel/android/app/spon/activities/MainContentActivity.java
```

Read the line `mainContentWebView.setWebViewClient(<var>)` and trace `<var>` back
to its class (e.g. `new ld.n(...)`). That class, in smali path form (`ld/n`), is
the patch target for step 4.

Cross-check with `python3 patch/apply_patch.py --dry-run`, which lists every
class extending `android.webkit.WebViewClient`.

**Gate:** you can name exactly one class, and `apktool_out/smali/<that>.smali` exists.

### Step 4 — Inject the ad blocker and the section hider

```bash
python3 patch/apply_patch.py --client <class, e.g. ld/n>
```

This writes `Lde/spiegel/adblock/Blocker;` and patches the target class twice:

- `shouldInterceptRequest` → empty `WebResourceResponse` for any host in
  `patch/hosts.txt`. Main-frame requests are skipped, so navigation can never break.
- `onPageFinished` → `evaluateJavascript` that hides unwanted sections, using
  `patch/hide.txt` (link substrings, matched against the resolved absolute
  `a.href`) and `patch/hide_titles.txt` (case-insensitive substrings of an
  `h1`–`h4`, hiding the whole `SECTION`). A `MutationObserver` re-runs it as
  SPIEGEL lazy-loads more teasers on scroll.

It also enables `WebView.setWebContentsDebuggingEnabled(true)`, which is what
makes step 9's live inspection possible. The devtools socket is only reachable
over adb, so on a personal phone this is fine — remove that call if you'd rather
not have it.

**Patch only that one class.** Running the script without `--client` patches every
WebViewClient it finds, and that was tried and it broke the app: the content
WebView ended on `about:blank` and the article area rendered empty. If you want
the offline-magazine reader covered too, add it in a *separate* build and verify
it on the device before keeping it.

**Gate:** script prints `patched L<class>;` and wrote the Blocker.

### Step 4b — Mark the build in the toolbar

```bash
python3 patch/add_marker.py
```

Adds a small white `⊘` next to the DER SPIEGEL wordmark so the patched build
is recognisable at a glance. The red header is **native** — the page's own
`<header>` is collapsed to zero height — so this edits
`res/layout/nav_fragment_top_tool_bar.xml`, not the page. The script anchors on
the `@id/top_toolbar_logo` ImageView and stops with an error if the layout has
changed.

### Step 5 — Rename so it installs alongside the original

```bash
python3 patch/rename_package.py
```

Changes only what Android requires to be unique: the manifest `package`, the
three provider authorities, the signature permission, and `app_name` →
"SPON no Ads". Component `android:name` values are left alone — they are Java
class names, and the manifest uses no relative `.Name` forms. If a future
manifest *does* use them, they must be made absolute before the package changes.

**Gate:**
```bash
grep -oE 'package="[^"]*"' apktool_out/AndroidManifest.xml | head -1
grep -oE 'android:authorities="[^"]*"' apktool_out/AndroidManifest.xml | sort -u
grep -E '"app_name"|auto_images_authority' apktool_out/res/values/strings.xml
```
Every authority and the permission must contain `.noads.`; a leftover would fail
installation with `INSTALL_FAILED_CONFLICTING_PROVIDER` or
`INSTALL_FAILED_DUPLICATE_PERMISSION`.

### Step 6 — Build

```bash
java -jar ~/.local/opt/apktools/apktool_*.jar b apktool_out -o spon-noads-unsigned.apk
```

**Gate:** `Built apk into: ...`. A smali syntax error surfaces here — fix it
rather than rebuilding blindly.

### Step 7 — Zipalign + sign

```bash
java -jar ~/.local/opt/apktools/uber-apk-signer-*.jar \
  -a spon-noads-unsigned.apk --allowResign -o signed
```

**Gate:** `sign success` and `signature verified [v1, v2, v3]`. Uses a throwaway
debug key, which is all a sideloaded app needs.

Confirm the patch actually reached the dex:
```bash
cd /tmp && rm -rf vchk && mkdir vchk && cd vchk \
  && unzip -oq <project>/signed/*.apk classes.dex \
  && grep -ac "de/spiegel/adblock/Blocker" classes.dex   # must be 1
```

### Step 8 — Install alongside the original

```bash
adb install -r signed/spon-noads-aligned-debugSigned.apk
adb shell pm list packages --user 0 | grep -i spiegel     # must list BOTH packages
```

Never uninstall `de.spiegel.android.app.spon` — that would wipe the real app's
data (offline library, downloaded audio, settings).

### Step 9 — Verify on the device

**The phone must be awake and unlocked**, or `screencap` returns a black frame and
`dumpsys` reports no resumed activity. Check first:

```bash
adb shell dumpsys window | grep -i isKeyguardShowing    # must be false
```
If it is locked, ask me to unlock it. You cannot get past the PIN.

Then:
```bash
adb logcat -c
adb shell am force-stop de.spiegel.android.app.spon.noads
adb shell monkey -p de.spiegel.android.app.spon.noads -c android.intent.category.LAUNCHER 1
sleep 15
adb logcat -d | grep -iE 'FATAL EXCEPTION' -A5              # must be empty
adb shell dumpsys activity activities | grep topResumedActivity
adb exec-out screencap -p > /tmp/noads.png
```

Open the screenshot and **look at it**. Required:

1. `topResumedActivity` is `...spon.noads/...MainContentActivity`.
2. The homepage shows real headlines — not an empty grey content area. A blank
   content area with the orange header still visible means the patch broke
   rendering; check logcat for the WebView ending on `about:blank`.
3. Open an article and scroll:
   ```bash
   adb shell am start -a android.intent.action.VIEW -d "<a spiegel.de article url>" \
     -n de.spiegel.android.app.spon.noads/de.spiegel.android.app.spon.activities.SplashScreenActivity
   ```
   Text and images render; no ad creatives appear.

**Gate:** all three. If 2 fails, go back to step 4 and reduce the patch scope.

#### Checking the hiding rules against the live page

Do not eyeball this — query the real DOM. The app's markup differs from what
`curl https://www.spiegel.de/` returns, so rules derived from the fetched HTML
can be wrong (in 5.3.8 the headings were literally "SPIEGEL Games" and
"11FREUNDE mit SPIEGEL+ gratis lesen", nothing you could guess).

```bash
PID=$(adb shell pidof de.spiegel.android.app.spon.noads | tr -d '\r')
adb forward tcp:9222 localabstract:webview_devtools_remote_$PID
python3 patch/cdp.py 'JSON.stringify({url:location.href,anchors:document.querySelectorAll("a[href]").length})'
```

`patch/cdp.py` is a dependency-free DevTools client (no websocket package on
this machine). Count what is still visible per pattern:

```bash
python3 patch/cdp.py '
(function(){
 function vis(e){for(var n=e;n;n=n.parentElement){if(n.style&&n.style.display==="none")return false;}return true;}
 var o={};
 ["11freunde.de","spiegel.de/games/","spiegel.de/sport/"].forEach(function(p){
  var a=[].slice.call(document.querySelectorAll("a[href]")).filter(function(x){return (x.href||"").indexOf(p)>=0;});
  o[p]=a.filter(vis).length+"/"+a.length+" visible";});
 return JSON.stringify(o);})()'
```

Every targeted pattern must report `0/N visible`, and a control section such as
`spiegel.de/politik/` must still have visible links. You can also prototype new
rules by running them through `cdp.py` against the live page first — that avoids
a full rebuild per attempt.

Note: `console.log` from the page does **not** reach logcat; the app's
WebChromeClient swallows it. Use `cdp.py`, not console output.

### Step 10 — Report

Tell me: the version built, the class patched, how many hosts are blocked,
whether both packages are installed, and what you saw on screen. Flag anything
you could not verify rather than assuming it works.

---

## Known-good reference (SPIEGEL 5.3.8, built 2026-09-18)

| | |
|---|---|
| Patch target | `ld/n` (`Lld/n;`, super `Lld/d;`) — the `MainContentWebView` client |
| Other WebViewClients present | `ld/d`, `ld/k`, `wc/n`, `a6/z` — **not** patched |
| Hosts blocked | 51, from `patch/hosts.txt` |
| Sections hidden | 7 link patterns + 4 heading patterns (see `patch/hide.txt`, `patch/hide_titles.txt`) |
| Toolbar marker | `⊘` after the logo, via `res/layout/nav_fragment_top_tool_bar.xml` |
| Verified | games 0/26, 11 Freunde 0/23, Sport 0/19, Sportdaten 0/1, Kaufradar 0/12, Lotto 0/4, Glücksspirale 0/4 visible; Politik 38/56 and Kultur 23/28 unaffected; 0 ad iframes |
| Result | homepage + articles render normally, no ads |

The two config files are the source of truth for what gets hidden — read them
rather than this table, which only records what was true at build time. As of
this build they hide: games/quizzes, 11 Freunde, Sport, the Sportdaten nav tab,
Kaufradar, Lotto and Glücksspirale. Still visible on purpose, one line each to
add: Effilee, SPIEGEL Shop, manager magazin, Reisewelt, Streaming-Guide, Abo
promos, Tests.

## What this does not fix

- **An empty grey gap is left where an ad was.** The page reserves the slot and
  blocking the request does not collapse it. Fixing it needs CSS injected into
  the page, but the slot containers are built by JavaScript at runtime, so the
  selectors cannot be read out of the static HTML — they would have to come from
  the live DOM over WebView remote debugging.
- **Push notifications and Play Billing will not work** in the renamed build
  (FCM registration and purchase checks validate package name and signature).
  Untested, but expect them to be dead.
- **No Play Store updates** for the patched app — that is what this prompt is for.
- The Sourcepoint consent CMP is deliberately **not** blocked; blocking it risks
  the page never rendering. So a consent dialog may still appear.

## Maintaining the host list

`patch/hosts.txt` is matched as exact host or any subdomain. To check whether
spiegel.de has added an ad provider:

```bash
curl -sL -A "Mozilla/5.0 (Linux; Android 14) Mobile Safari/537.36" https://www.spiegel.de/ -o /tmp/spon.html
grep -oE 'https?://[a-zA-Z0-9.-]+' /tmp/spon.html | sed 's|https\?://||' | sort -u
```

Add new ad/tracking domains, leave anything `*.spiegel.de` and the CMP alone.
