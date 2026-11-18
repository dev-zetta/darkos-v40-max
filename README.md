# dArkOS V40 Max

This fork brings ArkOS4Clone’s Debian-based dArkOS userspace to the RK3326 V40 Max with a 720×720 display and **Linux 7.3.4-v40.1**. It includes the V40 panel and controller support, I²S audio clock correction, speaker routing, battery indicators, RTL8851BU USB Wi-Fi support, and PPSSPP rendering and hotkey fixes.

## Install

- For a fresh SD card, follow the [full image installation and verification guide](ports/v40-mainline/IMAGE.md). Use a spare card of at least 16 GB.
- For a compatible existing V40 installation, follow the [kernel update instructions](ports/v40-mainline/KERNEL_RELEASE.md). [Download the kernel update](https://github.com/dev-zetta/darkos-v40-max/releases/tag/v40-kernel-7.3.4-v40.1).

See the [V40 port overview](ports/v40-mainline/README.md), [build instructions](ports/v40-mainline/BUILD.md), and [hardware validation results](ports/v40-mainline/docs/VALIDATION.md). GitHub Actions builds the [full image](https://github.com/dev-zetta/darkos-v40-max/actions/workflows/v40-image.yml) and the [kernel](https://github.com/dev-zetta/darkos-v40-max/actions/workflows/v40-mainline.yml).

## Maintainer

[Gabriel Max](https://github.com/dev-zetta) · [dev@zetta.app](mailto:dev@zetta.app)

See [upstream repositories, source provenance, and credits](ports/v40-mainline/UPSTREAM.md).
