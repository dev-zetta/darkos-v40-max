# Audio routing and device-tree audit, 2026-11-17

The user raised [issue519](https://github.com/lcdyk0517/arkos4clone/issues/519) after the optional DACMT guard failed to remove the menu-entry pop or improve overall game noise. This audit checks the actual installed and running trees against retained factory firmware, the working BSP runtime tree and the compiled mainline artifact. No device-tree or regulator change was installed during this audit, and the running game was not interrupted.

## What issue519 establishes

The initial report proposes a vendor `rockchip,multicodecs-card` node. The [maintainer's reply](https://github.com/lcdyk0517/arkos4clone/issues/519#issuecomment-6181322865) rejects that explanation for the reported 4.4 kernel, which has no consumer for that compatible. A [later report from another user](https://github.com/lcdyk0517/arkos4clone/issues/519#issuecomment-6427634081) restores a silent R36 Max speaker by removing `use-ext-amplifier`, while retaining that unit's GPIO and mute delay. This is a single-board result with headphone and suspend behavior untested, not an accepted general pop or static fix.

In the retained BSP codec, that boolean chooses the HP DAC path for an external amplifier when handling SPK; its absence selects the internal speaker DAC/Class-D path. It is not automatic amplifier detection. The older SPK_HP selection powers HP blocks as well as speaker blocks, so working sound with that setting does not identify the physical speaker connection by itself.

Our retained factory and working BSP trees already lack `use-ext-amplifier`, speaker/headphone control GPIOs and mute-delay properties. The exact mainline codec compiled for this trial does not consume those vendor amplifier properties, and its sound-card driver is `asoc-simple-card`, not `multicodecs-card`. Removing an absent property or copying numeric phandles from issue519 would not reproduce the reported fix on this kernel.

## Compiled, installed and running identities

The installed `/boot/mainline/battery-dc-20261116/rk3326-r36splus-linux.dtb` is 52,449 bytes, SHA256 `7b7f792f6cc5bfd57affb0589bd7f528c08f5d0087dca97f565cdf47ba2da5b3`, and matches the retained compiled DTB byte for byte. The captured running FDT is 53,376 bytes, SHA256 `ba851f47f3b2d28149e35ca1d733b4b032c011161d833070e0969ef46c3fd190`. Both contain the same 451 nodes. Independent parsing finds only serial-number, boot arguments, initrd boundaries and RAM-list bootloader fixups among node properties; the runtime also adds two reservation-table entries. These whole-blob differences do not alter the audio graph.

All 40 independently collected audio/PMIC/regulator/I2S/pin nodes have identical property bytes in the selected and running trees. The broader artifact audit also matches backlight properties. Decompilation of both mainline blobs reports no dtc warnings; this is structural and identity evidence, not full binding-schema or electrical validation. No stale, swapped or differently resolved audio tree was found.

The live card is registered and bound to `asoc-simple-card`; I2S1 at `ff070000` binds to `rockchip-i2s`, and the RK817 component binds to `rk817-codec`. Resolved CPU and codec DAI references target I2S1 and the RK817 PMIC parent, respectively, as required by the mainline arrangement. The older BSP's codec-child DAI is a different binding, not a phandle to copy into this tree. I2S1 clock, data and MCLK pins are claimed by their expected drivers; I2S0 remains disabled.

## Routing correction versus output state

The factory card declares a logical “Headphone Jack” sink from HPOL/HPOR and no Speaker widget. The current mainline tree inherits a Speaker widget connected to SPKO from the ODROID board include. An external amplifier is not modeled as a separate DAPM component. This is an incomplete board description; it does not establish a verified amplifier-enable GPIO or supply net.

The exact mainline codec connects HPOL, HPOR and SPKO through a shared Playback Mux. Consequently, the logical Speaker→SPKO edge does not force the internal Class-D path. Live readback selects HP, powers the left/right DACs and HP stages, and leaves the speaker DAC and Class-D disabled. HP selection previously restored recognizable speaker music and passed clean power-on comparisons. The present game also produces recognizable sound. This supports the earlier functional HP correction, while falling short of a traced amplifier schematic or proof that every analog transition is correct.

A Speaker→HPOL/HPOR graph correction would better describe the working HP output, but it is not a literal factory Speaker property and is not predicted to change steady codec registers at the existing HP selection. It is therefore not installed or offered as a demonstrated noise remedy. Amplifier power, mute and startup behavior require a supported control model rather than an invented GPIO.

## Power-management comparison

The factory and working BSP trees explicitly request initial mode NORMAL for their buck regulators; the mainline tree does not request an initial mode in DT. The fresh regulator-framework readback reports NORMAL for all four bucks: logic, CPU, DDR and 3.3 V. Thus there is a declaration difference but no current forced-PWM-versus-NORMAL mismatch. The readback does not prove behavior on every future boot or identify which external rail powers the amplifier, and it does not justify changing an untraced rail's mode.

Factory and current backlight declarations use the same 40,000 ns period, normal polarity and default level 80 of 160. Runtime PWM readback confirms 20,000/40,000 ns at that level, equivalent to 25 kHz. No backlight-frequency mismatch was found. Regulator-framework voltages and nominal supply names are software reports, not electrical measurements of the amplifier supply or battery.

## Outcome

The optional guard boot is verified as kernel Build ID `ae0578bd8ad04be4b759c32920472861277b2537`, with its parameter enabled and its virtual mute widget active. The user reports a normal menu, the same menu-entry pop, and “Audio plays; noise unchanged” in a game. This is a negative result for that candidate; static and scrambling were not separately quantified in this comparison.

The exact previous mainline 7.3.4 boot configuration and working Image have been restored as the next-boot selection and independently checked. The candidate Image remains preserved, and the candidate kernel continues running until a later boot; no reboot or game interruption was performed for rollback. The audio symptoms remain unresolved. The remaining distinction is between analog power/startup behavior and digital content/timing faults; the successful tree-identity audit does not rule out either category, and zero ALSA XRUNs do not establish clean sample contents.
