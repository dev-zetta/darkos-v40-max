# Build the pinned mainline components

Use Python 3.12 or newer, patch, make, an AArch64 cross toolchain, bc, bison, flex, libelf/libssl development headers, dtc, kmod, cpio, CMake, Ninja, Meson, Cargo and QEMU user tools. Dockerfile reconstructs the multiarch builder from a pinned Debian base without workstation-local image names. Its apt package resolution is not snapshot-pinned; docs/original-builder-packages.tsv records the original package versions. The tested kernel compiler was GCC 14.2.0 with binutils 2.44. A rebuilt Image need not be byte-identical on a different toolchain; preserve its actual hashes and ABI reports.

From this directory, download the exact archive and detached signature from the URLs in kernel/source-lock.json. Check the SHA-256 first; verify the uncompressed tar signature with the independently authenticated Linux stable-maintainer key. The supplied signature and signed checksum list are provenance inputs, not a substitute for authenticating the key. Preparation refuses another archive, an existing source path, unexpected patch preimages or a different patched source result.

```sh
python3 scripts/prepare_kernel.py --archive /cache/linux-7.3.4.tar.xz --source /work/linux-7.3.4-v40
bash scripts/build_kernel.sh /work/linux-7.3.4-v40 /work/kernel-output
```

The kernel output contains Image, the matching rockchip/rk3326-v40-max.dtb, Module.symvers and a freshly installed/indexed module tree. The exact committed config enables the joystick parent gate, the private board drivers, AArch32 support, native RTL8851BU, Btrfs and Panfrost. olddefconfig must retain the committed configuration exactly; investigate compiler/Kconfig drift rather than accepting a silent ABI change. Build and install modules from the same source/configuration; release-string equality alone does not establish ABI compatibility. Previously retained module imports were checked against all symbol CRCs, including the earlier lesson that NL80211 callback-layout configuration can matter beyond vermagic.

For the optional diagnostic only, add --continuous-dma when preparing a separate new source tree. That adds the source patch but leaves the module parameter off by default; explicitly setting pl330.v40_continuous=1 in the boot command line reproduces the latest diagnostic selection. It has exact board/controller/request/FIFO/burst/period/ring guards. A wedged DMA engine can block sleepable audio close, and coalesced events cannot be reconstructed. This is not a production audio-quality recommendation.

For each component in components/source-lock.json, clone its repository, check out the pinned base commit, and apply the files in its series with git am. Mail patches preserve the original authors, including the frontend MPP contribution; ENABLE_MPP_VIDEO remains OFF in the accepted frontend build. Applying patches reconstructs the accepted source tree, while commit object IDs can differ because committer metadata changes. Do not select experimental frontend patches by default.

Build private SDL for both aarch64-linux-gnu and arm-linux-gnueabihf with CMake: shared ON, static/tests OFF, KMSDRM and KMSDRM_SHARED ON, OFFSCREEN ON, X11/Wayland/PulseAudio/PipeWire/JACK/SNDIO/ARTS/ESD OFF, and the target libgbm.so/libdrm.so passed explicitly as GBM_LIB/DRM_LIB. Check the generated SDL_config.h for SDL_VIDEO_DRIVER_KMSDRM_DYNAMIC_GBM equal to libgbm.so.1 and ALSA enabled. The global vendor SDL embeds a proprietary Mali GBM SONAME and cannot be used for this path. Keep the valid-CRTC restoration patch in the private build.

Build the accepted frontend as Release for AArch64/Cortex-A35 with GLES=ON, CEC=OFF, ENABLE_MPP_VIDEO=OFF, CMAKE_SKIP_RPATH=ON and the target FreeImage include/library paths. Include the complete matching resources directory beside the relocated executable; fonts/icons/translations are required at runtime. Build ogage from its pinned Cargo.lock for aarch64-unknown-linux-gnu with aarch64-linux-gnu-gcc as linker. The accepted frontend source is f0939909342d95aa3f327dcbf111a9a4f5d15ea9, not the unactivated callback candidate.

Build Debian's Mesa 25.0.7-2+deb13u1 source, including its Debian patches, separately for both target architectures. The accepted Meson profile uses gallium-drivers=panfrost,softpipe, vulkan-drivers empty, platforms=x11, glx=dri, egl/gbm/glvnd/gles1/gles2 enabled, opengl=true, shared-glapi enabled, LLVM disabled and video/VA/VDPAU/OpenCL/Rusticl/Nine/XA/Teflon/tests disabled. Use the local VERSION suffix 25.0.7-2+deb13u1-v40gles1 and install privately under /usr/local/lib/v40-mainline/lib/TRIPLET. Debian's prebuilt Mesa disables GLES1 and is insufficient for the fixed-function frontend. Package GLVND dispatch, DRI/GBM backends, required dependency closure and notices with both architectures; do not substitute global vendor Mali libraries.

The exact Debian Mesa source archive URLs and hashes are in graphics/source-lock.json. graphics/mesa-legacy-soname.c can be built separately for each architecture as a shared library with SONAME libMali.so and --no-as-needed dependencies on standard libEGL.so.1, libGLESv1_CM.so.1, libGLESv2.so.2 and libgbm.so.1; provide libMali.so.1 as a symlink. This forwards standard API dependencies for old programs without implementing proprietary Mali ioctls. The loader, GLES1 and SDL GLES1 probes are supplied in graphics. diagnostics/framebuffer-capture.c builds with the target libdrm headers and -ldrm and can be staged as /usr/local/libexec/v40-drm-capture for the optional boot collector; it never acquires DRM master or changes modes. Retain its MIT notice. These helpers do not remove the need to resolve and verify the complete target library closure.

Once that graphics closure exists in a separate staging root, render the runtime text overlay and its coupled frontend digest consumers. This command writes a new local directory and never mounts or modifies an SD card:

```sh
python3 scripts/stage_runtime.py --frontend /work/frontend/emulationstation --resources /work/frontend-source/resources --hotkey /work/ogage/target/aarch64-unknown-linux-gnu/release/ogage --graphics-root /work/graphics-root --output /work/runtime-overlay
python3 tests/test_ppsspp_settings.py
```

Kernel source preparation and source hashes, component patch replay, runtime rendering and configuration behavioral checks are independently testable. They do not establish a fresh full-image build or physical acceptance of new binaries. Preserve the tested source/binary identities in docs/ARTIFACTS.json and record new identities for every rebuild.
