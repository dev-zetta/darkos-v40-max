# ArkOS4Clone: V40 mainline development branch

This fork branch preserves the upstream project below and adds the [V40 Max / R36S Plus Linux 7.3.4 port](ports/v40-mainline/README.md), including kernel configuration/patches, private graphics/runtime integration, speaker routing and the physically confirmed PSP rendering and FN/SELECT/START fixes. See its [build instructions](ports/v40-mainline/BUILD.md), [validation limits](ports/v40-mainline/docs/VALIDATION.md), and [upstream credits](ports/v40-mainline/UPSTREAM.md). Audio scrambling remains unresolved; this source branch does not yet publish a new OS image. The upstream download links and build_image.sh workflow below still refer to the original BSP images.

## Upstream project

Bringing **(d)ArkOS 4.4 kernel** porting to unsupported devices. Contributions via PRs are always welcome.

> 💡 Use the [DTB Analysis Tool](https://lcdyk0517.github.io/dtbTools.html) to identify your clone type or request support for unsupported devices.

> 🔧 Use the [DTB Customization Tool](https://lcdyk0517.github.io/tools/dtb-tools.html) to customize your device settings, including joystick axis remapping, button mapping, battery capacity, and screen refresh rate.

> ⚠️ Please make sure to read the [Wiki](https://github.com/lcdyk0517/arkos4clone/wiki) thoroughly before use.

> 📝 **[View Changelog](Changelog.md)**

---

## Collaborators

- [@jokubasver](https://github.com/jokubasver) — mainly maintains support for **kernel 5.10.252**.

---

## Support the Project

![devices](https://r36s.dpdns.org/devices.jpg)

If you find (d)ArkOS4Clone helpful and want to support future development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/lcdyk)

Thank you for your support! 🙏
