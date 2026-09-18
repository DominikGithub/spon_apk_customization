# Customized Spiegel-Online Android .apk

- No Ads
- Hide news categories  

Rebuild the latest version from the installed binary on a phone connected via `adb` debug bridge.

Single `Claude Opus 5 (medium)` prompt in `REBUILD_PROMPT.md`.

#### App build workflow
- Pull original .apk file via adb from Android phone
- Unpack .apk 
- Patch code by (/patch/hide.txt, etc) 
- Rebuild 
- Install customized version on the phone via adb 
