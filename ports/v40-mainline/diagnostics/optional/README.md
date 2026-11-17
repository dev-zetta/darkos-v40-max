# Optional DACMT ownership diagnostic

`0001-rk817-v40-dacmt-ownership.patch` is a default-off experiment against the ported RK817 source whose SHA256 is recorded in `dacmt-ownership-build.json`. It is deliberately outside the default patch recipe. Apply it only after reproducing the retained port baseline, verify zero-fuzz applicability, and rebuild the whole matching kernel rather than replacing an unrelated distribution module.

The built-in parameter is `snd_soc_rk817.v40_dacmt_guard=1`; it additionally requires the private V40 board compatible. The diagnostic holds DACMT during normal DAPM startup, leaves unmute to DAI preparation, and preserves an assert-only DAPM power-down event. It does not control the external amplifier, add settling delays, change volume or repair a demonstrated DMA fault. Direct pin power-cycle/re-enable can remain muted until a later DAI prepare, so broad hot-routing and suspend acceptance must not be assumed.

The recorded kernel build and module-ABI checks passed. No boot, electrical, audible pop, static or scrambling repair is accepted. Keep the working mainline Image and an exact boot-configuration backup before a controlled trial. See [the investigation](../../docs/AUDIO_20261117.md) for evidence, scope and unresolved findings.
