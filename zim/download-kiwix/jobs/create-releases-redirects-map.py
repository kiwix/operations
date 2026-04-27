#!/usr/bin/env python3

""" Rewrites releases redirects map for Kiwix and openZIM """

import argparse
import datetime
import os
import pathlib
import re
from dataclasses import dataclass
from packaging.version import Version


@dataclass
class Defaults:
    OPENZIM_DOWNLOAD_ROOT = "/data/openzim"
    OPENZIM_RELEASE_REDIRECTS_MAP = "/data/maps/openzim-releases.map"
    OPENZIM_RELEASE_IS_APACHE = False
    OPENZIM_NIGHTLY_REDIRECTS_MAP = "/data/maps/openzim-nightly.map"
    OPENZIM_NIGHTLY_IS_APACHE = False
    KIWIX_DOWNLOAD_ROOT = "/data/kiwix"
    KIWIX_RELEASE_REDIRECTS_MAP = "/data/maps/kiwix-releases.map"
    KIWIX_RELEASE_IS_APACHE = False
    KIWIX_NIGHTLY_REDIRECTS_MAP = "/data/maps/kiwix-nightly.map"
    KIWIX_NIGHTLY_IS_APACHE = False


# using special, custom syntax: the content within the two pipes
# is considered a single regex match expression for the version.
# this allows finer-matching when a simple * glob matching would
# match a different file because there are files with specifiers on same level
# as version.
# see https://github.com/kiwix/operations/issues/406
openzim_releases = {
    "javascript-libzim/libzim_wasm.zip": "libzim_wasm_*.zip",
    # obsolete
    "javascript-libzim/libzim_asm.zip": "libzim_asm_*.zip",

    "libzim/libzim.tar.xz": "libzim-*.tar.xz",
    "libzim/libzim_android-arm.tar.gz": "libzim_android-arm-*.tar.gz",
    "libzim/libzim_android-arm64.tar.gz": "libzim_android-arm64-*.tar.gz",
    "libzim/libzim_android-x86.tar.gz": "libzim_android-x86-*.tar.gz",
    "libzim/libzim_android-x86_64.tar.gz": "libzim_android-x86_64-*.tar.gz",
    "libzim/libzim_linux-aarch64.tar.gz": r"libzim_linux-aarch64-|[\d\.]+|.tar.gz",
    "libzim/libzim_linux-aarch64-bionic.tar.gz": "libzim_linux-aarch64-bionic-*.tar.gz",
    "libzim/libzim_linux-aarch64-musl.tar.gz": "libzim_linux-aarch64-musl-*.tar.gz",
    "libzim/libzim_linux-armv6.tar.gz": "libzim_linux-armv6-*.tar.gz",
    "libzim/libzim_linux-armv8.tar.gz": "libzim_linux-armv8-*.tar.gz",
    "libzim/libzim_linux-x86_64.tar.gz": r"libzim_linux-x86_64-|[\d\.]+|.tar.gz",
    "libzim/libzim_linux-x86_64-bionic.tar.gz": "libzim_linux-x86_64-bionic-*.tar.gz",
    "libzim/libzim_linux-x86_64-musl.tar.gz": "libzim_linux-x86_64-musl-*.tar.gz",
    "libzim/libzim_macos-arm64.tar.gz": "libzim_macos-arm64-*.tar.gz",
    "libzim/libzim_macos-x86_64.tar.gz": "libzim_macos-x86_64-*.tar.gz",
    "libzim/libzim_wasm-emscripten.tar.gz": "libzim_wasm-emscripten-*.tar.gz",
    # obsolete
    "libzim/libzim_linux-armhf.tar.gz": "libzim_linux-armv6-*.tar.gz",
    "zim-tools/zim-tools.tar.xz": "zim-tools-*.tar.xz",
    "zim-tools/zim-tools_linux-aarch64.tar.gz": r"zim-tools_linux-aarch64-|[\d\.]+|.tar.gz",
    "zim-tools/zim-tools_linux-aarch64-musl.tar.gz": "zim-tools_linux-aarch64-musl-*.tar.gz",
    "zim-tools/zim-tools_linux-armv6.tar.gz": "zim-tools_linux-armv6-*.tar.gz",
    "zim-tools/zim-tools_linux-armv8.tar.gz": "zim-tools_linux-armv8-*.tar.gz",
    "zim-tools/zim-tools_linux-i586.tar.gz": "zim-tools_linux-i586-*.tar.gz",
    "zim-tools/zim-tools_linux-x86_64.tar.gz": r"zim-tools_linux-x86_64-|[\d\.]+|.tar.gz",
    "zim-tools/zim-tools_linux-x86_64-musl.tar.gz": "zim-tools_linux-x86_64-musl-*.tar.gz",
    "zim-tools/zim-tools_macos-arm64.tar.gz": "zim-tools_macos-arm64-*.tar.gz",
    "zim-tools/zim-tools_macos-x86_64.tar.gz": "zim-tools_macos-x86_64-*.tar.gz",
    "zim-tools/zim-tools_win-i686.zip": "zim-tools_win-i686-*.zip",
    # obsolete
    "zim-tools/zim-tools_linux-armhf.tar.gz": "zim-tools_linux-armv6-*.tar.gz",

    "zimwriterfs/zimwriterfs.tar.xz": "zimwriterfs-*.tar.xz",
    "zimwriterfs/zimwriterfs_linux-x86_64.tar.gz": "zimwriterfs_linux-x86_64-*.tar.gz",
}

