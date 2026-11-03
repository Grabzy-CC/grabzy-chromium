<p align="center">
  <img src="branding/preview.png" alt="The Grabzy.CC icon at six sizes: a white G with a green dot on a near-black tile" width="720">
</p>

<h1 align="center">Grabzy.CC browser</h1>

<p align="center">
  A Chromium build for Grabzy.CC that keeps the claimer's connection alive.<br>
  It is <a href="https://github.com/ungoogled-software/ungoogled-chromium">ungoogled-chromium</a> with three small patches and our branding, built and released by GitHub Actions.
</p>

<p align="center">
  <a href="https://github.com/Grabzy-CC/grabzy-chromium-windows/releases/latest">Windows</a> ·
  <a href="https://github.com/Grabzy-CC/grabzy-chromium-macos/releases/latest">macOS</a> ·
  <a href="https://github.com/Grabzy-CC/grabzy-chromium-linux/releases/latest">Linux</a>
</p>

---

## Why this exists

Recent versions of Chrome cut connections the Grabzy.CC extension relies on:

- **Back/forward cache.** Since Chrome 156, a page with an open WebSocket can go into the back/forward cache, and Chrome closes the socket when it does. Enterprise policy can turn this off for now, but that policy is deprecated in 157 and goes away in 167.
- **Background throttling.** After five minutes in the background, Chrome wakes a tab's timers only once a minute. The relay heartbeat runs every 25 seconds and the server drops a socket after 62.5 quiet seconds, so a background tab loses its connection.

This browser fixes both in the source code, with no policies and no flags to set.

## Download

| Platform | File | Updates |
|---|---|---|
| Windows 10 and 11, x64 | `grabzy-chromium_<version>_installer_x64.exe`, or the `.zip` for a portable copy | [`updater/windows`](updater/windows/grabzy-update.ps1) |
| macOS 12+, Apple silicon or Intel | `grabzy-chromium_<version>_arm64-macos.dmg` or `_x86_64-macos.dmg` | [`updater/macos`](updater/macos/grabzy-update.sh) |
| Linux, x86_64 | `grabzy-chromium-<version>-x86_64.AppImage` | Built in, through AppImageUpdate |

Every release lists SHA-256 checksums. Releases are tagged `<ungoogled version>-grabzy.<n>`, for example `156.0.8078.79-1-grabzy.1`.

### Windows

Run the installer. It installs for your user only, with no admin prompt. To keep the browser updated, run the updater once with `-Schedule`. It then checks for new releases at every logon and every day at noon:

```powershell
powershell -ExecutionPolicy Bypass -File grabzy-update.ps1 -Schedule
```

The builds are not code-signed, so SmartScreen may warn the first time. Choose **More info**, then **Run anyway**.

### macOS

The quickest way to install is the updater script. It downloads the disk image for your Mac, checks it, and installs it to `/Applications`:

```bash
curl -fsSLO https://raw.githubusercontent.com/Grabzy-CC/grabzy-chromium/main/updater/macos/grabzy-update.sh
bash grabzy-update.sh --schedule
```

`--schedule` also checks at login and every six hours. It never replaces the app while the browser is open.

If you would rather open the `.dmg` yourself, be aware that the builds are signed ad hoc, not notarized. Drag the app to Applications, then run `xattr -cr /Applications/Chromium.app` once. Otherwise macOS reports the app as damaged.

### Linux

```bash
chmod +x grabzy-chromium-*-x86_64.AppImage
./grabzy-chromium-*-x86_64.AppImage
```

