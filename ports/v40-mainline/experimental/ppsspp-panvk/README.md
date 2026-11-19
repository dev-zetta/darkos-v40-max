# PPSSPP direct KMS with PanVK on the V40 Max

This optional source patch enables PPSSPP to acquire the panel through Vulkan when SDL runs on KMSDRM. The default image continues to use the standard standalone OpenGL route. The tested changes cover DRM connector acquisition and release, recovery of Linux instance slots after a crash, and a separate return status for Vulkan startup failure.

## Source and build

The patch starts at PPSSPP v1.20.4, commit `fa50bb1976065c4f8b1b47af227d367fe9771555`, and reproduces the tested source at `20a2f45e08c5ec73c25efc7bc4c2f7ced851f195`. It was checked against the pristine release archive. Files changed by the patch retain their upstream license. [PPSSPP v1.20.4 release and source archive](https://github.com/hrydgard/ppsspp/releases/tag/v1.20.4)

| Input | SHA-256 |
| --- | --- |
| `ppsspp-1.20.4.tar.xz` | `4de21db3105d9d81a465a8a7e78c68ee3c0e0bf6597d1c1d530f7555f3ad8b31` |
| `ppsspp-v1.20.4-v40-panvk.patch` | `72eddb79b39b70fe3ecb96e9d4e1a146bd12d14471e2e94af9a2e93a8eaa17d7` |
| Tested ARM64 `PPSSPPSDL` | `48c89b7b845339d1f2d020be79544ca784a4d9630f4bfd7633cf432d514630e5` |
| Tested driver source `mesa-26.3.1.tar.xz` | `4e4e438eac7b840a9383988cbb7c08dad8041da544b9319fc26d319fa7348961` |

Apply the patch to a fresh extraction before configuring. Use the ARM64 toolchain, bundled FFmpeg build, and SDL2/EGL/GLES2 CMake options from [the standard PPSSPP build recipe](../../scripts/build_image_ppsspp.sh). Add `-DUSE_VULKAN_DISPLAY_KHR=ON` to the configure command and build the `PPSSPPSDL` target with its matching assets.

```sh
git -C "$source" apply --check "$patch"
git -C "$source" apply "$patch"
```

## Run on the handheld

Use a PanVK ICD with Mali-G31 support and the `VK_KHR_display`, `VK_EXT_direct_mode_display`, and `VK_EXT_acquire_drm_display` extensions. The verified system used Linux 7.3.4-v40.1 and Mesa 26.3.1 from a separate ARM64 PanVK build with direct-display WSI. Release EmulationStation's display before launching. Use an isolated PPSSPP profile with `GraphicsBackend = 3 (VULKAN)` and `SoftwareRendering = False` under `[Graphics]` in `ppsspp/PSP/SYSTEM/ppsspp.ini`. Keep the working profile and its saves in place.

```sh
SDL_VIDEODRIVER=KMSDRM \
XDG_CONFIG_HOME="$profile" \
VK_DRIVER_FILES="$panvk/share/vulkan/icd.d/panfrost_icd.cortex-a35.json" \
DRIRC_CONFIGDIR="$panvk/share/drirc.d" \
PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1 \
PPSSPP_KMSDRM_PANVK=1 PPSSPP_KMSDRM_CONNECTOR=DSI-1 \
"$build/PPSSPPSDL" --fullscreen "$rom"
```

Status 69 from direct-KMS startup means Vulkan was unavailable before emulation began. A launcher can wait for that process to exit, then retry standard standalone OpenGL once with the Vulkan environment cleared. The handheld test verified a missing-connector fallback, and two successful Vulkan launches acquired the Mali-G31 DSI connector, opened a 44.1 kHz SDL stream with nonzero samples, and released the display on exit.

## Observed performance

| Matched replay scene | OpenGL speed | PanVK speed | Audio and presentation |
| --- | ---: | ---: | --- |
| GTA Vice City Stories, first in-engine cutscene | 25.3–25.4% | 99.88–99.94% with frame skip 1 | About 15 distinct frames per second and persistent internal audio underruns with PanVK. |
| Alien Syndrome, character creation at 1× PSP with frame skipping off | 99.91–99.94% | 92.70–93.27% | OpenGL had zero internal underruns. PanVK had about 23–25 per second. |

The speed figures come from an instrumented comparison build on the same handheld. The final source patch was verified separately for startup, fallback and delivery of audio samples. The GTA result uses a different presentation workload with frame skipping, and the audio meter measured digital samples before the speaker.