kiwix_releases = {
    "browsers/firefox/kiwix-firefox.xpi": "kiwix-firefox_*.xpi",
    "browsers/chrome/kiwix-chrome-mv2.zip": "kiwix-chrome-mv2_*.zip",
    "browsers/chrome/kiwix-chrome.crx": "kiwix-chrome_*.crx",
    "browsers/edge/kiwix-edge-mv2.zip": "kiwix-edge-mv2_*.zip",

    "firefox-os/kiwix-firefoxos.zip": "kiwix-firefoxos-*.zip",

    "kiwix-android/kiwix.apk": "kiwix-*.apk",
    "kiwix-android/org.kiwix.kiwixmobile.standalone.apk": "org.kiwix.kiwixmobile.standalone-*.apk",

    "kiwix-desktop-macos/kiwix-desktop-macos.dmg": "kiwix-macos_*.dmg",
    "kiwix-desktop-macos/kiwix-macos.dmg": "kiwix-macos_*.dmg",
    "kiwix-macos/kiwix-macos.dmg": "kiwix-macos_*.dmg",

    "kiwix-desktop/kiwix-desktop.tar.gz": "kiwix-desktop-*.tar.gz",
    "kiwix-desktop/kiwix-desktop_windows_x64.zip": ("kiwix-desktop_windows_x64_*.zip"),
    "kiwix-desktop/kiwix-desktop_x86_64.appimage": ("kiwix-desktop_x86_64_*.appimage"),
    "kiwix-desktop/org.kiwix.desktop.flatpak": "org.kiwix.desktop.*.flatpak",

    "kiwix-hotspot/kiwix-hotspot-linux.tar.gz": "kiwix-hotspot-linux-*.tar.gz",
    "kiwix-hotspot/kiwix-hotspot-macos.dmg": "kiwix-hotspot-macos-*.dmg",
    "kiwix-hotspot/kiwix-hotspot-win64.exe": "kiwix-hotspot-win64-*.exe",

    "kiwix-js-electron/kiwix-js-electron_i386.deb": "kiwix-js-electron_i386_*.deb",
    "kiwix-js-electron/kiwix-js-electron_x86-64.deb": "kiwix-js-electron_x86-64_*.deb",
    "kiwix-js-electron/kiwix-js-electron_x86-64.deb": "kiwix-js-electron_x86-64_*.deb",
    "kiwix-js-electron/kiwix-js-electron_x86-64.rpm": "kiwix-js-electron_x86-64_*.rpm",
    "kiwix-js-electron/kiwix-js-electron_i686.rpm": "kiwix-js-electron_i686_*.rpm",
    "kiwix-js-electron/kiwix-js-electron_i386.appimage": "kiwix-js-electron_i386_*.appimage",
    "kiwix-js-electron/kiwix-js-electron_x86-64.appimage": "kiwix-js-electron_x86-64_*.appimage",
    "kiwix-js-electron/kiwix-js-electron.zip": "kiwix-js-electron_*.zip",
    "kiwix-js-electron/kiwix-js-electron_win_setup.exe": "kiwix-js-electron_win_setup_*.exe",
    "kiwix-js-electron/kiwix-js-electron_win_portable.exe": "kiwix-js-electron_win_portable_*.exe",
    "kiwix-js-electron/kiwix-js-electron_x86-64.appx": "kiwix-js-electron_x86-64_*.appx",
    "kiwix-js-electron/kiwix-js-nwjs_win-xp_i386.zip": "kiwix-js-nwjs_win-xp_i386_*.zip",
    "kiwix-js-electron/kiwix-js-nwjs_win_i386.zip": "kiwix-js-nwjs_win_i386_*.zip",

    "kiwix-js-windows/kiwix-js-windows.appxbundle": "kiwix-js-windows_*.appxbundle",
    "kiwix-js-windows/kiwix-js-windows.appx": "kiwix-js-windows_*.appx",

    "kiwix-tools/kiwix-tools_macos-x86_64.tar.gz": "kiwix-tools_macos-x86_64-*.tar.gz",
    "kiwix-tools/kiwix-tools_macos-arm64.tar.gz": "kiwix-tools_macos-arm64-*.tar.gz",
    "kiwix-tools/kiwix-tools.tar.xz": "kiwix-tools-*.tar.xz",
    "kiwix-tools/kiwix-tools_linux-x86_64.tar.gz": r"kiwix-tools_linux-x86_64-|[\d\.]+|.tar.gz",
    "kiwix-tools/kiwix-tools_linux-aarch64-musl.tar.gz": "kiwix-tools_linux-aarch64-musl-*.tar.gz",
    "kiwix-tools/kiwix-tools_linux-armv6.tar.gz": "kiwix-tools_linux-armv6-*.tar.gz",
    "kiwix-tools/kiwix-tools_linux-armv8.tar.gz": "kiwix-tools_linux-armv8-*.tar.gz",
    "kiwix-tools/kiwix-tools_linux-x86_64-musl.tar.gz": "kiwix-tools_linux-x86_64-musl-*.tar.gz",
    "kiwix-tools/kiwix-tools_linux-aarch64.tar.gz": r"kiwix-tools_linux-aarch64-|[\d\.]+|.tar.gz",
    "kiwix-tools/kiwix-tools_win-i686.zip": "kiwix-tools_win-i686-*.zip",
    "kiwix-tools/kiwix-tools_linux-i586.tar.gz": "kiwix-tools_linux-i586-*.tar.gz",
    # obsolete
    "kiwix-tools/kiwix-tools_linux-armhf.tar.gz": "kiwix-tools_linux-armv6-*.tar.gz",

    "libkiwix/libkiwix_xcframework.tar.gz": "libkiwix_xcframework-*.tar.gz",
    "libkiwix/libkiwix_macos-x86_64.tar.gz": "libkiwix_macos-x86_64-*.tar.gz",
    "libkiwix/libkiwix_macos-arm64.tar.gz": "libkiwix_macos-arm64-*.tar.gz",
    "libkiwix/libkiwix_linux-x86_64.tar.gz": "libkiwix_linux-x86_64-*.tar.gz",
    "libkiwix/libkiwix_android-x86_64.tar.gz": "libkiwix_android-x86_64-*.tar.gz",
    "libkiwix/libkiwix_android-x86.tar.gz": "libkiwix_android-x86-*.tar.gz",
    "libkiwix/libkiwix_android-arm64.tar.gz": "libkiwix_android-arm64-*.tar.gz",
    "libkiwix/libkiwix_android-arm.tar.gz": "libkiwix_android-arm-*.tar.gz",

    "ubuntu-touch/kiwix-ubuntu-touch.click": "kiwix-ubuntu-touch-*.click",
}


