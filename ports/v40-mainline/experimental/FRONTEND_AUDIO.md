# Audio callback candidate

This branch moves playlist scanning, song loading/freeing and application-state updates out of SDL_mixer's music-finished callback. The callback only sets an atomic notification; AudioManager::update consumes it on the UI thread. Removing the hook precedes cancelling the notification so an in-flight callback cannot reassert a stale request after stopMusic.

The complete production AudioManager source passed eight behavioral fixture cases. The accepted V3 source is a negative control for callback-thread work, and a mutation reversing hook removal and flag clearing fails cancellation coverage. An AArch64 build completed with unchanged dynamic-library dependencies; its callback contains no function calls. This is bounded software evidence, not proof of physical audio quality.

The built V4 candidate SHA-256 is 39339a1e77bcc7582958a807751a62de2e79bcac91a0918a0094c79c1feb48ac. It was staged but not activated on the handheld. The physically accepted frontend remains parent commit f0939909342d95aa3f327dcbf111a9a4f5d15ea9 with binary SHA-256 74e0c5f9adace11468d4aabb243fc60b0e39fecf48eda72c72a53d10d1042e62. This track-transition correction does not establish a fix for navigation clicks, preview mixing or PSP audio scrambling.
