# Publish the V40 kernel on the fork

The maintainer checkout uses `fork` for the [dArkOS V40 Max repository](https://github.com/dev-zetta/darkos-v40-max). To configure that remote in a checkout which already tracks the ArkOS4Clone parent, run the following commands.

```sh
git remote add fork https://github.com/dev-zetta/darkos-v40-max.git
git push -u fork main
```

The fork's default `main` branch carries the V40 port. The commits retain upstream ancestry, component mail-patch authorship, source and license provenance, and the image-cleanup commits. Keep private SD backups, raw journals, credentials, ROMs and generated binaries outside the repository. See [upstream repositories](UPSTREAM.md#tracking-upstream-changes) for fetch commands.

The fork's [V40 mainline kernel workflow](../../.github/workflows/v40-mainline.yml) runs on V40 port changes pushed to `main` or `v40-mainline-7.3.4`. It verifies the source archive hash and exact patch profile, runs the PPSSPP configuration tests, builds the kernel, DTB and modules, and checks the configuration, DTB and symbol CRC hashes. Its downloadable artifact is the CI rebuild.

For a kernel update, wait for a successful V40 workflow run on the exact source commit, then create an annotated tag on that commit. Package the hardware-verified Image and matching DTB with the release manifest, ABI table, kernel config, installation instructions and checksums. Ship the matching upstream source archive, signature, exact patches, configuration, build scripts and licenses as corresponding source alongside it. Verify the uploaded archive digests and tag target before making the release public.

Use [KERNEL_RELEASE.md](KERNEL_RELEASE.md) for the kernel update compatibility and rollback boundary and [VALIDATION.md](docs/VALIDATION.md) for the observed hardware behavior.

For a full image, the [V40 image workflow](../../.github/workflows/v40-image.yml) runs on the same branches and on `v40-image-*` tags. Review the successful branch run and its checksum-verified artifact before tagging that exact source commit. The tag promotes the artifact for its commit, looking first on `main` and then on `v40-mainline-7.3.4`. The publish job verifies GitHub's asset digests before publishing a prerelease. Record the raw image SHA-256 when reporting a cold boot or emulator qualification on the handheld. Until then, describe the exact image as a hardware test candidate.