def write_release_redirects_map(content_fpath, redirects_map_fpath, releases, is_nginx):
    release_dir = "release"
    release_fpath = content_fpath / release_dir
    eol = ";" if is_nginx else ""

    if not release_fpath.exists():
        raise IOError(f"release folder {release_fpath} does not exist.")

    def version_key(item: tuple[str, str]):
        version = item[0]
        try:
            return Version(version)
        except Exception:
            ...
        for sep in ("_", "-"):
            if sep in version:
                try:
                    parts = version.split(sep)
                    for part in parts:
                        if part[0].isdigit():
                            return Version(part)
                except Exception:
                    ...
        return Version(re.sub(r"[^\d\.]", "", version))

    def get_latest_release_path(pattern, *, use_sem: bool = True):
        """content_fpath-relative path of latest matching file"""

        glob_pattern = pattern
        re_pattern = pattern.replace("*", "(?P<version>.+)")

        # using special regex syntax
        if pattern.count("|") == 2:
            prefix, regexp, suffix = pattern.split("|", 2)
            glob_pattern = f"{prefix}*{suffix}"  # we filter files with *, always
            re_pattern = f"{prefix}(?P<version>{regexp}){suffix}"  # for actual matching

        # retrieve list of files using glob
        files: list[pathlib.Path] = list(release_fpath.rglob(glob_pattern))

        # create regex from simple “glob” pattern
        version_reg = re.compile(re_pattern)

        # tuple of extracted version and filepath
        files_with_version: list[tuple[str, Path]] = sorted(
            [
                (
                    version_reg.match(p.name).groupdict()["version"],  # pyright: ignore
                    p,
                )
                for p in files
                if version_reg.match(p.name)
            ],
            key=lambda v: v[0],
        )

        # last version and file based on str comparison
        latest_version, lastest_fpath = files_with_version[-1]

        # sorted list of version and files but sorted using version semantics
        files_with_semver = sorted(files_with_version, key=version_key)
        latest_sem_version, lastest_sem_fpath = files_with_semver[-1]

        if use_sem:
            return lastest_sem_fpath.relative_to(content_fpath)

        return lastest_fpath.relative_to(content_fpath)

    print(f"Rewriting {redirects_map_fpath}...")
    content = "# releases redirects: no-version to latest\n"
    if is_nginx:
        content += "# this file is reloaded by nginx thanks to reload-nginx.sh, scheduled hourly at 10mins\n"
    for path, pattern in releases.items():
        content += f"/{release_dir}/{path} /{get_latest_release_path(pattern)}{eol}\n"

    redirects_map_fpath.write_text(content)

    print(f"> OK. Wrote {len(content.splitlines()) -1 } redirects")


