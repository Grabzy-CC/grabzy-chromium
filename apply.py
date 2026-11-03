#!/usr/bin/env python3
"""Turn a checkout of an ungoogled-chromium platform repo into Grabzy.CC.

    python3 apply.py <windows|macos|linux> <checkout>

Copies our patches and branding in, hooks brand.py in right after the patches
are applied, and points packaging and releases at Grabzy-CC. Every edit looks
for an exact piece of upstream text and stops if it is not there, so a changed
build script fails here, in the sync job, and never half way through a build.
Running it twice changes nothing the second time.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORG = "Grabzy-CC"


def log(msg):
    print("[apply] " + msg, flush=True)


def edit(root, path, old, new, count=1):
    full = os.path.join(root, path)
    raw = open(full, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"  # a Windows checkout may have CRLF
    data = raw.replace("\r\n", "\n")
    if new in data and (old in new or old not in data):  # already applied
        return
    found = data.count(old)
    if found != count:
        sys.exit("[apply] %s: expected %d of %r, found %d. Upstream changed this file." % (path, count, old[:80], found))
    open(full, "w", encoding="utf-8", newline=eol).write(data.replace(old, new))
    log("edited " + path)


def remove(root, path):
    full = os.path.join(root, path)
    if os.path.exists(full):
        os.remove(full)
        log("removed " + path)


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8", newline="\n").write(text)
    log("wrote " + path)


def common(root):
    """Our patches after upstream's, and the branding kit at grabzy/."""
    names = [l.strip() for l in open(os.path.join(HERE, "patches", "series")) if l.strip() and not l.startswith("#")]
    dst = os.path.join(root, "patches", "grabzy")
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for n in names:
        shutil.copyfile(os.path.join(HERE, "patches", n), os.path.join(dst, n))
    series = os.path.join(root, "patches", "series")
    lines = open(series, encoding="utf-8").read().splitlines()
    lines = [l for l in lines if not l.startswith("grabzy/")] + ["grabzy/" + n for n in names]
    open(series, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    log("patches: %d added to patches/series" % len(names))

    kit = os.path.join(root, "grabzy")
    shutil.rmtree(kit, ignore_errors=True)
    os.makedirs(kit)
    shutil.copyfile(os.path.join(HERE, "branding", "brand.py"), os.path.join(kit, "brand.py"))
    shutil.copytree(os.path.join(HERE, "branding", "files"), os.path.join(kit, "files"))
    log("branding kit copied to grabzy/")


WINDOWS_BUILD = """name: build-x64
on:
  workflow_dispatch:
  push:
    tags:
      - '*-grabzy.*'

permissions:
  contents: read

concurrency:
  group: build-x64-${{ github.ref }}
  cancel-in-progress: false

jobs:
  build:
    uses: ./.github/workflows/reusable-build.yml

  release:
    needs: build
    if: startsWith(github.ref, 'refs/tags/')
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Download the installer and zip
        uses: actions/download-artifact@v8
        with:
          name: chromium
          path: artifacts
      - name: Name them for Grabzy.CC
        working-directory: artifacts
        run: |
          for f in ungoogled-chromium_*; do mv -v "$f" "grabzy-chromium_${f#ungoogled-chromium_}"; done
          sha256sum grabzy-chromium_* | tee SHA256SUMS.txt
      - name: Publish the release
        uses: softprops/action-gh-release@v3
        with:
          tag_name: ${{ github.ref_name }}
          name: Grabzy.CC ${{ github.ref_name }}
          fail_on_unmatched_files: true
          files: |
            artifacts/grabzy-chromium_*
            artifacts/SHA256SUMS.txt
"""


def windows(root):
    edit(root, "build.py",
         "            patches.generate_patches_from_series(_ROOT_DIR / 'patches', resolve=True),\n"
         "            source_tree,\n"
         "            patch_bin_path=(source_tree / _PATCH_BIN_RELPATH)\n"
         "        )\n",
         "            patches.generate_patches_from_series(_ROOT_DIR / 'patches', resolve=True),\n"
         "            source_tree,\n"
         "            patch_bin_path=(source_tree / _PATCH_BIN_RELPATH)\n"
         "        )\n"
         "        # Grabzy.CC: product name, translations and icons\n"
         "        subprocess.run([sys.executable, str(_ROOT_DIR / 'grabzy' / 'brand.py'), str(source_tree)], check=True)\n")
    # x64 only, released by build-x64 itself.
    for f in ("build-x86.yml", "build-arm.yml", "publish-release.yml"):
        remove(root, ".github/workflows/" + f)
    write(root, ".github/workflows/build-x64.yml", WINDOWS_BUILD)


def macos(root):
    hook = 'python3 "$_main_repo/utils/patches.py" apply "$_src_dir" "$_main_repo/patches" "$_root_dir/patches"\n'
    brand = hook + 'python3 "$_root_dir/grabzy/brand.py" "$_src_dir"\n'
    edit(root, "build.sh", hook, brand)
    edit(root, ".github/scripts/github_fetch_resources.sh", hook, brand)

    # GitHub's own runners instead of Depot's paid ones, and only our tags.
    edit(root, ".github/workflows/build.yml", "os: depot-macos-latest", "os: macos-latest")
    edit(root, ".github/workflows/build.yml", "      - '**'\n", "      - '*-grabzy.*'\n")

    for f in (".github/scripts/github_prepare_release.sh", ".github/scripts/github_generate_release_note.sh"):
        edit(root, f, '="ungoogled-chromium_', '="grabzy-chromium_', count=2)
    edit(root, ".github/scripts/github_prepare_artifacts.sh", '_file_name="ungoogled-chromium_', '_file_name="grabzy-chromium_')
    # The release goes out under the tag that was pushed.
    edit(root, ".github/scripts/github_prepare_release.sh",
         '_release_tag_version="${_chromium_version}-${_ungoogled_revision}.${_package_revision}"\n_release_name="${_release_tag_version}"',
         '_release_tag_version="${GITHUB_REF_NAME}"\n_release_name="Grabzy.CC ${GITHUB_REF_NAME}"')
    edit(root, ".github/scripts/github_generate_release_note.sh",
         "printf '## Ungoogled-Chromium macOS %s\\n\\n'", "printf '## Grabzy.CC for macOS %s\\n\\n'")

    # Without an Apple Developer ID the app is signed ad hoc, and not notarized.
    edit(root, ".github/scripts/github_prepare_artifacts.sh",
         '  # Prepare the certificate for app signing\n'
         '  printf \'%s\' "$MACOS_CERTIFICATE" | base64 --decode > "$TMPDIR/certificate.p12"\n'
         '\n'
         '  security create-keychain -p "$MACOS_CI_KEYCHAIN_PWD" build.keychain\n'
         '  security default-keychain -s build.keychain\n'
         '  security unlock-keychain -p "$MACOS_CI_KEYCHAIN_PWD" build.keychain\n'
         '  security import "$TMPDIR/certificate.p12" -k build.keychain -P "$MACOS_CERTIFICATE_PWD" -T /usr/bin/codesign\n'
         '  security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$MACOS_CI_KEYCHAIN_PWD" build.keychain\n',
         '  if [[ -n "${MACOS_CERTIFICATE:-}" ]]; then\n'
         '    # Prepare the certificate for app signing\n'
         '    printf \'%s\' "$MACOS_CERTIFICATE" | base64 --decode > "$TMPDIR/certificate.p12"\n'
         '\n'
         '    security create-keychain -p "$MACOS_CI_KEYCHAIN_PWD" build.keychain\n'
         '    security default-keychain -s build.keychain\n'
         '    security unlock-keychain -p "$MACOS_CI_KEYCHAIN_PWD" build.keychain\n'
         '    security import "$TMPDIR/certificate.p12" -k build.keychain -P "$MACOS_CERTIFICATE_PWD" -T /usr/bin/codesign\n'
         '    security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$MACOS_CI_KEYCHAIN_PWD" build.keychain\n'
         '  else\n'
         '    export MACOS_AD_HOC_SIGNING=1\n'
         '  fi\n')
    edit(root, "sign_and_package_app.sh", "--volname Chromium ", '--volname "Grabzy.CC" ')


def linux(root):
    edit(root, "scripts/shared.sh",
         '        "${_main_repo}/utils/patches.py" apply "${_src_dir}" "${_main_repo}/patches" "${_root}/patches"\n',
         '        "${_main_repo}/utils/patches.py" apply "${_src_dir}" "${_main_repo}/patches" "${_root}/patches"\n'
         '        python3 "${_root}/grabzy/brand.py" "${_src_dir}"\n')

    edit(root, "scripts/package.sh", '_app_name="ungoogled-chromium"', '_app_name="grabzy-chromium"')
    # AppImageUpdate looks for new versions in our releases.
    edit(root, "scripts/package.sh",
         '_update_info="gh-releases-zsync|ungoogled-software|ungoogled-chromium-portablelinux|',
         '_update_info="gh-releases-zsync|%s|grabzy-chromium-linux|' % ORG)
    edit(root, "package/ungoogled-chromium.desktop", "Name=ungoogled-chromium\n", "Name=Grabzy.CC\n")
    edit(root, ".github/actions/package/action.yml", "ungoogled-chromium-${{", "grabzy-chromium-${{", count=4)
    edit(root, ".github/actions/release/action.yml", "ungoogled-chromium-*", "grabzy-chromium-*", count=5)

    edit(root, ".github/workflows/build.yml",
         "      - '[0-9]+.[0-9]+.[0-9]+.[0-9]+-[0-9]+'\n", "      - '*-grabzy.*'\n")
    edit(root, ".github/workflows/build.yml", "arch: [arm64, x86_64]", "arch: [x86_64]")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("windows", "macos", "linux"):
        sys.exit(__doc__)
    platform, root = sys.argv[1], sys.argv[2]
    common(root)
    globals()[platform](root)
    log("done: %s" % platform)


if __name__ == "__main__":
    main()
