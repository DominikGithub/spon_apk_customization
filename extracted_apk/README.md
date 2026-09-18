# `extracted_apk/` — raw contents of the DER SPIEGEL Android app

This folder is a plain `unzip` of `../spon.apk`.

| | |
|---|---|
| Package | `de.spiegel.android.app.spon` |
| Source APK | `../spon.apk` (9.1 MB, single APK — no splits) |

**This is not decompiled code.** An APK is a ZIP, so `unzip` gets you the file
tree — but the code is still Dalvik bytecode, the manifest is binary XML, and the
resources are a compiled blob. See *[How to actually read it](#how-to-actually-read-it)*.

## Where the core code is

All of it is in **`classes.dex`** (9.2 MB). The app's own classes live under the
package **`de/spiegel/android/app/spon/**`**.

`classes2.dex` (468 KB) contains **no app logic** — it is only `java.util` /
`java.lang` desugaring backports emitted by the toolchain. Ignore it.

The app was minified with R8, so only ~70 class names survive in readable form:
those that can't be renamed because the manifest, Room, or WorkManager reference
them by name. Everything else was renamed into short packages (`e7`, `zd`, `q`,
`p5`, `v0`, …). The bulk of `com/**` (≈3800 references) is bundled third-party
libraries, not Spiegel code.

The surviving names map the app out well:

| Package under `de/spiegel/android/app/spon/` | What lives there |
|---|---|
| `application/MainApplication` | Application entry point |
| `activities/` | `SplashScreenActivity`, `MainContentActivity` (the main screen), `NativeSettingsActivity`, `DeveloperSettingsActivity` |
| `webview/` | `MainContentWebView`, `MagazineSheetAdheringBehavior` — **the heart of the app** |
| `fragments/` | Navigation, top/bottom toolbars, customer-management chrome |
| `audio/` | Podcast & read-aloud player: `AppAudioService`, `database/`, `offline/AudioDownloadWorker`, `synchronization/` (playlist sync), `ui/` bottom sheets, `auto/` (Android Auto) |
| `offline_library/` | Magazine downloads: `PublicationDownloadWorker`, `ui/OfflinePublicationReaderActivity` |
| `push/fcm/` | Firebase push: `PushNotificationService`, tag registration workers |
| `push/settings/` | `PushSettingsActivity` |
| `billing/` | Play Billing + `account_linking/LinkAccountWorker` |
| `widget/` | Home-screen widgets (`small_widget/`, `large_widget/`), `WidgetConfigurationActivity` |
| `database/` | Room `AppDatabase` |
| `layout/` | Custom font views (`CustomBoldTextView`, …), `FontSizeDialogFragment`, `MarkerSeekBar` |
| `rating/` | In-app rating dialog |

### The one architectural fact that matters

**This is largely a WebView wrapper around spiegel.de**, with native features
(audio, offline library, push, widgets, Android Auto) built around it.

Evidence: `webview/MainContentWebView` is the main content surface,
`classes.dex` references `android/webkit` and `org/chromium` heavily, and
`assets/application.properties` — see below — simply points at
`https://www.spiegel.de/`. Article rendering, paywall and layout are web content,
not Android views.

## How to actually read it

Neither tool is installed on this machine, and there is no `java` either, so start with:

```bash
sudo apt install default-jdk-headless
```

Then pick a route — run these against the **APK**, not against this folder:

```bash
# Readable Java source. Best for understanding the app. Cannot be rebuilt.
jadx -d ../jadx_out ../spon.apk

# Smali + decoded AndroidManifest.xml + proper res/. Editable and rebuildable.
apktool d ../spon.apk -o ../apktool_out
```

* `jadx` — get the release zip from `github.com/skylot/jadx` (not in the Ubuntu repos).
  Look in `jadx_out/sources/de/spiegel/android/app/spon/`.
* `apktool` — Ubuntu 24.04 ships 2.7.0 (2022), which often fails on resources from
  recent AAPT2 builds; prefer the current `apktool.jar` + wrapper from
  `github.com/iBotPeaches/Apktool/releases`.
* Rebuilding (`apktool b`) produces an unsigned APK. You must `zipalign` and re-sign
  it (`apksigner`, or `uber-apk-signer`), and uninstall the Play Store version first —
  the signatures won't match.

## Directory map

Ordered roughly by how much attention each entry deserves.

| Entry | Size | What it is |
|---|---|---|
| `classes.dex` | 9.2 MB | **The app. All Spiegel code + bundled libraries.** Dalvik bytecode. |
| `assets/` | 500 KB, 15 files | Runtime assets — the only plain-text config in the dump. See below. |
| `AndroidManifest.xml` | 33 KB | Components, permissions, intent filters — but **binary AXML**, not text. Needs apktool. |
| `resources.arsc` | 1.7 MB | Compiled resource table (strings, styles, the real names behind `res/`). Binary. |
| `res/` | 8.8 MB, 2015 files | Drawables and layouts, but with **obfuscated flat filenames** (`0c.9.png`, `1Q.xml`, `-1.xml`). Unusable without `resources.arsc` — apktool restores the real `res/layout/…` tree. |
| `classes2.dex` | 468 KB | Desugaring backports only. No app logic. |
| `META-INF/` | 948 KB, 99 files | `CERT.RSA` / `CERT.SF` / `MANIFEST.MF` (Spiegel's original signature) + 78 AndroidX `*.version` markers that reveal the exact library versions used. |
| `lib/` | 64 KB, 4 files | One tiny native library, `libdatastore_shared_counter.so` (12 KB), shipped for `arm64-v8a`, `armeabi-v7a`, `x86`, `x86_64`. Jetpack DataStore, nothing app-specific. |
| `kotlin/` | 112 KB, 8 files | `*.kotlin_builtins` — stdlib metadata for the Kotlin compiler. Noise. |
| `google/` | 496 KB, 63 files | `.proto` schemas bundled by gRPC/Firebase (`google/api`, `google/rpc`, `google/protobuf`, …). Noise. |
| `firebase/`, `logs/`, `developers/` | 76 KB total | More bundled `.proto` schemas (in-app messaging, Firebase logging, targeting). Noise. |
| `*.properties` (25 files) | ~2 KB | Version stamps dropped in by each Play Services / Firebase library (`play-services-ads.properties`, `billing.properties`, …). Handy as an SDK inventory. |
| `*.proto` (3 files) | ~6 KB | `client_analytics.proto`, `messaging_event.proto`, `messaging_event_extension.proto`. |
| `DebugProbesKt.bin` | 1.7 KB | kotlinx-coroutines debug metadata. |

## Worth reading right now

These are the few files that are plain text and actually informative:

**`assets/application.properties`** — the app's endpoint configuration, and the
single most useful file here:

```
home_url=https://www.spiegel.de/
customer_management_base_url=https://gruppenkonto.spiegel.de/
android_auto_podcasts_relative_url=api/audio/v1/podcasts/
android_auto_latest_audios=api/audio/v1/tts/
playlist_sync=services/depot/api/v1/playlists
widget_default_feed_relative_url=schlagzeilen/app.rss
account_menu_relative_url=assets/app/account-menu.html
onboarding_relative_url=assets/app/onboarding.html
```

It even retains commented-out staging URLs (`pr6541.feature.dev.www.spiegel.de`,
`review.cm.spiegel.de`).

**`assets/partner_apps.json`** — host → package handoff to the sibling apps
`de.spiegel.android.app.mmo` (manager-magazin) and `de.android.elffreunde` (11 Freunde).

**`assets/fonts/`** — the Spiegel corporate typefaces (`SpiegelSans4UI-*`,
`SpiegelSlab4UICd-ExtraBold`). **`assets/images/`** — Android Auto icons.

**`META-INF/*.version`** — exact AndroidX versions, if you need to match a library's
source to the bytecode.

