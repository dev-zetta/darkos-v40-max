# Standalone console audio diagnostic

`v40-audio-test.c` is a Linux/ALSA C program for separating known PCM content from frontend, video and emulator behavior. It links only libasound, libm and libc. It does not use SDL, a graphical toolkit, a decoder or a mixer API. It does not edit audio configuration, gain, routes, clocks, GPIOs or kernel parameters. Ordinary ALSA open/prepare/close still causes the existing driver's normal power transitions.

Build on the intended userspace with ALSA development headers and a C compiler. Cross-compilation additionally requires the matching target library and an appropriate libc/toolchain; a successful host build is not ARM64 runtime acceptance.

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -Wconversion -Wshadow \
  v40-audio-test.c $(pkg-config --cflags --libs alsa) -lm -o v40-audio-test
./v40-audio-test --selftest
./v40-audio-test --dump new-reference.raw
```

`--selftest` loads the library and reports the fixed generator parameters without opening a PCM. `--dump` writes the generated stereo S16_LE stream to a new file without playback; independently check its channel invariants rather than treating the selftest report alone as waveform validation. The implementation targets little-endian Linux as used by the tested AArch64 handheld.

Playback requires an explicit `--run` and a process-private ALSA configuration containing `pcm.v40_console { type hw card 0 device 0 }`. Reidentify card0 before use. The investigation's external guard refuses running games, verifies the card/kernel/frontend, stops the frontend service, checks that it and graphical/game processes are gone, and provides normal and independent timed restoration. That device-specific guard is not part of this portable C source. Do not run playback alongside an unsaved game or assume that the program itself stops/restores another process.

The program requests 44,100 Hz, stereo S16_LE, RW_INTERLEAVED, 1,024-frame periods and a 2,048-frame buffer with resampling disabled. Its 52 source seconds contain 12 seconds of digital silence, four eight-second sections (left only, right only, both identical, both opposite in polarity), then eight seconds of digital silence. Tone sections contain 660 Hz beeps with 20 ms fades and quiet gaps; per-channel peak is 8,192, approximately −12.04 dBFS. Silent channels receive zero samples while both analog DAC paths remain available; this is not analog power isolation or a permanent mono downmix.

The stream stays open across those sections. Low-rate JSON logs report application writes, delay, available frames, ALSA state, CPU time and raw monotonic elapsed time. Phase labels are also written to tty1 when available. The program does not repeatedly read codec registers during playback. It aborts on ALSA errors/XRUNs rather than silently recovering, and bounds playback/drain to 105 wall seconds. Signal handling requests a bounded exit; the separate guard remains necessary for restoring the frontend after external termination or a stalled device.

Reported PCM pointers and queued-frame estimates depend on the existing kernel driver; they are not physical clock or DAC waveform measurements. Zero XRUNs do not establish correct sample contents or clean analog output. Listening results, actual frontend absence, complete playback and restoration must be verified separately. See [the console investigation](../../docs/AUDIO_CONSOLE_20261117.md).