Each AppImage carries its own update information, so [AppImageUpdate](https://github.com/AppImageCommunity/AppImageUpdate) and [Gear Lever](https://github.com/mijorus/gearlever) fetch new versions from our releases and download only the changed parts.

## What we change

Everything else is ungoogled-chromium, unchanged.

| Change | File | Effect |
|---|---|---|
| [keep-websocket-pages-out-of-bfcache](patches/keep-websocket-pages-out-of-bfcache.patch) | `runtime_enabled_features.json5` | Turns off `DisconnectWebSocketOnBFCache`. A page with an open WebSocket never enters the back/forward cache, so its socket is never closed there. |
| [keep-background-timers-awake](patches/keep-background-timers-awake.patch) | `blink/common/features.cc` | Turns off intensive wake-up throttling. Background tabs keep Chrome's usual limit of one wake-up per second, never one per minute. |
| [default-to-grabzy-theme](patches/default-to-grabzy-theme.patch) | `theme_service.cc` | New profiles start dark, with the website's green (`#2EE87A`) as the colour seed. Settings › Appearance can still change both. |
| [Branding](branding/brand.py) | strings, `BRANDING`, icons | The product is called Grabzy.CC in menus, dialogs, the installer and every translation, with our icon on every platform. |

### Theme

The browser uses the website's palette. Surfaces are near-black (`#0B0D14`), text is off-white (`#EEF0F5`), and the live green (`#2EE87A`) marks what is active. Chromium builds its Material colours from one seed colour, so the green carries into tabs, the omnibox and focus rings without a theme extension. Incognito stays grey, as in Chrome.

### How the branding works

[`brand.py`](branding/brand.py) runs right after the patches, with the standard library only. It renames "Chromium" in the two product string files, but keeps "Chromium OS" and "The Chromium Authors". Chromium keys each translation by a hash of its English text, so changing the English would normally send every locale back to English. `brand.py` computes grit's message IDs itself, which matches 864 of 864 IDs on 156, and moves each translation to its new ID. It stops the build if fewer than 95% of the new IDs match a translation, which would mean the hashing changed. The icons are generated from [`icon.svg`](branding/icon.svg) by [`make_icons.py`](branding/make_icons.py) and committed under [`branding/files`](branding/files).

## How new versions ship

```
 ungoogled-chromium release
          │
          ▼
 sync.yml (daily, in this repo)
   ├─ new release for windows / macos / linux?   no → done
   ├─ ci/check.py: fetch the ~170 Chromium files we touch at that version,
   │    replay upstream's patches, then ours, then brand.py --check
   │      └─ fails → open an issue here, tag nothing
   └─ apply.py: patches + branding into upstream's repo
        → push tag <version>-grabzy.<n> to Grabzy-CC/grabzy-chromium-<platform>
          │
          ▼
 the platform fork builds and publishes the release → updaters pick it up
```

Nothing is tagged until the check passes, so a Chromium change that breaks a patch never ships a half-patched browser. Users stay on the last good release, and an issue in this repo says which file stopped matching.

**What happens at Chrome 167.** Our patch does not use the `BackForwardCacheForWebSocketsAllowed` policy. It changes the engine default behind that policy, so removing the policy changes nothing for us. If Chromium later removes the flag itself, our patch stops applying. The sync then opens an issue and holds the release until the patch is updated, for example by marking WebSockets as a back/forward cache blocker in `content/`. The Grabzy.CC extension also reconnects on `pageshow`, so claims keep working in the meantime.

To rebuild the same upstream version after changing a patch or the branding, bump [`revision.txt`](revision.txt). The next sync tags `-grabzy.<n+1>`.

## Repository layout

```
patches/          our Chromium patches and their series
branding/         brand.py, icon.svg, make_icons.py, generated icons in files/
apply.py          turns an ungoogled-chromium platform checkout into Grabzy.CC
ci/check.py       the pre-flight check sync.yml runs before tagging
updater/          Windows and macOS update scripts
.github/workflows/sync.yml
revision.txt      our build number on top of each upstream version
```

`apply.py` matches exact lines in upstream's build scripts and stops if one is missing. A change upstream fails loudly in the sync, never halfway through a five-hour build. Running it twice changes nothing.

## Running the pipeline

These steps are for maintainers. Users only need the downloads above.

1. Fork the three upstream repos into the org under these names:

   | Fork | Upstream |
   |---|---|
   | `Grabzy-CC/grabzy-chromium-windows` | `ungoogled-software/ungoogled-chromium-windows` |
   | `Grabzy-CC/grabzy-chromium-macos` | `ungoogled-software/ungoogled-chromium-macos` |
   | `Grabzy-CC/grabzy-chromium-linux` | `ungoogled-software/ungoogled-chromium-portablelinux` |

2. In each fork, open **Actions** and enable workflows. GitHub turns them off in new forks.
3. Create a fine-grained token for the three forks with **Contents: read and write** and **Workflows: read and write**. Workflows access is needed because `apply.py` edits files under `.github/workflows`. Add the token to this repo as the secret `SYNC_TOKEN`. A token is needed because a tag pushed with the built-in `GITHUB_TOKEN` does not start workflows in another repo.
4. Run **sync** from this repo's Actions tab, or wait for the 03:17 UTC daily run.

Optional: on macOS, add the fork secrets `MACOS_CERTIFICATE`, `MACOS_CERTIFICATE_PWD` and `MACOS_CI_KEYCHAIN_PWD`, plus upstream's notarization secrets, to sign with a Developer ID. Without them the build is signed ad hoc.

### Build times on free runners

All builds run on GitHub's free runners for public repos.

- **Windows.** Upstream splits the build into 16 chained jobs to stay under the 6-hour job limit. A release takes most of a day.
- **macOS.** Builds run on `macos-latest` instead of upstream's paid Depot runners. Expect several hours per architecture. Disk space is tight on these runners, so a build can fail for lack of space; rerunning the failed job usually works.
- **Linux.** One x86_64 build, several hours.

## Known limitations

- **Names on disk.** The app is still `Chromium.app` on macOS, and the install folder and profile folder stay `Chromium` on every platform. Renaming the bundle means renaming its helpers, framework and signing setup, which needs a test build first. Because the folders are shared, this browser and an existing Chromium or ungoogled-chromium install use the same profile. Use one or the other, or start one with `--user-data-dir`.
- **Unsigned on Windows, ad hoc on macOS**, as described above.
- **x64 only on Windows and Linux.** The arm64 and x86 jobs are switched off to save runner time.

## Credits and licence

Built on [ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium) and its [Windows](https://github.com/ungoogled-software/ungoogled-chromium-windows), [macOS](https://github.com/ungoogled-software/ungoogled-chromium-macos) and [Linux](https://github.com/ungoogled-software/ungoogled-chromium-portablelinux) packaging, all BSD-3-Clause, and on [Chromium](https://www.chromium.org/), © The Chromium Authors, BSD-style licence. Grabzy.CC is not affiliated with Google or the ungoogled-chromium project.

The code in this repository is BSD-3-Clause; see [LICENSE](LICENSE).
