FROM debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 AS kernel-builder
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential gcc-aarch64-linux-gnu libc6-dev-arm64-cross rustc python3 patch \
    bc bison flex libelf-dev libssl-dev openssl kmod cpio xz-utils \
    && rm -rf /var/lib/apt/lists/*

FROM debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2 AS runtime-builder
RUN dpkg --add-architecture arm64 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libgtest-dev build-essential crossbuild-essential-arm64 cmake ninja-build pkg-config git ca-certificates python3 \
    rustc cargo libstd-rust-dev:arm64 qemu-user \
    libsdl2-dev libsdl2-mixer-dev libsdl2-dev:arm64 libsdl2-mixer-dev:arm64 \
    libcurl4-openssl-dev:arm64 libfreetype6-dev:arm64 rapidjson-dev libfreeimage-dev:arm64 \
    libvlc-dev:arm64 libegl-dev:arm64 libgles-dev:arm64 libgbm-dev:arm64 libdrm-dev:arm64 \
    libasound2-dev:arm64 libevdev-dev:arm64 libudev-dev:arm64 libeigen3-dev \
    && rm -rf /var/lib/apt/lists/*
ENV CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc
ENV CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc
ENV PKG_CONFIG_ALLOW_CROSS=1

FROM runtime-builder AS mainline-builder
USER root
RUN dpkg --add-architecture armhf
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bc bison flex libelf-dev:amd64 libssl-dev:amd64 device-tree-compiler cpio kmod \
    python3-dev python3-venv python3-pip swig libfdt-dev qemu-system-arm gcc-arm-linux-gnueabihf libc6-dev-armhf-cross \
    libegl1:arm64 libgles1:arm64 libgles2:arm64 libgbm1:arm64 libegl-mesa0:arm64 libgl1-mesa-dri:arm64 \
    libegl1:armhf libgles1:armhf libgles2:armhf libgbm1:armhf libegl-mesa0:armhf libgl1-mesa-dri:armhf \
    libgl1:arm64 libglx0:arm64 libglx-mesa0:arm64 libopengl0:arm64 \
    libgl1:armhf libglx0:armhf libglx-mesa0:armhf libopengl0:armhf \
    meson ninja-build dpkg-dev python3-mako python3-packaging python3-yaml \
    libdrm-dev:armhf libexpat1-dev:arm64 libexpat1-dev:armhf \
    libzstd-dev:arm64 libzstd-dev:armhf zlib1g-dev:arm64 zlib1g-dev:armhf \
    libglvnd-dev:arm64 libglvnd-dev:armhf libx11-dev:arm64 libx11-dev:armhf \
    libxext-dev:arm64 libxext-dev:armhf libxfixes-dev:arm64 libxfixes-dev:armhf \
    libxcb-glx0-dev:arm64 libxcb-glx0-dev:armhf libxcb-dri2-0-dev:arm64 libxcb-dri2-0-dev:armhf \
    libxcb-dri3-dev:arm64 libxcb-dri3-dev:armhf libxcb-present-dev:arm64 libxcb-present-dev:armhf \
    libxshmfence-dev:arm64 libxshmfence-dev:armhf \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libxcb-randr0-dev:arm64 libxcb-randr0-dev:armhf libxcb-xfixes0-dev:arm64 libxcb-xfixes0-dev:armhf \
    libxcb-shm0-dev:arm64 libxcb-shm0-dev:armhf libx11-xcb-dev:arm64 libx11-xcb-dev:armhf \
    libxcb-sync-dev:arm64 libxcb-sync-dev:armhf g++-arm-linux-gnueabihf \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/dt-schema && /opt/dt-schema/bin/pip install --no-cache-dir dtschema
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libxxf86vm-dev:armhf libxrandr-dev:armhf libudev-dev:armhf libelf-dev:armhf && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/dt-schema/bin:${PATH}"

FROM mainline-builder AS v40-builder
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libgbm-dev:armhf libasound2-dev:armhf libsamplerate0-dev:armhf \
    libfontconfig-dev:arm64 libsdl2-ttf-dev:arm64 nasm pkg-config zlib1g-dev:arm64 \
    curl libxkbcommon-dev:arm64 libxkbcommon-dev:armhf \
    && rm -rf /var/lib/apt/lists/*
