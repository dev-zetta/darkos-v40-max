# Publish this development branch as a fork

Create a GitHub fork of lcdyk0517/arkos4clone under the intended owner, then add that fork as a separate remote in this checkout. The existing origin still points to upstream. Replace OWNER with the actual account or organization; the commands below are instructions, not actions already performed.

```sh
git remote add fork https://github.com/OWNER/arkos4clone.git
git push -u fork v40-mainline-7.3.4
```

Select that branch for reviewing or developing the mainline port. The new commits retain upstream ancestry, component mail-patch authorship, source/license provenance and the existing image-cleanup commits. The port includes only its reviewed source/docs/configuration/patches and public artifact identities; the private workspace evidence is outside this repository. Do not add SD backups, raw journals, credentials, ROMs or generated binaries to a later commit.

The source/configuration/staging checks are recorded in docs/SOURCE_CHECKS.json. They do not establish a new full image build or a finished public hardware release. Complete the remaining validation in docs/VALIDATION.md and assemble corresponding-source/license notices before publishing compiled binaries. The optional PL330 diagnostic and experimental audio/performance candidates must retain their explicit unresolved/unactivated labels.
