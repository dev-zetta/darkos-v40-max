# Sources, authorship and licensing

## Tracking upstream changes

The GitHub fork parent is [lcdyk0517/arkos4clone](https://github.com/lcdyk0517/arkos4clone) on `main`. The Debian-based userspace upstream is [christianhaitian/dArkOS](https://github.com/christianhaitian/dArkOS) on `master`. The repositories have separate Git histories. Fetch both histories and review dArkOS changes individually for compatibility with the V40 image and runtime.

In the maintainer checkout, `origin` tracks the ArkOS4Clone parent, `darkos-upstream` tracks canonical dArkOS, and `fork` points to this repository. To configure the upstream remotes in a fresh clone of this fork, add them under separate names.

```sh
git remote add --no-tags -t main arkos4clone-upstream https://github.com/lcdyk0517/arkos4clone.git
git remote add --no-tags -t master darkos-upstream https://github.com/christianhaitian/dArkOS.git
git fetch --filter=blob:none arkos4clone-upstream
git fetch --filter=blob:none darkos-upstream
```

Use `git fetch --filter=blob:none origin` in the maintainer checkout to refresh the ArkOS4Clone parent. Fetching upstream Git refs leaves the released base-image lock in `image-inputs.json` in effect until a reviewed image update changes it.

### November 2026 sync

The source tree merges [ArkOS4Clone main through `c6b2551`](https://github.com/lcdyk0517/arkos4clone/compare/4abb343...c6b2551). The V40 image is assembled from the checksum-locked Debian base and the V40 overlays. The parent’s new Kodi, netplay, rotation fixes, and additional emulator packages are part of the upstream source merge for its own builds. The V40 build uses its Linux 7.3.4 kernel, source-built graphics and frontend, and tested emulator paths.

The V40 bootstrap now locks the [R36S Plus donor from `4abb343`](https://github.com/lcdyk0517/arkos4clone/blob/4abb34366bb76b93e846fb3040c2511304badf9b/boot/dArkOS/consoles/r36splus/rk3326-r36splus-linux.dtb) in the port. Upstream can update its own donor without changing the V40 boot chain. The build verifies the V40 donor’s SHA-256 before deriving the Max panel profile.

[ArkOS4Clone PR #533](https://github.com/lcdyk0517/arkos4clone/pull/533) is represented by `9cea22a`, `abd904b`, and `2ccb6dd` in this fork. The parent-style image assembly has those cleanup changes. The V40 builder clears generated APT caches, creates an empty games partition, and drops the entire inherited `roms.tar`, including its JDK payload. The V40 image keeps installed package documentation and notices.

The [canonical dArkOS changes through `e9fb727`](https://github.com/christianhaitian/dArkOS/compare/86bac70...e9fb727) cover core-package installation, chroot build efficiency, and RK3566 or RK2023/RG353 targets. The V40 runtime already applies 512 KiB read-ahead to MMC disks, as proposed in the [dArkOS build-efficiency series](https://github.com/christianhaitian/dArkOS/commit/f2e9ccb). Its releases continue to use the port’s separate image assembly and pinned emulator builds.

## Component provenance

The battery follow-up backports the authored RK817 NVRAM-scale and counter-first/rested-OCV fixes carried by ROCKNIX PR3305 at merge bc31d4293ac079e92e391ee737ad47064be82009. Chris Morgan and Jacob Cook's original headers, sign-offs and assistance attribution remain intact in kernel patches 0003 and 0004. The learned-FCC overflow guard and optional DC-input reporting patch are separate local changes. The latter uses the preserved factory GPIO0_B3 and pin bias; it does not import another board's amplifier GPIO or charger power policy. The frontend battery/layout/newline/footer fixes are recorded as separate local commits after the retained author-preserving series. See docs/BATTERY_STATUS_20261116.md and the patch/source locks for exact scope and hashes.

ArkOS4Clone is based on lcdyk0517/arkos4clone. This fork retains upstream history, authors and its MIT license; the starting integration includes the three existing image-cleanup commits rather than flattening them into this port. The frontend derives from lcdyk0517/EmulationStation-fcamod, the hotkey daemon from lcdyk0517/ogage, SDL from libsdl-org/SDL, Linux from kernel.org, and Mesa from Debian's patched 25.0.7-2+deb13u1 source package. Component repository URLs, exact base/accepted commits and author-preserving mail patches are in components/source-lock.json.

Linux's archive checksum and source-patch preimages/results are recorded in kernel/source-lock.json. The archive is linux-7.3.4.tar.xz, SHA-256 `b11b6df8295e8e991ff040b71aaa4994a8b55caa23b6b092907f195b5840fd1f`; its detached uncompressed-tar signature was verified using Greg Kroah-Hartman's fingerprint `647F28654894E3BD457199BE38DBBDC86092693E`. The source archive remains external. The default board patch was derived by comparing the exact compiled source against all 95,979 regular files in the signed archive, plus the seven explicitly added board files. Generated build objects are excluded. The separate PL330 patch is not silently folded into the default board port.

Hardkernel and lcdyk's combined gamepad driver comes from BSP commit `923a6105701d03fbaa597273a42a49f6434cc4da`. Preserve its original GPL notices and authorship. The RK817 codec retains Rockchip's copyright and board-scoped additions; the panel timing/packet records come from the preserved factory DTB and the BSP DCS encoder behavior. The optional PL330 adaptation credits the retained Samsung/Linux authors, Huibin Hong and Sugar Zhang's 2022 cyclic-DMA work, and Alexander Kochetkov's 2017 continuous-cyclic work. It is adapted source, not an unchanged upstream cherry-pick. The retained post-PHY-rearm proposal is not in this port's default patch set.

Kernel source and patches retain their per-file SPDX/GPL terms, including GPL-2.0-only and GPL-2.0-or-later where stated; the gamepad says GPL version 2 or later. Device-tree/binding files retain their stated dual licenses. The hotkey daemon is GPL-3.0; SDL uses the zlib license; the frontend uses the retained MIT notice. The parent repository's MIT license does not relicense these components. License texts are retained under licenses, and new preparation/configuration helpers carry SPDX-License-Identifier: MIT. Include complete corresponding source and the full upstream license/notice sets when distributing compiled components; this source tree is not a binary-license clearance claim.

Runtime source was taken from the tested migration's text helpers and service drop-ins, with the frontend digest converted to a staging-time token. Raw journals, Wi-Fi profiles/passwords, SSH host keys, SD images, ROMs, BIOS, saves, device-specific settings snapshots, personal recording attachments and generated binaries are excluded from this port. Public validation records use artifact hashes and bounded observations rather than raw private evidence.
