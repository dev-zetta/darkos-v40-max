## Image revision 7.3.4-v40.1-r2

- Use RetroArch 1.22.2 with Mesa and ordinary DRM/KMS on ARM64 and ARMHF. Rebuild the ARMHF PCSX ReARMed NEON core with a non-executable stack, and repair the GO-Super RetroArch face button and stick bindings.
- Use a private V40 RetroArch presenter and ParaLLEl N64 core for the verified PAL Super Mario 64 launch. Prepare 86 verified guest code blocks before demand, avoid eager Rice shader variants, and populate a separate Mesa cache during play.
- Serialize standard standalone PPSSPP launches and recover a stale same-user instance counter that could mute game audio after an interrupted run.
- Build and install the uinput add-on against the unchanged Linux 7.3.4-v40.1 module ABI, with access for the input group.
- Use the private ARMHF Mesa route for the inherited Flycast r7 launchers for Dreamcast, Naomi and Atomiswave. Supply your own appropriate BIOS files.

The three normal-launch castle replays on the development card measured 50.026–50.031 guest FPS, 699 displayed frames of 700 each, and a longest display gap of 49.45 ms. They passed the automated digital audio and control checks. The public image builds the emulator binaries from source and starts with an empty shader cache. A V40 Max cold boot of the exact r2 image and hardware qualification of its rebuilt emulator binaries remain pending. [Emulator evidence and scope](EMULATORS.md)

## Image revision 7.3.4-v40.1-r1

- First full SD-card release for the V40 Max. It uses Linux 7.3.4-v40.1, the pinned Debian 13 ArkOS4Clone base, the V40 display and audio fixes, and standard PPSSPP 1.20.4.
- Adapted [ArkOS4Clone’s SDL CRC controller fix](https://github.com/lcdyk0517/arkos4clone/commit/6f3fae9106510d581b9811486d55ac4cbd3c5d84) for the shared controller database. The V40 mapping includes FN, SELECT, START, and the stick buttons.
- Adapted [dArkOS’s boot startup change](https://github.com/christianhaitian/dArkOS/commit/e752dfdb083c7f4e554339ffd2a8eeffc8f464d8) to skip the inherited console welcome service on fresh cards. Adapted [dArkOS’s root filesystem copy verification](https://github.com/christianhaitian/dArkOS/commit/3b29b1597a606b923b893a4fe983863d25ff0097) to compare staged files with the image before writing the new UUID-based `fstab`.
- Merged [ArkOS4Clone upstream through `4abb343`](https://github.com/lcdyk0517/arkos4clone/commit/4abb343) into the source tree. The parent’s board-profile, ScummVM, and Saturn changes apply to its own image and update builds. The V40 image uses its pinned base and the targeted changes above.

This prerelease targets the RK3326 V40 Max with a 720×720 panel. A physical cold boot of this revision remains pending. The image is for a fresh SD card and includes empty directories for your games and BIOS files.
