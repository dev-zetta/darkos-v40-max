# Unactivated audio/performance candidates

These changes passed bounded source/build/fixture checks and were staged, but remain unactivated on the handheld. The default accepted frontend and runtime do not include them.

frontend-audio-callback.patch applies after accepted frontend source f0939909342d95aa3f327dcbf111a9a4f5d15ea9; see FRONTEND_AUDIO.md. perfmax-mainline.patch targets the retained device script SHA-256 22820af9c8dd39095db25484d7adb566b017865795f682c64b89b90bbf7d6f27, not an arbitrary upstream script. It selects a supported mainline GPU userspace maximum within the existing cap only for performance/kodi, retaining an explicit powersave choice. Its 28 Bash fixture checks passed, but legacy CPU/DMC writes and command sequencing are not made atomic by that change.

Do not install either candidate merely because menu, rendering and speaker-routing acceptance passed. Audible menu/game scrambling remains unresolved. The optional PL330 diagnostic is separately controlled by kernel preparation and its default-off parameter.