def write_nightly_redirects_map(content_fpath, redirects_map_fpath, releases, is_nginx):
    nightly_dir = "nightly"
    nightly_fpath = content_fpath / nightly_dir
    eol = ";" if is_nginx else ""

    if not nightly_fpath.exists():
        raise IOError(f"nightly folder {nightly_fpath} does not exist.")

    content = "# nightly redirects: path -> date/path\n"
    if is_nginx:
        content += "# this file is reloaded by nginx thanks to reload-nginx.sh, scheduled hourly at 10mins\n"
    ordered_folders = [
        nightly_fpath / d.strftime("%Y-%m-%d")
        for d in sorted(
            [
                datetime.date(*[int(p) for p in file.name.split("-")])
                for file in nightly_fpath.iterdir()
                if file.is_dir()
            ],
            reverse=True,
        )
    ]

    patterns = []
    for folder in ordered_folders:
        for fpath in folder.rglob("*"):
            if not fpath.is_file():
                continue
            pattern = (
                fpath.name.replace(f"_{folder.name}", "")
                .replace(f"-{folder.name}", "")
                .replace(f".{folder.name}", "")
            )
            if pattern not in patterns:
                patterns.append(pattern)
                content += (
                    f"/{nightly_dir}/{pattern} "
                    f"/{nightly_dir}/{fpath.relative_to(nightly_fpath)}{eol}\n"
                )

    redirects_map_fpath.write_text(content)

    print(f"> OK. Wrote {len(content.splitlines()) -1 } redirects")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="create-releases-maps",
        description="Rewrites releases redirects map for Kiwix and openZIM",
    )

    parser.add_argument(
        "projects",
        help="Maps to create, from `kiwix`, `openzim`",
        nargs="+",
    )

    parser.add_argument(
        "--openzim-root",
        default=os.getenv("OPENZIM_DOWNLOAD_ROOT", Defaults.OPENZIM_DOWNLOAD_ROOT),
        help="Root openZIM download folder. Defaults to "
        f"`OPENZIM_DOWNLOAD_ROOT` environ or {Defaults.OPENZIM_DOWNLOAD_ROOT}",
        dest="openzim_root",
    )
    parser.add_argument(
        "--openzim-release-redirects",
        default=os.getenv(
            "OPENZIM_RELEASE_REDIRECTS_MAP", Defaults.OPENZIM_RELEASE_REDIRECTS_MAP
        ),
        help="Path to openZIM releases redirects map. "
        "Defaults to `OPENZIM_RELEASE_REDIRECTS_MAP` environ "
        f"or {Defaults.OPENZIM_RELEASE_REDIRECTS_MAP}",
        dest="openzim_release_redirects",
    )
    parser.add_argument(
        "--openzim-release-apache",
        default=os.getenv(
            "OPENZIM_RELEASE_IS_APACHE", Defaults.OPENZIM_RELEASE_IS_APACHE
        ),
        help="Whether to generate maps using apache format (nginx otherwise) "
        "Defaults to `OPENZIM_RELEASE_IS_APACHE` environ "
        f"or {Defaults.OPENZIM_RELEASE_IS_APACHE}",
        dest="openzim_release_apache",
    )
    parser.add_argument(
        "--openzim-nightly-redirects",
        default=os.getenv(
            "OPENZIM_NIGHTLY_REDIRECTS_MAP", Defaults.OPENZIM_NIGHTLY_REDIRECTS_MAP
        ),
        help="Path to openZIM nightly redirects map. "
        "Defaults to `OPENZIM_NIGHTLY_REDIRECTS_MAP` environ "
        f"or {Defaults.OPENZIM_NIGHTLY_REDIRECTS_MAP}",
        dest="openzim_nightly_redirects",
    )
    parser.add_argument(
        "--openzim-nightly-apache",
        default=os.getenv(
            "OPENZIM_NIGHTLY_IS_APACHE", Defaults.OPENZIM_NIGHTLY_IS_APACHE
        ),
        help="Whether to generate maps using apache format (nginx otherwise) "
        "Defaults to `OPENZIM_NIGHTLY_IS_APACHE` environ "
        f"or {Defaults.OPENZIM_NIGHTLY_IS_APACHE}",
        dest="openzim_nightly_apache",
    )
    parser.add_argument(
        "--kiwix-root",
        default=os.getenv("KIWIX_DOWNLOAD_ROOT", Defaults.KIWIX_DOWNLOAD_ROOT),
        help="Root Kiwix download folder. Defaults to "
        f"`KIWIX_DOWNLOAD_ROOT` environ or {Defaults.KIWIX_DOWNLOAD_ROOT}",
        dest="kiwix_root",
    )
    parser.add_argument(
        "--kiwix-release-redirects",
        default=os.getenv(
            "KIWIX_RELEASE_REDIRECTS_MAP", Defaults.KIWIX_RELEASE_REDIRECTS_MAP
        ),
        help="Path to Kiwix releases redirects map. "
        "Defaults to `KIWIX_RELEASE_REDIRECTS_MAP` environ "
        f"or {Defaults.KIWIX_RELEASE_REDIRECTS_MAP}",
        dest="kiwix_release_redirects",
    )
    parser.add_argument(
        "--kiwix-release-apache",
        default=os.getenv(
            "KIWIX_RELEASE_IS_APACHE", Defaults.KIWIX_RELEASE_IS_APACHE
        ),
        help="Whether to generate maps using apache format (nginx otherwise) "
        "Defaults to `KIWIX_RELEASE_IS_APACHE` environ "
        f"or {Defaults.KIWIX_RELEASE_IS_APACHE}",
        dest="kiwix_release_apache",
    )
    parser.add_argument(
        "--kiwix-nightly-redirects",
        default=os.getenv(
            "KIWIX_NIGHTLY_REDIRECTS_MAP", Defaults.KIWIX_NIGHTLY_REDIRECTS_MAP
        ),
        help="Path to Kiwix nightly redirects map. "
        "Defaults to `KIWIX_NIGHTLY_REDIRECTS_MAP` environ "
        f"or {Defaults.KIWIX_NIGHTLY_REDIRECTS_MAP}",
        dest="kiwix_nightly_redirects",
    )
    parser.add_argument(
        "--kiwix-nightly-apache",
        default=os.getenv(
            "KIWIX_NIGHTLY_IS_APACHE", Defaults.KIWIX_NIGHTLY_IS_APACHE
        ),
        help="Whether to generate maps using apache format (nginx otherwise) "
        "Defaults to `KIWIX_NIGHTLY_IS_APACHE` environ "
        f"or {Defaults.KIWIX_NIGHTLY_IS_APACHE}",
        dest="kiwix_nightly_apache",
    )
    args = parser.parse_args()

    if "kiwix" in args.projects:
        print("Generating releases map for Kiwix…")
        write_release_redirects_map(
            pathlib.Path(args.kiwix_root),
            pathlib.Path(args.kiwix_release_redirects),
            kiwix_releases,
            is_nginx=not args.kiwix_release_apache,
        )
        print("Generating nightly map for Kiwix…")
        write_nightly_redirects_map(
            pathlib.Path(args.kiwix_root),
            pathlib.Path(args.kiwix_nightly_redirects),
            kiwix_releases,
            is_nginx=not args.kiwix_nightly_apache,
        )

    if "openzim" in args.projects:
        print("Generating releases map for openZIM…")
        write_release_redirects_map(
            pathlib.Path(args.openzim_root),
            pathlib.Path(args.openzim_release_redirects),
            openzim_releases,
            is_nginx=not args.openzim_release_apache,
        )
        print("Generating nightyly map for openZIM…")
        write_nightly_redirects_map(
            pathlib.Path(args.openzim_root),
            pathlib.Path(args.openzim_nightly_redirects),
            openzim_releases,
            is_nginx=not args.openzim_nightly_apache,
        )
