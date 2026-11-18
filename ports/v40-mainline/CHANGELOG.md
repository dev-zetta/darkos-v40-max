## Image revision 7.3.4-v40.1-r1

- First full SD-card release for the V40 Max. It uses Linux 7.3.4-v40.1, the pinned Debian 13 ArkOS4Clone base, the V40 display and audio fixes, and standard PPSSPP 1.20.4.
- Adapted [ArkOS4Clone’s SDL CRC controller fix](https://github.com/lcdyk0517/arkos4clone/commit/6f3fae9106510d581b9811486d55ac4cbd3c5d84) for the shared controller database. The V40 mapping includes FN, SELECT, START, and the stick buttons.
- Adapted [dArkOS’s boot startup change](https://github.com/christianhaitian/dArkOS/commit/e752dfdb083c7f4e554339ffd2a8eeffc8f464d8) to skip the inherited console welcome service on fresh cards. Adapted [dArkOS’s root filesystem copy verification](https://github.com/christianhaitian/dArkOS/commit/3b29b1597a606b923b893a4fe983863d25ff0097) to compare staged files with the image before writing the new UUID-based `fstab`.
- Merged [ArkOS4Clone upstream through `4abb343`](https://github.com/lcdyk0517/arkos4clone/commit/4abb343) into the source tree. The parent’s board-profile, ScummVM, and Saturn changes apply to its own image and update builds. The V40 image uses its pinned base and the targeted changes above.

This prerelease targets the RK3326 V40 Max with a 720×720 panel. A physical cold boot of this revision remains pending. The image is for a fresh SD card and includes empty directories for your games and BIOS files.
