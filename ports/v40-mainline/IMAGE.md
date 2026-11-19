# ArkOS4Clone V40 Max image

This image targets the tested RK3326 V40 Max board with a 720×720 panel. It uses the publicly released Debian 13 dArkOS4Clone userspace, the V40 Linux 7.3.4-v40.1 kernel, private ARM64 and ARM32 Mesa/SDL, EmulationStation V6, and standard PPSSPP 1.20.4. It carries the mainline panel, gamepad, speaker routing, I²S clock, and battery indicator fixes. Image r2 adds the DRM/KMS RetroArch builds, corrected emulator launch paths, the uinput add-on, and the PAL Super Mario 64 launch profile. See the [emulator notes](EMULATORS.md) for coverage. Use a separate SD card of at least **16 GB**. Flashing the image replaces the partition table and files on the selected card.

Image r3 fixes a Mesa startup failure in the verified PAL Super Mario 64 launch from EmulationStation. For the hardware check, launch the verified PAL ROM from the game list and confirm the title screen animates, the castle renders, and the usual exit hotkey returns to the menu. Mesa populates the game's shader cache during play.

## Install and test

1. Download the filesystem image and its checksums from the corresponding [GitHub release](https://github.com/dev-zetta/darkos-v40-max/releases). For an Actions candidate, use the `v40-bootable-image` artifact from the matching workflow run.
2. Download every image part listed in `SHA256SUMS`. Verify the downloaded files with `sha256sum --ignore-missing -c SHA256SUMS`. If the image has numbered chunks, concatenate only its `.img.xz.NNN` parts in ascending order, then decompress the resulting `.img.xz`. Verify the raw `.img` with `sha256sum -c IMAGE-SHA256SUMS`.
3. Write the raw image to a spare SD card using a raw image writer. Insert it in the V40 Max and power it on from fully off. The card contains a FAT BOOT partition, a Btrfs system partition, and an exFAT EASYROMS partition. Add your own game and BIOS files to EASYROMS.
4. Confirm that the menu appears, the display and controls work, the speaker plays audio, and a native RTL8851BU Wi-Fi adapter reconnects. For PPSSPP, check the game picture, audio, and FN/SELECT/START. Return to your existing SD card if the test fails.

The full image uses the public Clone-u-boot binaries and a 720×720 bootloader DTB derived from the public R36S Plus profile. The previously tested in-place update kept the factory bootloader. A fresh image has a different boot chain and needs its own cold-boot test. Hardware validation should name the image SHA-256. A successful CI build or QEMU test covers only the paths it exercised. See [validation](docs/VALIDATION.md) for the tested kernel and the outstanding hardware checks.

The image disables the inherited automated updater, first-boot scripts, and console welcome message. Remote services are off initially. Set up your own SSH public key for user `ark` before enabling SSH. The image generates its own host identity and carries no developer Wi-Fi profiles, games, saves, or BIOS files. The build removes the legacy premium PPSSPP executable, selected restricted standalone emulator directories, raw proprietary Mali blobs, and the upstream game-partition seed archive. V40 Max Tools gives EmulationStation a system to show on an empty games card. The default theme is included as editable source. See the [image changelog](CHANGELOG.md) for the upstream changes included in each revision.

The correction for PPSSPP audio scrambling is separate from USB-dependent speaker clicks. Moving the USB Wi-Fi dongle away on an extension helped on the tested device. Steady static, the menu-entry pop, and broad suspend and emulator coverage remain open.

## Build and provenance

[image-inputs.json](image-inputs.json) records the public base parts, bootloader profile, BusyBox and Realtek firmware identities. [BUILD.md](BUILD.md) describes the kernel and userspace source inputs. The [image workflow](../../.github/workflows/v40-image.yml) builds the kernel and modules, private graphics and frontend, PPSSPP, and the RetroArch and libretro overlay in independent jobs. It then combines the outputs into a fresh disk image and verifies the partitions and boot files. The tagged publish job promotes the verified archive built for the same commit without regenerating the partitions.

To assemble locally, use Linux with Bash, Python 3, jq, curl, xz, 7z, zstd, dosfstools, btrfs-progs, exfatprogs, util-linux, device-tree-compiler and rsync. The assembler needs root for temporary loop-backed mounts. Inputs are the kernel payload directory, the runtime overlay merged with the emulator overlay, and the standard PPSSPP installation. The kernel payload contains `Image`, `rk3326-v40-max.dtb`, `bootstrap.dtb` from `build_uboot_profile.py`, and the built `modules/7.3.4-v40.1` tree with its ABI-checked uinput add-on.

```sh
sudo bash ports/v40-mainline/scripts/build_full_image.sh \
  /work/v40-scratch /work/kernel-payload /work/runtime-overlay \
  /work/ppsspp /work/v40-outputs
```

An optional sixth argument is a local copy of the exact upstream `dArkOS4Clone-20261008.img.xz` or its decompressed `.img`. The builder validates the input and uses a disposable loop-backed copy. The scratch and output directories must be new. The builder never opens an SD card as its destination.

This non-commercial test image credits [ArkOS4Clone](https://github.com/lcdyk0517/arkos4clone/releases/tag/20261008), [dArkOS](https://github.com/christianhaitian/dArkOS/blob/86bac70b51f6264670b95020aa7d3cf2cede622d/LICENSES.md), Debian, the Linux and U-Boot maintainers, and the individual runtime authors. Existing component terms and notices apply. Matching build scripts and component source identities are in the tagged tree.
