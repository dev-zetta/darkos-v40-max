# Publish the V40 kernel on the fork

Create a GitHub fork of lcdyk0517/arkos4clone under the intended owner, then add that fork as a separate remote in this checkout. The existing origin still points to upstream. Replace OWNER with the actual account or organization; the commands below are instructions, not actions already performed.

```sh
git remote add fork https://github.com/OWNER/arkos4clone.git
git push -u fork v40-mainline-7.3.4
```

Select that branch for reviewing or developing the mainline port. The new commits retain upstream ancestry, component mail-patch authorship, source/license provenance and the existing image-cleanup commits. The port includes only its reviewed source/docs/configuration/patches and public artifact identities; the private workspace evidence is outside this repository. Do not add SD backups, raw journals, credentials, ROMs or generated binaries to a later commit.

The fork's [V40 mainline kernel workflow](../../.github/workflows/v40-mainline.yml) runs on V40 port changes pushed to `v40-mainline-7.3.4`. It verifies the source archive hash and exact patch profile, runs the PPSSPP configuration tests, builds the kernel, DTB and modules, and checks the configuration, DTB and symbol CRC hashes. Its downloadable artifact is the CI rebuild. The inherited BSP image workflow is for the legacy images.

For a kernel update, wait for a successful V40 workflow run on the exact source commit, then create an annotated tag on that commit. Package the hardware-verified Image and matching DTB with the release manifest, ABI table, kernel config, installation instructions and checksums. Ship the matching upstream source archive, signature, exact patches, configuration, build scripts and licenses as corresponding source alongside it. Verify the uploaded archive digests and tag target before making the release public.

Use [KERNEL_RELEASE.md](KERNEL_RELEASE.md) for the kernel update compatibility and rollback boundary and [VALIDATION.md](docs/VALIDATION.md) for the observed hardware behavior.

For a full image, the separate [V40 image workflow](../../.github/workflows/v40-image.yml) runs on V40 branch pushes and `v40-image-*` tags. Review the branch run, its checksum-verified artifact and cold-boot results before tagging the same tested source. The tag promotes that exact branch artifact while it remains available. The publish job verifies GitHub's asset digests before publishing a prerelease.
