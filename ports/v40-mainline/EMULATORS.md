# V40 Max emulator changes in image r2

The V40 image builds RetroArch 1.22.2 for AArch64 and ARM hard-float with DRM/KMS, GBM, Mesa EGL and ALSA. On the development card this restored scanout for the tested libretro launchers. The rebuilt ARMHF PCSX ReARMed NEON core loads with the normal non-executable-stack policy. The Linux uinput add-on uses the same V40 kernel configuration and exported symbol versions. The installer repairs the V40 GO-Super profile for both RetroArch variants. Tested menu and exit chords were FN + X and FN + START for RetroArch.

The Flycast r7 launcher uses the private ARMHF Mesa path for Dreamcast, Naomi and Atomiswave. The development card passed display and control checks for Crazy Taxi 2, Guilty Gear X and Demolish Fist. Demolish Fist ran below its native speed. These checks cover the named games and scenes. The image leaves game and BIOS directories for the user to populate.

Standard standalone PPSSPP stays on OpenGL. After a crash or interrupted launch, an orphaned POSIX shared-memory counter could make the next process a secondary instance and set its audio volume to zero. The launcher serializes starts, checks for a live emulator, and removes a stale counter of the expected type, size and ownership before a new launch. The separate Vulkan and frameskip trials improved some GTA Vice City Stories scenes and slowed one Alien Syndrome comparison. Their results apply to those workloads. DraStic two-screen orientation and FN menu behavior were checked on the development card with a separately supplied installation. The public image omits DraStic.

## PAL Super Mario 64

The launch profile checks the game and selected ARMHF ParaLLEl N64 route before enabling the private core and display presenter. The presenter queues completed frames for DRM vblank delivery. The recompiler verifies resident guest code and prepares at most one block every two native video interrupts, using the ordinary in-memory emitter and invalidation rules. The profile covers the 86 blocks first used at the three observed compilation bursts. The same title scope enables Rice’s lazy shader variants and a private Mesa disk cache.

Three fresh normal launches on the development card took the same controller-driven castle route at 50.026–50.031 guest FPS. Each presented 699 of 700 frames, with a maximum recorded display gap of 49.45 ms. Digital PCM passed the write, silence, clipping and sample continuity checks. Menu, resume and exit passed. A separate Mario Kart 64 launch selected the shared RetroArch route. The audio tap measures the digital stream. Its results cover the tested castle replay.

The release builds these components from pinned sources and shipped patches. Mesa generates its cache on the card. The release includes no development-card shader cache, game, BIOS, or save state. Its initial scene loads may still compile shaders. The tested development-card numbers used a populated cache. Hardware qualification of the exact public image, including cold-cache behavior, is separate from the replay and the image build checks.

## Build records

The image job packages `emulator-build.json`, `emulator-sources.tar.xz`, `sm64-build.json` and `sm64-sources.tar.xz` with the image. They provide the build identities and corresponding sources with the applied patches. See [BUILD.md](BUILD.md) for build entry points and [IMAGE.md](IMAGE.md) for installation.
