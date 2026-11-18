# V40 Max Linux 7.3.4-v40.1 kernel update

Use this kernel update only on an existing V40 Max mainline installation with the tested RK3326, 720×720 board wiring. The reference factory DTB SHA-256 is `06b611d370f32165d340fb8184f54cc2f735fb312ed7b7a8e59e4cb028e3d05f`. This prerelease supplies an Image for the previously validated bootloader, mainline DTB, initramfs and module ABI. A stock/BSP card needs a complete port integration first.

## Contents and validation

The kernel archive contains the hardware-tested ARM64 Image (Build ID `9b9fa24e4d8ee542980a34654afa47e9bde5bbd9`), its matching DTB, configuration, exported symbol CRCs and checksums. The corresponding-source archive includes the Linux source, exact patch series, configuration and build scripts. See [the release manifest](kernel/release-7.3.4-v40.1.json) for exact hashes and boot parameters.

The I²S1 driver applies the 600 MHz fractional-divider input limit after the PX30 controller protects its critical clocks. The user confirmed a normal cold boot and reported that the scrambling was gone in the tested PPSSPP game. SSH verified the running kernel and a 44.1 kHz playback stream with zero ALSA XRUNs during the sample. Idle speaker static and the menu-entry pop remain open. In a separate comparison, placing the Wi-Fi dongle away from the handheld on a USB extension stopped the repeating cracks while Wi-Fi stayed functional.

## Update an existing card

1. Verify the downloaded archives with the release's `SHA256SUMS`, then verify the extracted payload against its own `SHA256SUMS`. Back up `boot.ini` and the existing boot files to your PC.
2. Before changing the boot selector, confirm it already starts the tested board on Linux `7.3.4-v40.1`. Compare the selected DTB and existing Image to the release manifest. The documented compatible prior Image has SHA-256 `9f62be8d129d363e0ca123bb3ea8ab6358e5abb3484a827a88f58b43b53d387f`. The board DTB must match `dtb_sha256` even if it uses a different filename. Keep the matching installed modules and initramfs. If your existing Image comes from another build, verify its installed modules against the included `Module.symvers` before proceeding.
3. Copy the new Image to a fresh directory on BOOT, for example `mainline/i2s-clock-7.3.4-v40.1/Image`. Check the copied file against `image_sha256`. Change only the Image path in your existing `boot.ini`, preserving its root UUID, DTB, initramfs, boot options and load addresses. Save the selector last, safely eject the card and perform a full power-on.
4. Confirm the menu and audio return. If startup fails, power off and restore the saved `boot.ini` on the PC to select your previous Image.

## Build the exact source profile

From the source archive's top-level directory, run the following with the kernel toolchain listed in [BUILD.md](BUILD.md). The tracked Dockerfile's `kernel-builder` target supplies the Debian tools. The two flags include the diagnostic code retained in the hardware-tested build. Both features default off in the drivers. The tested boot kept standard PL330 DMA and enabled the DAC guard, as recorded in the release manifest.

```sh
port=ports/v40-mainline
python3 "$port/scripts/prepare_kernel.py" --archive linux-7.3.4.tar.xz \
  --source linux-7.3.4-v40 --continuous-dma --dacmt-guard
KCFLAGS=-Werror bash "$port/scripts/build_kernel.sh" linux-7.3.4-v40 kernel-output
```

Use the SHA-256 and Build ID from your own build when identifying rebuilt artifacts. The GitHub Actions output records a clean rebuild and verifies the config, DTB and module ABI against the release manifest.
